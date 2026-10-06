"""Pure Home Assistant presence predicates used by the Marquee bridge."""


def bedroom_eligible(occupied, asleep_kris, asleep_magda, hour, minute):
    return bool(occupied and not asleep_kris and not asleep_magda and
                (int(hour), int(minute)) < (22, 0))
