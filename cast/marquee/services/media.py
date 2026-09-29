"""Media backends, artwork enrichment, session parsing, and Cast control."""
import json
import math
import mimetypes
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

POLL = int(os.environ.get("POLL_SECONDS", "5"))
CAST_MUTE_SETTLE = float(os.environ.get("CAST_MUTE_SETTLE_SECONDS", "0.8"))
CAST_UNMUTE_DELAY = float(os.environ.get("CAST_UNMUTE_DELAY_SECONDS", "2.5"))

FANART_KEY_ENV = os.environ.get("FANART_API_KEY", "")
FANART_TYPES = {
    "background": ("moviebackground", "showbackground"),
    "poster": ("movieposter", "tvposter"),
    "logo": ("hdmovielogo", "hdtvlogo"),
    "clearart": ("hdmovieclearart", "hdclearart"),
    "banner": ("moviebanner", "tvbanner"),
    "thumb": ("moviethumb", "tvthumb"),
}


def clamp_fanart_rotate(value):
    """Fanart rotation seconds: 300 (5 min) floor — the Hub is ambient, not a
    slideshow, and fanart.tv's CDN deserves the courtesy. 3600 ceiling."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return 600
    return max(300, min(3600, seconds))


def fanart_api_key(settings=None):
    s = settings if settings is not None else load_settings()
    return s.get("fanartKey") or FANART_KEY_ENV


def fanart_fetch(kind, fid, key):
    """Raw fanart.tv doc for /movies/{tmdb|imdb} or /tv/{tvdb}; {} on miss."""
    try:
        url = f"https://webservice.fanart.tv/v3/{kind}/{fid}?api_key={key}"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"fanart.tv fetch failed ({kind}/{fid}): {e}", flush=True)
        return {}


def fanart_urls(doc, is_movie, settings=None):
    """Best-liked art URLs of the configured type, ready for the card.

    Picked per poll (not at cache time) so changing the art type in settings
    takes effect on the next tick instead of the next title."""
    if not doc:
        return []
    s = settings if settings is not None else load_settings()
    kind = s.get("fanartType")
    if kind not in FANART_TYPES:
        kind = "background"
    arts = doc.get(FANART_TYPES[kind][0 if is_movie else 1]) or []
    arts = [a for a in arts if isinstance(a, dict) and a.get("url")]

    def likes(a):
        try:
            return int(a.get("likes") or 0)
        except (TypeError, ValueError):
            return 0
    arts.sort(key=likes, reverse=True)
    return [a["url"] for a in arts[:12]]

_meta_cache = {}  # ratingKey -> extras dict


def _cache_put(cache, key, value, cap=8):
    """Bounded FIFO insert. Keeps a few rotating titles cached (rotate_pick
    alternates the current title across concurrent sessions) without letting the
    dict grow unbounded over a long uptime. Re-putting a present key never evicts."""
    if key not in cache and len(cache) >= cap:
        cache.pop(next(iter(cache)))       # dicts are insertion-ordered: oldest out
    cache[key] = value
    return value


def plex_creds(settings=None):
    """(host, token) for Plex: the settings page wins, PLEX_HOST/PLEX_TOKEN
    env is the fallback — the same rule hub_ip() follows."""
    s = settings if settings is not None else load_settings()
    host = s.get("plexHost") or PLEX
    token = s.get("plexToken") or TOKEN
    return (host or "").rstrip("/"), token or ""


def plex_url(path):
    host, token = plex_creds()
    return f"{host}{path}{'&' if '?' in path else '?'}X-Plex-Token={token}"


def fetch_xml(path):
    with urllib.request.urlopen(plex_url(path), timeout=10) as r:
        return ET.fromstring(r.read())


def atomic_write(path, data, mode="w"):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, mode) as f:
        f.write(data)
    os.replace(tmp, path)
    # settings.json contains media credentials; display output and artwork are
    # intentionally readable by the unprivileged web process.
    os.chmod(path, 0o600 if os.path.basename(path) == "settings.json" else 0o644)


def hub_ip():
    """Device picked in settings wins; HUB_IP env is the fallback."""
    return load_settings().get("hubIp") or HUB_IP


def catt_for(target, *args):
    # Status checks must never stall the media poll; cast/stop operations can
    # retain the longer timeout for a slow-to-wake Hub.
    timeout = 6 if args and args[0] == "info" else (15 if args and args[0] == "stop" else 90)
    result = subprocess.run(["catt", "-d", target, *args],
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown catt error").strip()
        raise RuntimeError(f"catt {' '.join(args)} failed: {detail}")
    return result


def catt(*args):
    return catt_for(hub_ip(), *args)


def parse_cast_mute_state(output):
    match = re.search(r"^volume_muted:\s*(true|false)\s*$", output or "",
                      flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).lower() == "true" if match else None


def cast_mute_state(target):
    """Return the receiver mute state, or None when it cannot be determined."""
    try:
        output = catt_for(target, "info").stdout
        return parse_cast_mute_state(output)
    except Exception as e:
        log_warn(f"cast mute state unavailable for {target}: {e}")
        return None


def quiet_cast_site(target, url):
    """Launch DashCast without the receiver connection sound.

    Muting is allowed time to reach the receiver before the new application is
    launched. The receiver's original mute state is restored after DashCast has
    connected, so an intentionally muted display remains muted.
    """
    previous_mute = cast_mute_state(target)
    muted = False
    try:
        catt_for(target, "volumemute", "true")
        muted = True
        time.sleep(max(0.0, CAST_MUTE_SETTLE))
        catt_for(target, "cast_site", url)
    finally:
        if muted:
            time.sleep(max(0.0, CAST_UNMUTE_DELAY))
            # Unknown normally means the receiver was waking up. Restore the
            # common unmuted state; a known prior state is always respected.
            catt_for(target, "volumemute",
                     "true" if previous_mute is True else "false")


_scan_cache = {"at": 0.0, "devices": []}


def parse_scan(text):
    """catt scan lines look like: '192.168.1.50 - Living Room - Google Nest Hub'."""
    devices = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d{1,3}(?:\.\d{1,3}){3})\s+-\s+(.+?)\s+-\s+(.*)", line)
        if m:
            devices.append({"ip": m.group(1), "name": m.group(2),
                            "model": m.group(3).strip()})
    return devices


def scan_devices(refresh=False):
    """Google Cast devices announce over mDNS; catt scan collects them."""
    if refresh or time.time() - _scan_cache["at"] > 300:
        try:
            result = subprocess.run(["catt", "scan"], capture_output=True,
                                    text=True, timeout=45)
            _scan_cache.update(at=time.time(),
                               devices=parse_scan(result.stdout))
        except Exception as e:
            print(f"device scan failed: {e}", flush=True)
    return {"devices": _scan_cache["devices"], "current": hub_ip()}


def dashcast_active():
    return "DashCast" in catt("info").stdout


def garage_dashcast_active():
    """Best-effort stale-card check; a sleeping garage Hub is not a poll error."""
    try:
        return bool(GARAGE_HUB_IP and
                    "DashCast" in catt_for(GARAGE_HUB_IP, "info").stdout)
    except Exception as e:
        log_warn(f"garage display status unavailable: {e}")
        return False


_wx_cache = {"at": 0.0, "zip": None, "loc": "", "data": {}}


def weather():
    """One authoritative HA observation for every display; never geolocate."""
    try:
        with open(HA_WEATHER_PATH) as handle:
            value = json.load(handle)
        if not 0 <= time.time() - float(value.get("updated", 0)) < 1800:
            return {"temp": None, "condition": "unavailable"}
        return value
    except (OSError, ValueError, TypeError):
        return {"temp": None, "condition": "unavailable"}


def tmdb_stinger(tmdb_id):
    """['during'|'after', ...] from TMDb keywords (aftercreditsstinger etc.)."""
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/keywords?api_key={TMDB_KEY}"
    with urllib.request.urlopen(url, timeout=10) as r:
        names = {k["name"] for k in json.load(r).get("keywords", [])}
    return [w for w, kw in (("during", "duringcreditsstinger"),
                            ("after", "aftercreditsstinger")) if kw in names]


def transcode_to(path, plex_path, w, h):
    host, token = plex_creds()
    source = (f"{plex_path}?X-Plex-Token={token}"
              if str(plex_path).startswith("/") else str(plex_path))
    inner = urllib.parse.quote(source, safe="")
    url = (f"{host}/photo/:/transcode?width={w}&height={h}&minSize=1"
           f"&upscale=1&url={inner}&X-Plex-Token={token}")
    with urllib.request.urlopen(url, timeout=15) as r:
        atomic_write(os.path.join(OUTPUT, path), r.read(), "wb")


def env_first(*names):
    """First non-empty env var among names; "" when none is set. An
    empty-but-present var counts as unset — a compose file that lists
    `JELLYFIN_HOST: ""` next to a filled EMBY_HOST must not shadow it."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


# Jellyfin honors the same api_key query auth and endpoint shapes as Emby, so
# either env pair works with either backend; the pair matching the backend
# name wins when both are set. A host/key stored from the settings page wins
# over env — the same rule hub_ip() follows.
def emby_creds(backend=None, settings=None):
    """(host, key) for the emby-family backend in force."""
    s = settings if settings is not None else load_settings()
    if backend is None:
        backend = media_backend(s)
    if backend == "jellyfin":
        host = s.get("jellyfinHost") or env_first("JELLYFIN_HOST", "EMBY_HOST")
        key = s.get("jellyfinKey") or env_first("JELLYFIN_API_KEY", "EMBY_API_KEY")
    else:
        host = s.get("embyHost") or env_first("EMBY_HOST", "JELLYFIN_HOST")
        key = s.get("embyKey") or env_first("EMBY_API_KEY", "JELLYFIN_API_KEY")
    return (host or "").rstrip("/"), key or ""


def emby_url(path, creds=None):
    host, key = creds or emby_creds()
    base = host + path
    return f"{base}{'&' if '?' in base else '?'}api_key={key}"


def emby_fetch_json(path):
    with urllib.request.urlopen(emby_url(path), timeout=10) as r:
        return json.load(r)


def emby_image_url(host, key, item_id, kind, w=600, h=900):
    return (f"{host.rstrip('/')}/Items/{item_id}/Images/{kind}"
            f"?maxWidth={w}&maxHeight={h}&api_key={key}")


def emby_save_image(item_id, kind, out_name, w, h):
    host, key = emby_creds()
    url = emby_image_url(host, key, item_id, kind, w, h)
    with urllib.request.urlopen(url, timeout=15) as r:
        atomic_write(os.path.join(OUTPUT, out_name), r.read(), "wb")


def emby_download_art(item):
    """Save poster/backdrop/logo for an Emby item into output/."""
    out = {"poster": False, "backdrop": False, "logo": False}
    item_id = item.get("Id")
    tags = item.get("ImageTags") or {}
    if item.get("Type") == "Episode" and item.get("SeriesId"):
        poster_id = item["SeriesId"]
    else:
        poster_id = item_id
    try:
        if poster_id:
            emby_save_image(poster_id, "Primary", "poster.jpg", 600, 900)
            out["poster"] = True
    except Exception:
        pass
    backdrop_id = item.get("ParentBackdropItemId") or item.get("SeriesId") or item_id
    try:
        if backdrop_id:
            emby_save_image(backdrop_id, "Backdrop/0", "backdrop.jpg", 1280, 800)
            out["backdrop"] = True
    except Exception:
        pass
    logo_id = item.get("ParentLogoItemId") or item.get("SeriesId") or item_id
    try:
        if "Logo" in tags or logo_id:
            emby_save_image(logo_id, "Logo", "logo.png", 800, 310)
            out["logo"] = True
    except Exception:
        pass
    return out


def select_clean_plex_poster(images):
    """Prefer an untouched remote TMDb poster over Plex's selected overlay."""
    choices = [image for image in images if image.get("selected") != "1"]
    ranked = sorted(choices, key=lambda image: (
        0 if image.get("provider") == "tmdb" and
             str(image.get("key", "")).startswith("https://") else
        1 if str(image.get("key", "")).startswith("https://") else 2))
    return ranked[0].get("key", "") if ranked else ""


def select_clean_plex_art(images):
    """Prefer an unselected remote backdrop, avoiding Posterizarr overlays."""
    return select_clean_plex_poster(images)


def plex_clean_poster(item, rating_key):
    """Resolve a clean poster already advertised by Plex; empty on any miss."""
    artwork_key = item.get("grandparentRatingKey") or rating_key
    try:
        root = fetch_xml(f"/library/metadata/{artwork_key}/posters")
        return select_clean_plex_poster(list(root))
    except Exception as error:
        log_warn(f"clean Plex poster unavailable for {artwork_key}: {error}")
        return ""


def plex_clean_backdrop(item, rating_key):
    """Resolve a clean series/movie backdrop already advertised by Plex."""
    artwork_key = (item.get("grandparentRatingKey")
                   or item.get("parentRatingKey") or rating_key)
    try:
        root = fetch_xml(f"/library/metadata/{artwork_key}/arts")
        return select_clean_plex_art(list(root))
    except Exception as error:
        log_warn(f"clean Plex backdrop unavailable for {artwork_key}: {error}")
        return ""


def download_art(item, rating_key):
    """Save poster.jpg, backdrop.jpg, logo.png into output/."""
    out = {"poster": False, "backdrop": False, "logo": False}
    poster = (plex_clean_poster(item, rating_key)
              if load_settings().get("plexCleanPosters", True) else "")
    poster = poster or item.get("grandparentThumb") or item.get("thumb")
    if poster:
        transcode_to("poster.jpg", poster, 600, 900)
        out["poster"] = True
        try:
            out["posterVersion"] = str(os.stat(
                os.path.join(OUTPUT, "poster.jpg")).st_mtime_ns)
        except OSError:
            pass
    backdrop = (plex_clean_backdrop(item, rating_key)
                if load_settings().get("plexCleanPosters", True) else "")
    backdrop = backdrop or item.get("art")
    if backdrop:
        transcode_to("backdrop.jpg", backdrop, 1280, 800)
        out["backdrop"] = True
        try:
            out["backdropVersion"] = str(os.stat(
                os.path.join(OUTPUT, "backdrop.jpg")).st_mtime_ns)
        except OSError:
            pass
    try:
        with urllib.request.urlopen(
                plex_url(f"/library/metadata/{rating_key}/clearLogo"), timeout=15) as r:
            atomic_write(os.path.join(OUTPUT, "logo.png"), r.read(), "wb")
        out["logo"] = True
    except Exception:
        pass
    return out


def library_extras(rating_key, is_movie=False):
    """Genres, IMDb, stinger, art/logo from the full metadata record; cached per item."""
    if rating_key in _meta_cache:
        return _meta_cache[rating_key]
    x = {"genres": [], "imdb": None, "stinger": [],
         "poster": False, "backdrop": False, "logo": False,
         "fanartDoc": {}, "fanartMovie": is_movie}
    try:
        root = fetch_xml(f"/library/metadata/{rating_key}?includeRatings=1")
        item = root.find("./*")
        if item is not None:
            x["genres"] = [g.get("tag") for g in item.findall("Genre") if g.get("tag")]
            for r in item.findall("Rating"):
                if (r.get("image") or "").startswith("imdb://") and r.get("value"):
                    x["imdb"] = float(r.get("value"))
            if TMDB_KEY and is_movie:
                for g in item.findall("Guid"):
                    if (g.get("id") or "").startswith("tmdb://"):
                        x["stinger"] = tmdb_stinger(g.get("id")[7:])
                        break
            x.update(download_art(item, rating_key))
            fkey = fanart_api_key()
            if fkey:
                if is_movie:
                    guids = [(g.get("id") or "") for g in item.findall("Guid")]
                    fid = next((g[7:] for g in guids if g.startswith("tmdb://")),
                               None) or next((g[7:] for g in guids
                                              if g.startswith("imdb://")), None)
                    if fid:
                        x["fanartDoc"] = fanart_fetch("movies", fid, fkey)
                else:
                    # fanart.tv keys TV on the SHOW's TheTVDB id; an episode's
                    # own tvdb guid is the episode, so read the grandparent.
                    show = item
                    if item.get("grandparentRatingKey"):
                        show = fetch_xml("/library/metadata/"
                                         + item.get("grandparentRatingKey")).find("./*")
                    guids = ([(g.get("id") or "") for g in show.findall("Guid")]
                             if show is not None else [])
                    fid = next((g[7:] for g in guids if g.startswith("tvdb://")), None)
                    if fid:
                        x["fanartDoc"] = fanart_fetch("tv", fid, fkey)
    except Exception as e:
        log_warn(f"metadata fetch failed for {rating_key}: {e}")
    # Cap rather than clear: with 2+ concurrent sessions rotate_pick alternates
    # the "current" title each bucket, so clearing evicted the other one → a full
    # metadata + art + TMDB/fanart refetch on every rotation flip. Keep a few.
    _cache_put(_meta_cache, rating_key, x)
    return x


def pretty_resolution(res):
    if not res:
        return None
    return {"4k": "4K", "sd": "SD"}.get(res.lower(), res + "p" if res.isdigit() else res.upper())


def emby_ticks_to_ms(ticks):
    return int(ticks) // 10000 if ticks is not None else None


def normalized_progress(offset, duration):
    """Return bounded source progress, or no progress when duration is unusable.

    Providers occasionally report a negative offset, an offset beyond the end,
    or a zero duration while a session is being established.  The renderer
    must receive one sane contract rather than reimplementing those rules.
    """
    try:
        total = int(duration)
        current = int(offset or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return {"offsetMs": max(0, min(current, total)), "durationMs": total}


def emby_resolution(width, height=None):
    """Label resolution by frame Width. Height is unreliable for
    letterboxed/scope films (a 1080p 2.76:1 movie is 1920x696, which by
    height would mislabel as "696p"). Width tracks the resolution tier."""
    w = int(width) if width else 0
    if w >= 3800:
        return "4K"
    if w >= 2500:
        return "1440p"
    if w >= 1800:
        return "1080p"
    if w >= 1200:
        return "720p"
    if w >= 700:
        return "480p"
    if height:  # width missing/odd -> fall back to height buckets
        return {2160: "4K", 1080: "1080p", 720: "720p", 480: "480p"}.get(
            int(height), f"{int(height)}p")
    return f"{w}px" if w else None


def bool_value(value):
    """Boolean-ish media API values without treating the string "false" as true."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "lan", "local"):
        return True
    if text in ("0", "false", "no", "off", "wan", "remote"):
        return False
    return None


def int_value(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalized_year(value):
    """Return a real calendar year, omitting Plex placeholder payloads."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        return None
    return str(int(number))


def bitrate_kbps(value, bits_per_second=False):
    """Normalise Plex kbps and Emby/Jellyfin bits-per-second values to kbps."""
    number = int_value(value)
    if number is None or number <= 0:
        return None
    return round(number / 1000) if bits_per_second else number


def channel_label(channels, layout=None):
    """Compact speaker-layout label shared by Plex, Emby and Jellyfin."""
    if layout:
        text = str(layout).strip()
        if text:
            return text.upper().replace("CH", " ch")
    number = int_value(channels)
    return {1: "Mono", 2: "2.0", 6: "5.1", 8: "7.1"}.get(
        number, f"{number} ch" if number else None)


def dynamic_range_label(*values):
    """Return a friendly HDR label, ignoring ordinary SDR markers."""
    text = " ".join(str(v) for v in values if v).lower()
    if not text or text.strip() == "sdr":
        return None
    if "dovi" in text or "dolby vision" in text:
        return "Dolby Vision"
    if "hdr10+" in text or "hdr10plus" in text:
        return "HDR10+"
    if "hdr10" in text:
        return "HDR10"
    if "hlg" in text:
        return "HLG"
    if "hdr" in text:
        return "HDR"
    return None


def playback_decision(*values):
    """Collapse backend-specific playback methods into three user labels."""
    methods = [re.sub(r"[^a-z]", "", str(v).lower()) for v in values if v]
    if any("transcod" in method for method in methods):
        return "Transcoding"
    if any(method in ("copy", "directstream", "remux")
           or "directstream" in method for method in methods):
        return "Direct Stream"
    if any("directplay" in method for method in methods):
        return "Direct Play"
    return None


def track_payload(language=None, codec=None, channels=None, layout=None,
                  title=None, display=None, spatial=None):
    """Common audio/subtitle shape used by every media backend."""
    # Atmos is signalled in the codec profile or the display title (Plex encodes
    # it in extendedDisplayTitle, e.g. "…Dolby Atmos") — a user-entered track
    # *title* is not authoritative, so keep it out or "Atmospheric Score" reads
    # as Atmos.
    spatial_text = " ".join(str(v) for v in (display, spatial) if v)
    return {
        "language": language or None,
        "codec": str(codec).upper() if codec else None,
        "channels": channel_label(channels, layout),
        "title": title or None,
        "display": display or None,
        "spatial": "Atmos" if "atmos" in spatial_text.lower() else None,
    }


def plex_stream(video, stream_type, default_ok=True):
    streams = [s for s in video.findall(".//Stream")
               if s.get("streamType") == str(stream_type)]
    selected = next((s for s in streams if bool_value(s.get("selected")) is True), None)
    if selected is not None:
        return selected
    if not default_ok:
        return None
    return next((s for s in streams if bool_value(s.get("default")) is True),
                streams[0] if streams else None)


def plex_track(stream):
    if stream is None:
        return None
    return track_payload(
        language=stream.get("language") or stream.get("languageCode"),
        codec=stream.get("codec"), channels=stream.get("channels"),
        layout=stream.get("audioChannelLayout"), title=stream.get("title"),
        display=stream.get("extendedDisplayTitle") or stream.get("displayTitle"),
        spatial=stream.get("profile"))


def plex_session_payload(video, position=None):
    """Viewer, device, stream and track data from one Plex Video session."""
    user, device = session_names(video)
    player = video.find("Player")
    session = video.find("Session")
    media = video.find("Media")
    part = media.find("Part") if media is not None else video.find(".//Part")
    transcode = video.find("TranscodeSession")
    video_track = plex_stream(video, 1)
    audio_track = plex_stream(video, 2)
    subtitle_track = plex_stream(video, 3, default_ok=False)

    local = bool_value(player.get("local")) if player is not None else None
    if local is None and session is not None:
        local = bool_value(session.get("location"))
    pos, count = position or (1, 1)
    session_info = {
        "user": user or None,
        "device": device or None,
        "client": ((player.get("product") or player.get("platform"))
                   if player is not None else None),
        "platform": ((player.get("platform") or player.get("device"))
                     if player is not None else None),
        "local": local,
        "position": pos,
        "count": count,
    }

    decisions = []
    for node in (transcode, media, part):
        if node is not None:
            decisions.extend(node.get(k) for k in
                             ("decision", "videoDecision", "audioDecision",
                              "subtitleDecision"))
    decision = playback_decision(*decisions)
    if not decision and media is not None:
        decision = "Direct Play"
    source_resolution = None
    if media is not None:
        source_resolution = (pretty_resolution(media.get("videoResolution"))
                             or emby_resolution(media.get("width"), media.get("height")))
    output_resolution = None
    if transcode is not None:
        output_resolution = (pretty_resolution(transcode.get("videoResolution"))
                             or emby_resolution(transcode.get("width"),
                                                transcode.get("height")))
    hdr = dynamic_range_label(
        media.get("videoDynamicRange") if media is not None else None,
        video_track.get("videoDynamicRange") if video_track is not None else None,
        video_track.get("HDRFormat") if video_track is not None else None,
        "dovi" if video_track is not None and any(
            bool_value(video_track.get(k)) is True for k in
            ("DOVIPresent", "DOVIBLPresent", "DOVIELPresent")) else None,
        video_track.get("displayTitle") if video_track is not None else None)
    stream_info = {
        "decision": decision,
        "sourceResolution": source_resolution,
        "outputResolution": output_resolution,
        "videoCodec": ((media.get("videoCodec") if media is not None else None)
                       or (video_track.get("codec") if video_track is not None else None)),
        "audioCodec": ((media.get("audioCodec") if media is not None else None)
                       or (audio_track.get("codec") if audio_track is not None else None)),
        "dynamicRange": hdr,
        "bitrateKbps": bitrate_kbps(media.get("bitrate")) if media is not None else None,
        "bandwidthKbps": bitrate_kbps(session.get("bandwidth"))
                         if session is not None else None,
        "hardware": bool(transcode is not None and any(
            bool_value(transcode.get(k)) is True for k in
            ("transcodeHwRequested", "transcodeHwFullPipeline"))),
    }
    tracks = {"audio": plex_track(audio_track),
              "subtitle": plex_track(subtitle_track)}
    return session_info, stream_info, tracks


def emby_stream(item, kind, index=None, default_ok=True):
    streams = [s for s in (item.get("MediaStreams") or []) if s.get("Type") == kind]
    if index is not None:
        wanted = int_value(index)
        match = next((s for s in streams if int_value(s.get("Index")) == wanted), None)
        if match is not None:
            return match
    if not default_ok:
        return None
    return next((s for s in streams if s.get("IsDefault") is True),
                streams[0] if streams else None)


def emby_track(stream):
    if stream is None:
        return None
    return track_payload(
        language=stream.get("Language"), codec=stream.get("Codec"),
        channels=stream.get("Channels"), layout=stream.get("ChannelLayout"),
        title=stream.get("Title"),
        display=stream.get("DisplayTitle") or stream.get("ExtendedVideoType"),
        spatial=stream.get("Profile"))


def emby_session_payload(session, position=None):
    """Viewer, device, stream and track data from Emby/Jellyfin /Sessions."""
    item = session.get("NowPlayingItem") or {}
    play = session.get("PlayState") or {}
    transcode = session.get("TranscodingInfo") or {}
    video = emby_stream(item, "Video")
    audio = emby_stream(item, "Audio", play.get("AudioStreamIndex"))
    subtitle_index = play.get("SubtitleStreamIndex")
    subtitle = (emby_stream(item, "Subtitle", subtitle_index, default_ok=False)
                if int_value(subtitle_index) is not None
                and int_value(subtitle_index) >= 0 else None)
    pos, count = position or (1, 1)
    user, device = emby_session_names(session)
    session_info = {
        "user": user or None,
        "device": device or None,
        "client": session.get("Client") or None,
        "platform": session.get("DeviceName") or None,
        "local": None,
        "position": pos,
        "count": count,
    }
    decision = playback_decision(play.get("PlayMethod"), transcode.get("PlayMethod"))
    if not decision:
        if transcode:
            decision = ("Direct Stream" if transcode.get("IsVideoDirect") is True
                        and transcode.get("IsAudioDirect") is True else "Transcoding")
        elif item:
            decision = "Direct Play"
    source_resolution = (emby_resolution(video.get("Width"), video.get("Height"))
                         if video else None)
    output_resolution = (emby_resolution(transcode.get("Width"), transcode.get("Height"))
                         if transcode else None)
    stream_info = {
        "decision": decision,
        "sourceResolution": source_resolution,
        "outputResolution": output_resolution,
        "videoCodec": ((transcode.get("VideoCodec") if transcode else None)
                       or (video.get("Codec") if video else None)),
        "audioCodec": ((transcode.get("AudioCodec") if transcode else None)
                       or (audio.get("Codec") if audio else None)),
        "dynamicRange": dynamic_range_label(
            video.get("VideoRangeType") if video else None,
            video.get("VideoRange") if video else None,
            video.get("DisplayTitle") if video else None,
            video.get("VideoDoViTitle") if video else None),
        "bitrateKbps": bitrate_kbps(
            (transcode.get("Bitrate") if transcode else None)
            or (video.get("BitRate") if video else None), bits_per_second=True),
        "bandwidthKbps": bitrate_kbps(
            transcode.get("Bitrate") if transcode else None,
            bits_per_second=True),
        "hardware": bool(transcode.get("HardwareAccelerationType")) if transcode else False,
    }
    tracks = {"audio": emby_track(audio), "subtitle": emby_track(subtitle)}
    return session_info, stream_info, tracks


def parse_emby_session(session, extras, position=None):
    """One Emby /Sessions entry -> now-playing dict (same shape as Plex)."""
    item = session.get("NowPlayingItem") or {}
    play = session.get("PlayState") or {}
    is_episode = item.get("Type") == "Episode"
    info = {
        "playing": True,
        "type": (item.get("Type") or "").lower(),
        "key": item.get("Id"),
        "title": item.get("SeriesName") if is_episode else item.get("Name"),
        "year": item.get("ProductionYear"),
    }
    info["session"], info["stream"], info["tracks"] = \
        emby_session_payload(session, position)
    if is_episode and item.get("ParentIndexNumber") and item.get("IndexNumber"):
        info["subtitle"] = (f"S{item['ParentIndexNumber']} · "
                            f"E{item['IndexNumber']} · {item.get('Name')}")
    info["state"] = "paused" if play.get("IsPaused") else "playing"
    offset = emby_ticks_to_ms(play.get("PositionTicks"))
    duration = emby_ticks_to_ms(item.get("RunTimeTicks"))
    progress = normalized_progress(offset, duration)
    if progress:
        info["progress"] = progress
    if duration:
        m = duration // 60000
        info["runtime"] = f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"
    if item.get("Overview"):
        info["summary"] = item["Overview"]
    if item.get("OfficialRating"):
        info["contentRating"] = item["OfficialRating"]
    genres = [g for g in (item.get("Genres") or []) if g]
    if genres:
        info["genres"] = genres[:3]
    streams = item.get("MediaStreams") or []
    video = next((s for s in streams if s.get("Type") == "Video"), None)
    audio = next((s for s in streams if s.get("Type") == "Audio"), None)
    parts = [emby_resolution(video.get("Width"), video.get("Height")) if video else None,
             (video.get("Codec") or "").upper() or None if video else None,
             (audio.get("Codec") or "").upper() or None if audio else None]
    media = " · ".join(p for p in parts if p)
    if media:
        info["media"] = media
    scores = {}
    if item.get("CommunityRating"):
        scores["imdb"] = round(float(item["CommunityRating"]), 1)
    if item.get("CriticRating") is not None:
        scores["rtCritic"] = round(float(item["CriticRating"]))
        scores["rtCriticFresh"] = float(item["CriticRating"]) >= 60
    if scores:
        info["scores"] = scores
    x = extras(item)
    if x.get("stinger"):
        info["stinger"] = x["stinger"]
    fa = fanart_urls(x.get("fanartDoc"), x.get("fanartMovie", True))
    if fa:
        info["fanart"] = fa
    info["poster"] = x.get("poster", False)
    info["backdrop"] = x.get("backdrop", False)
    info["logo"] = x.get("logo", False)
    return info


def parse_session(video, extras=library_extras, position=None):
    """Video element from /status/sessions -> now-playing dict."""
    a = video.get
    is_episode = a("type") == "episode"
    info = {
        "playing": True,
        "type": a("type"),
        "key": a("ratingKey"),
        "title": a("grandparentTitle") if is_episode else a("title"),
    }
    year = normalized_year(a("year"))
    if year is not None:
        info["year"] = year
    info["session"], info["stream"], info["tracks"] = \
        plex_session_payload(video, position)
    if is_episode and a("parentIndex") and a("index"):
        episode_title = a("title") or ""
        episode_label = " - ".join(part for part in (year, episode_title) if part)
        info["subtitle"] = " · ".join(
            part for part in (f"S{a('parentIndex')}", f"E{a('index')}",
                              episode_label) if part)

    x = (extras(a("ratingKey"), a("type") == "movie") if a("ratingKey")
         else {"genres": [], "imdb": None, "stinger": [],
               "poster": False, "backdrop": False, "logo": False})
    fa = fanart_urls(x.get("fanartDoc"), x.get("fanartMovie", True))
    if fa:
        info["fanart"] = fa

    player = video.find("Player")
    if player is not None and player.get("state"):
        info["state"] = player.get("state")
    progress = normalized_progress(a("viewOffset"), a("duration"))
    if progress:
        info["progress"] = progress
    if a("summary"):
        info["summary"] = a("summary")
    if x["genres"]:
        info["genres"] = x["genres"][:3]
    if x["stinger"]:
        info["stinger"] = x["stinger"]
    info["poster"] = x["poster"]
    info["posterVersion"] = x.get("posterVersion", "")
    info["backdrop"] = x["backdrop"]
    info["backdropVersion"] = x.get("backdropVersion", "")
    info["logo"] = x["logo"]
    if a("contentRating"):
        info["contentRating"] = a("contentRating")
    if a("duration"):
        m = int(a("duration")) // 60000
        info["runtime"] = f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"
    media = video.find("Media")
    if media is not None:
        parts = [pretty_resolution(media.get("videoResolution")),
                 (media.get("videoCodec") or "").upper() or None,
                 (media.get("audioCodec") or "").upper() or None]
        info["media"] = " · ".join(p for p in parts if p)
    scores = {}
    if "rottentomatoes" in (a("ratingImage") or "") and a("rating"):
        scores["rtCritic"] = round(float(a("rating")) * 10)
        scores["rtCriticFresh"] = "ripe" in a("ratingImage")
    if "rottentomatoes" in (a("audienceRatingImage") or "") and a("audienceRating"):
        scores["rtAudience"] = round(float(a("audienceRating")) * 10)
        scores["rtAudienceFresh"] = "upright" in a("audienceRatingImage")
    if x["imdb"]:
        scores["imdb"] = x["imdb"]
    if scores:
        info["scores"] = scores
    return info


def session_names(video):
    """(user, device) display names for a session; device falls back through
    Player title -> device -> product."""
    user = video.find("User")
    player = video.find("Player")
    u = (user.get("title") or "") if user is not None else ""
    d = ""
    if player is not None:
        d = player.get("title") or player.get("device") or player.get("product") or ""
    return u, d


def session_sort_key(user, device, title):
    """A total, case-insensitive order over sessions.

    /status/sessions has no defined order and Plex reorders it as sessions come
    and go, so "the first allowed session" is not a stable choice. Sorting first
    makes the pick deterministic: every poll, and every display, agrees.
    """
    return ((user or "").lower(), (device or "").lower(), (title or "").lower())


def clamp_rotate(value):
    """Rotation period in seconds: 0 disables, otherwise 5..3600."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return 30
    if seconds <= 0:
        return 0
    return max(5, min(3600, seconds))


def rotate_pick(items, seconds, now=None):
    """Which of several equally-allowed sessions drives the display right now.

    The choice is a pure function of the wall clock, so it needs no state and
    survives a restart mid-rotation. `seconds` <= 0 pins the first session.
    """
    if not items:
        return None
    if len(items) == 1 or seconds <= 0:
        return items[0]
    now = time.time() if now is None else now
    return items[int(now // seconds) % len(items)]


def session_allowed(video, users=None, devices=None):
    """True when the session's Plex user AND device pass the allow-lists
    (an empty list allows everyone / any device).

    /status/sessions is server-wide: with the owner token it includes every
    shared and home user, so without a filter the marquee reacts to anyone
    streaming from the library.
    """
    users = USERS if users is None else users
    devices = DEVICES if devices is None else devices
    u, d = session_names(video)
    if users and u.lower() not in users:
        return False
    if devices:
        player = video.find("Player")
        if player is None:
            return False
        names = {(player.get(k) or "").lower()
                 for k in ("title", "device", "product")} - {""}
        if not (names & devices):
            return False
    return True


LAST_SESSIONS = []  # every active session from the last poll, filtered or not
PLEX_PAUSE_GRACE = 300  # keep a short pause visible, then return to the dashboard
PLEX_PAUSED_SINCE = {}


def plex_live_sessions(videos, server="", now=None):
    """Bound Plex's lingering paused sessions independently for each player.

    Some clients remain in /status/sessions for hours after powering off.
    Only an observed resume resets the pause deadline; repeated paused polls
    must not extend it. Monotonic time avoids clock adjustments extending it.
    After a process restart a paused session receives at most one new grace.
    """
    now = time.monotonic() if now is None else now
    present, live = set(), []
    for video in videos:
        player = video.find("Player")
        session = video.find("Session")
        user, device = session_names(video)
        identity = (server, video.get("sessionKey") or
                    (session.get("id") if session is not None else ""),
                    (player.get("machineIdentifier") or device) if player is not None else device,
                    user, video.get("ratingKey") or video.get("key"))
        present.add(identity)
        state = (player.get("state") or "").lower() if player is not None else ""
        if state in ("stopped", "ended"):
            PLEX_PAUSED_SINCE.pop(identity, None)
            continue
        if state == "paused":
            since = PLEX_PAUSED_SINCE.setdefault(identity, now)
            if now - since >= PLEX_PAUSE_GRACE:
                continue
        else:
            PLEX_PAUSED_SINCE.pop(identity, None)
        live.append(video)
    for identity in list(PLEX_PAUSED_SINCE):
        if identity not in present:
            del PLEX_PAUSED_SINCE[identity]
    return live

# The card page fetches /now-playing.json every POLL seconds. When it stops, the
# page is gone even if the Hub still reports the DashCast app as loaded.
# `at` is only ever set by a real request, so /healthz reports the truth; the
# grace window a freshly cast page gets is tracked separately rather than by
# faking a poll -- seeding `at` would make a card that never polled look alive.
LAST_CARD_POLL = {"at": 0.0, "clients": {}}
CARD_GRACE = {"until": 0.0}
CARD_TIMEOUT = max(45, POLL * 6)
GARAGE_STATE = {"occupied": False, "updated": 0.0}


def card_alive(now, last_poll, timeout=CARD_TIMEOUT):
    """True when the card fetched now-playing.json recently enough."""
    return bool(last_poll) and (now - last_poll) < timeout


def card_ok(now, last_poll, grace_until, timeout=CARD_TIMEOUT):
    """Leave the Hub alone: the card is polling, or a freshly cast page is still
    inside the window we give it to load and check in."""
    return card_alive(now, last_poll, timeout) or now < grace_until


def main_card_poll():
    """Heartbeat from the primary Hub only; a garage/dashboard client must not
    hide a dead primary card."""
    return LAST_CARD_POLL["clients"].get(hub_ip(), 0.0)


def cast_card(target=None):
    """Load the card on the Hub, and let it be silent for one timeout window."""
    target = target or hub_ip()
    display = "garage" if target == GARAGE_HUB_IP else "hubs"
    url = urllib.parse.urlsplit(PAGE_URL)
    query = urllib.parse.parse_qs(url.query)
    path = url.path
    if cast_kiosk_enabled(display):
        path = "/kiosk"
        query["receiver"] = ["1"]
    query["display"] = [display]
    query["cb"] = [str(int(time.time()))]
    page_url = urllib.parse.urlunsplit((url.scheme, url.netloc, path,
                                      urllib.parse.urlencode(query, doseq=True), url.fragment))
    quiet_cast_site(target, page_url)
    if target == hub_ip():
        CARD_GRACE["until"] = time.time() + CARD_TIMEOUT


def current_session():
    s = load_settings()
    host, token = plex_creds(s)
    if not (host and token):
        return None   # not configured yet — the settings page can fix it live
    users = filter_set(s.get("plexUsers"), ENV_USERS)
    devices = filter_set(s.get("plexDevices"), ENV_DEVICES)
    block = filter_set(s.get("blockTags"), ENV_BLOCK_TAGS)
    root = fetch_xml("/status/sessions")
    seen, allowed = [], []
    for video in plex_live_sessions(root.findall("Video"), server=host):
        if video.get("type") not in ("movie", "episode"):
            continue
        u, d = session_names(video)
        title = video.get("title") or ""
        ok = (session_allowed(video, users, devices)
              and not content_blocked(block, plex_item_terms(video)))
        seen.append({"user": u, "device": d, "title": title, "allowed": ok})
        if ok:
            allowed.append((session_sort_key(u, d, title), video))
    LAST_SESSIONS[:] = seen
    # Sort before picking: the server's order is not stable, and without this
    # the card flips between two people's sessions on an arbitrary poll.
    allowed.sort(key=lambda pair: pair[0])
    candidates = [video for _, video in allowed]
    picked = rotate_pick(candidates, clamp_rotate(s.get("rotateSeconds")))
    if picked is None:
        return None
    info = parse_session(picked, position=(candidates.index(picked) + 1,
                                           len(candidates)))
    # The rotation count only covers allowed candidates. Active streams is a
    # separate server-wide indicator and intentionally includes filtered
    # movie/episode sessions without exposing their titles or users.
    info.setdefault("session", {})["activeStreams"] = len(seen)
    return info


def emby_session_names(s):
    """(user, device) display names for an Emby session; device falls back
    from DeviceName to Client, mirroring session_names() on the Plex path."""
    return (s.get("UserName") or "",
            s.get("DeviceName") or s.get("Client") or "")


def emby_session_allowed(s, users, devices):
    """True when the session's user AND device pass the allow-lists
    (an empty list allows everyone / any device)."""
    if users and (s.get("UserName") or "").lower() not in users:
        return False
    if devices:
        names = {(s.get(k) or "").lower()
                 for k in ("DeviceName", "Client")} - {""}
        if not (names & devices):
            return False
    return True


def emby_select_session(sessions, users, devices=frozenset()):
    """First session with a Movie/Episode NowPlayingItem whose user AND device
    pass the allow-lists (an empty list allows everyone / any device)."""
    for s in sessions:
        item = s.get("NowPlayingItem")
        if not item or item.get("Type") not in ("Movie", "Episode"):
            continue
        if not emby_session_allowed(s, users, devices):
            continue
        return s
    return None


_emby_meta_cache = {}    # item Id -> extras dict; current item only (mirrors _meta_cache)
_emby_enrich_cache = {}  # item Id -> enrichment fields; current item only


def emby_extras(item):
    """TMDB stinger + downloaded art for an Emby item; cached once per item.

    Without this, loop() would re-download poster/backdrop/logo and re-hit TMDB
    every POLL_SECONDS for the whole runtime — matching the Plex library_extras
    cache keeps it to one fetch per title.
    """
    key = item.get("Id")
    if key and key in _emby_meta_cache:
        return _emby_meta_cache[key]
    is_movie = item.get("Type") == "Movie"
    x = {"stinger": [], "poster": False, "backdrop": False, "logo": False,
         "fanartDoc": {}, "fanartMovie": is_movie}
    try:
        tmdb_id = (item.get("ProviderIds") or {}).get("Tmdb")
        if TMDB_KEY and is_movie and tmdb_id:
            x["stinger"] = tmdb_stinger(tmdb_id)
    except Exception as e:
        print(f"emby stinger failed: {e}", flush=True)
    fkey = fanart_api_key()
    if fkey:
        try:
            ids = item.get("ProviderIds") or {}
            if is_movie:
                fid = ids.get("Tmdb") or ids.get("Imdb")
                if fid:
                    x["fanartDoc"] = fanart_fetch("movies", fid, fkey)
            else:
                # fanart.tv keys TV on the show's TheTVDB id — an episode's
                # own Tvdb provider id is the episode, so look up the series.
                fid = None
                if item.get("SeriesId"):
                    got = emby_fetch_json(f"/Items?Ids={item['SeriesId']}"
                                          "&Fields=ProviderIds")
                    series = (got.get("Items") or [{}])[0]
                    fid = (series.get("ProviderIds") or {}).get("Tvdb")
                if fid:
                    x["fanartDoc"] = fanart_fetch("tv", fid, fkey)
        except Exception as e:
            log_warn(f"emby fanart lookup failed: {e}")
    try:
        x.update(emby_download_art(item))
    except Exception as e:
        log_warn(f"emby art failed: {e}")
    if key:
        # See _meta_cache above: cap, don't clear, so rotating titles stay cached.
        _cache_put(_emby_meta_cache, key, x)
    return x


def emby_enrich(item):
    """Fetch the fields /Sessions omits (genres, streams, ratings, overview)
    from /Items once per title, cached, and merge them in place."""
    key = item.get("Id")
    if not key:
        return
    if key not in _emby_enrich_cache:
        enriched = {}
        try:
            fields = ("Genres,MediaStreams,ProviderIds,Overview,"
                      "OfficialRating,CommunityRating,CriticRating")
            data = emby_fetch_json(f"/Items?Ids={key}&Fields={fields}")
            items = data.get("Items") if isinstance(data, dict) else None
            full = items[0] if items else {}
            for f in fields.split(","):
                if full.get(f) is None:
                    continue
                have = item.get(f)
                if isinstance(have, dict) and isinstance(full[f], dict):
                    # /Sessions can return a partial dict. A truthy-but-partial
                    # dict must still gain the missing keys; values already on
                    # the session win.
                    merged = {**full[f], **have}
                    if merged != have:
                        enriched[f] = merged
                elif not have:
                    enriched[f] = full[f]
        except Exception as e:
            print(f"emby enrich failed: {e}", flush=True)
        _emby_enrich_cache.clear()  # only ever need the current item
        _emby_enrich_cache[key] = enriched
    item.update(_emby_enrich_cache[key])


def emby_current_session():
    s = load_settings()
    host, key = emby_creds(settings=s)
    if not (host and key):
        return None   # not configured yet — the settings page can fix it live
    users = filter_set(s.get("plexUsers"), ENV_USERS)
    devices = filter_set(s.get("plexDevices"), ENV_DEVICES)
    block = filter_set(s.get("blockTags"), ENV_BLOCK_TAGS)
    sessions = emby_fetch_json("/Sessions")
    seen, allowed = [], []
    for session in sessions:
        item = session.get("NowPlayingItem")
        if not item or item.get("Type") not in ("Movie", "Episode"):
            continue
        u, d = emby_session_names(session)
        title = item.get("Name") or ""
        ok = (emby_session_allowed(session, users, devices)
              and not content_blocked(block, emby_item_terms(item)))
        seen.append({"user": u, "device": d, "title": title, "allowed": ok})
        if ok:
            allowed.append((session_sort_key(u, d, title), session))
    LAST_SESSIONS[:] = seen
    # Emby's /Sessions order tracks activity, so "the first allowed session"
    # flipped between two people's titles on an arbitrary poll. Sort, then let
    # the clock decide whose turn it is — same rotation as the Plex path.
    allowed.sort(key=lambda pair: pair[0])
    candidates = [session for _, session in allowed]
    match = rotate_pick(candidates, clamp_rotate(s.get("rotateSeconds")))
    if match is None:
        return None
    # /Sessions sometimes omits Genres, so the pre-filter may have passed a title
    # the enriched record reveals as blocked. Skip just that one and rotate on
    # through the rest, rather than dropping every innocent sibling session this
    # poll. Enrich lazily from the clock's pick; with no block set the first
    # candidate always passes, so this stays one enrich in the common case.
    start = candidates.index(match)
    match = None
    for i in range(len(candidates)):
        cand = candidates[(start + i) % len(candidates)]
        emby_enrich(cand.get("NowPlayingItem") or {})
        if not content_blocked(block, emby_item_terms(cand.get("NowPlayingItem") or {})):
            match = cand
            break
    if match is None:
        return None
    info = parse_emby_session(match, extras=emby_extras,
                              position=(candidates.index(match) + 1,
                                        len(candidates)))
    info.setdefault("session", {})["activeStreams"] = len(seen)
    return info




def bind(application_services):
    """Bind the small set of app-level config/logging callbacks used here."""
    globals().update({name: getattr(application_services, name)
                      for name in dir(application_services) if not name.startswith("__")})

def exports():
    return {name: value for name, value in globals().items()
            if (callable(value) or name.isupper()) and not name.startswith("_")}
