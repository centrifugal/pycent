from typing import Optional

from cent.types.base import CentObject


class Override(CentObject):
    """Override object."""

    presence: Optional[bool] = None
    """Override presence."""
    join_leave: Optional[bool] = None
    """Override join_leave."""
    force_push_join_leave: Optional[bool] = None
    """Override force_push_join_leave."""
    force_positioning: Optional[bool] = None
    """Override force_positioning."""
    force_recovery: Optional[bool] = None
    """Override force_recovery."""
