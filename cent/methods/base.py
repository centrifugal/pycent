from abc import ABC, abstractmethod
from typing import TypeVar, Any, Generic, TYPE_CHECKING, ClassVar, Generator, Optional

from pydantic import BaseModel, ConfigDict

from cent.context_controller import ClientContextController

if TYPE_CHECKING:
    from cent.client.cent_client import CentClient

CentType = TypeVar("CentType", bound=Any)


class Error(BaseModel):
    code: int
    message: str


class Response(BaseModel, Generic[CentType]):
    error: Optional[Error] = None
    result: Optional[CentType] = None


class CentMethod(ClientContextController, BaseModel, Generic[CentType], ABC):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    if TYPE_CHECKING:
        __returning__: ClassVar[type]
        __api_method__: ClassVar[str]
    else:

        @property
        @abstractmethod
        def __returning__(self) -> type:
            pass

        @property
        @abstractmethod
        def __api_method__(self) -> str:
            pass

    async def emit(self, client: "CentClient") -> CentType:
        return await client(self)

    def __await__(self) -> Generator[Any, None, CentType]:
        client = self._client
        if not client:
            raise RuntimeError("CentMethod is not bound to a client")
        return self.emit(client).__await__()
