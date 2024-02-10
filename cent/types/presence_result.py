from typing import Dict


from cent.types.base import CentResult
from cent.types.client_info_result import ClientInfoResult


class PresenceResult(CentResult):
    """Presence result."""

    presence: Dict[str, ClientInfoResult]
    """Offset of publication in history stream."""
