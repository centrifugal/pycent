from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from cent.client.session.base_http import BaseHttpSession


class BaseHttpAsyncSession(BaseHttpSession, ABC):
    @abstractmethod
    async def close(self) -> None:
        """
        Close client session
        """

    @abstractmethod
    async def make_request(
        self,
        api_key: str,
        method: str,
        json_data: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> str:
        """
        Make request to Centrifugo HTTP API.
        """
