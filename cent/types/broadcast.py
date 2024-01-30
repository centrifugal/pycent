from typing import List

from pydantic import Field

from cent.methods.base import Response
from cent.types.base import CentObject
from cent.types.publish import PublishObject


class BroadcastObject(CentObject):
    """Publish result."""

    responses: List[Response[PublishObject]] = Field(default_factory=list)
