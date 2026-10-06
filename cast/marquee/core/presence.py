"""Presence eligibility and hysteresis for Cast destinations."""

from dataclasses import dataclass


@dataclass
class PresenceGate:
    """Debounce activation while allowing a short, explicit release grace."""
    activation_seconds: float = 15
    release_seconds: float = 30
    wanted: bool = False
    pending_since: float | None = None
    ineligible_since: float | None = None

    def update(self, eligible: bool, now: float, absolute_veto: bool = False) -> bool:
        if eligible:
            self.ineligible_since = None
            if self.wanted:
                self.pending_since = None
                return True
            if self.pending_since is None:
                self.pending_since = now
            if now - self.pending_since >= self.activation_seconds:
                self.wanted = True
                self.pending_since = None
            return self.wanted
        self.pending_since = None
        if absolute_veto:
            self.wanted = False
            self.ineligible_since = None
            return False
        if self.ineligible_since is None:
            self.ineligible_since = now
        if now - self.ineligible_since >= self.release_seconds:
            self.wanted = False
            self.ineligible_since = None
        return self.wanted


def bedroom_eligible(occupied, asleep_kris, asleep_magda, local_hour, local_minute):
    """Bedroom has three absolute gates: occupancy, sleep, and 22:00 cutoff."""
    return bool(occupied and not asleep_kris and not asleep_magda and
                (int(local_hour), int(local_minute)) < (22, 0))
