from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from cent.client.session.base_http import BaseHttpSession


class BaseHttpSyncSession(BaseHttpSession, ABC):
    @abstractmethod
    def close(self) -> None:
        """
        Close client session
        """

    @abstractmethod
    def make_request(
        self,
        api_key: str,
        method: str,
        json_data: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> str:
        """
        Make request to Centrifugo HTTP API.
        """
