from typing import List

from pydantic import Field

from cent.methods.base import Response
from cent.types.base import CentResult
from cent.types.publish_result import PublishResult


class BroadcastResult(CentResult):
    """Publish result."""

    responses: List[Response[PublishResult]] = Field(default_factory=list)
    """Responses for each individual publish (with possible error and publish result)."""
