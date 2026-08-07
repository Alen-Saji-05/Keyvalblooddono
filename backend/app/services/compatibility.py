"""ABO and Rh compatibility for whole blood transfusion.

The brief specifies that a broadcast selects donors "matching blood group", and exact
match is the default. This module supports an opt-in widening, because exact match alone
turns down help that is medically usable: an O negative donor can give to anybody, and a
request for AB positive that is short of units while compatible donors sit unnotified is a
worse outcome than a slightly larger notification list.

Widening is opt-in rather than automatic so that the default behaviour is exactly what the
brief describes, and so an administrator broadcasting a request makes that call knowingly.
"""

from __future__ import annotations

from typing import Dict, FrozenSet

from ..models.enums import BloodGroup

# Keyed by the recipient's group, valued by the donor groups that may give to them.
# Direction matters and is easy to invert by accident: this maps recipient to acceptable
# donors, not donor to acceptable recipients.
COMPATIBLE_DONORS: Dict[BloodGroup, FrozenSet[BloodGroup]] = {
    BloodGroup.O_NEGATIVE: frozenset({BloodGroup.O_NEGATIVE}),
    BloodGroup.O_POSITIVE: frozenset({BloodGroup.O_NEGATIVE, BloodGroup.O_POSITIVE}),
    BloodGroup.A_NEGATIVE: frozenset({BloodGroup.O_NEGATIVE, BloodGroup.A_NEGATIVE}),
    BloodGroup.A_POSITIVE: frozenset(
        {
            BloodGroup.O_NEGATIVE,
            BloodGroup.O_POSITIVE,
            BloodGroup.A_NEGATIVE,
            BloodGroup.A_POSITIVE,
        }
    ),
    BloodGroup.B_NEGATIVE: frozenset({BloodGroup.O_NEGATIVE, BloodGroup.B_NEGATIVE}),
    BloodGroup.B_POSITIVE: frozenset(
        {
            BloodGroup.O_NEGATIVE,
            BloodGroup.O_POSITIVE,
            BloodGroup.B_NEGATIVE,
            BloodGroup.B_POSITIVE,
        }
    ),
    BloodGroup.AB_NEGATIVE: frozenset(
        {
            BloodGroup.O_NEGATIVE,
            BloodGroup.A_NEGATIVE,
            BloodGroup.B_NEGATIVE,
            BloodGroup.AB_NEGATIVE,
        }
    ),
    BloodGroup.AB_POSITIVE: frozenset(BloodGroup),
}


def acceptable_donor_groups(
    recipient: BloodGroup, include_compatible: bool = False
) -> FrozenSet[BloodGroup]:
    """The donor groups a broadcast should target for this recipient."""

    if not include_compatible:
        return frozenset({recipient})
    return COMPATIBLE_DONORS[recipient]
