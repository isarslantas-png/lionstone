"""Rights model for presets, brand kits and team roles.

Lionstone is free: every tier label (free / pro / studio) is unlocked for everyone. The tier
names stay in preset metadata as a grouping (`lionstone fx list --tier studio`), and the
checks stay in compile/render/studio code so the model keeps working and tests can still
build a restricted entitlement with ``for_tier``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

TIER_ORDER = ("free", "pro", "studio")


class EntitlementError(PermissionError):
    pass


@dataclass(frozen=True)
class Entitlement:
    tiers: frozenset[str] = frozenset(TIER_ORDER)
    user: str = "local"
    team: str | None = None
    features: tuple[str, ...] = field(default_factory=tuple)

    @property
    def level(self) -> str:
        return max(self.tiers, key=TIER_ORDER.index)

    def allows(self, tier: str) -> bool:
        return tier in self.tiers

    def require(self, tier: str, what: str) -> None:
        if not self.allows(tier):
            raise EntitlementError(f"{what} is not available in this entitlement ({self.level}).")


def current() -> Entitlement:
    """Everyone gets every tier. The user name only matters for team roles."""
    from ..identity import member_email
    return Entitlement(user=member_email() or "local", team=os.environ.get("LIONSTONE_TEAM") or None)


def for_tier(tier: str, user: str = "test@example.com", team: str | None = None) -> Entitlement:
    """Explicit, restricted entitlement (tests, server-side checks)."""
    idx = TIER_ORDER.index(tier)
    return Entitlement(frozenset(TIER_ORDER[: idx + 1]), user=user, team=team)
