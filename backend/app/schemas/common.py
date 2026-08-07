"""Pagination and other cross-resource schema pieces."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from pydantic import Field

from .base import ApiModel


class PageParams(ApiModel):
    """Query parameters for a paginated list.

    Every list endpoint is paginated, including the ones that look small today. The donor
    directory is the obvious case - a real network has tens of thousands of donors and an
    unbounded list endpoint is both a slow query and an easy way to export the entire
    contact database in one request.

    ``page_size`` is capped rather than merely defaulted, so a caller cannot ask for
    everything by passing a large number.
    """

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginated(items: Sequence[Any], total: int, params: PageParams) -> Dict[str, Any]:
    """Build the envelope every list endpoint returns.

    ``total`` is the count before the limit, so the client can render the page count
    without a second request, and ``pages`` is computed here rather than left to each
    caller to get the rounding right.
    """

    pages = (total + params.page_size - 1) // params.page_size if total else 0
    return {
        "items": list(items),
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": pages,
    }
