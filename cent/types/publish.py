from typing import Optional

from cent.types.base import CentObject


class PublishObject(CentObject):
    """Publish result."""

    offset: Optional[int] = None
    """Offset of publication in history stream."""
    epoch: Optional[str] = None
    """Epoch of current stream."""
