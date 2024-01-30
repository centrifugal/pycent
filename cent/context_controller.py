from typing import Optional, TYPE_CHECKING, Any

from pydantic import BaseModel, PrivateAttr

if TYPE_CHECKING:
    from cent.client import CentClient


class ClientContextController(BaseModel):
    _client: Optional["CentClient"] = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        self._client = __context.get("client") if __context else None

    def as_(self, client: Optional["CentClient"]) -> "ClientContextController":
        """
        Bind an object to a client instance.

        :param client: Client instance
        :return: self
        """
        self._client = client
        return self

    @property
    def client(self) -> Optional["CentClient"]:
        """
        Get client instance.

        :return: Client instance
        """
        return self._client
