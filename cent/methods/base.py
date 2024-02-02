from abc import ABC, abstractmethod
from typing import TypeVar, Any, Generic, TYPE_CHECKING, ClassVar, Optional

from pydantic import BaseModel, ConfigDict

from cent.context_controller import ClientContextController

CentType = TypeVar("CentType", bound=Any)


class Error(BaseModel):
    code: int
    message: str


class Response(BaseModel, Generic[CentType]):
    error: Optional[Error] = None
    result: Optional[CentType] = None


class CentMethod(
    ClientContextController,
    BaseModel,
    Generic[CentType],
    ABC,
):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    if TYPE_CHECKING:
        __returning__: ClassVar[type]
        __api_method__: ClassVar[str]

        __grpc_method__: ClassVar[type]
    else:

        @property
        @abstractmethod
        def __returning__(self) -> type:
            pass

        @property
        @abstractmethod
        def __api_method__(self) -> str:
            pass

        @property
        @abstractmethod
        def __grpc_method__(self) -> type:
            pass


class NestedModel(ClientContextController, BaseModel, ABC):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
    if TYPE_CHECKING:
        __grpc_method__: ClassVar[type]
    else:

        @property
        @abstractmethod
        def __grpc_method__(self) -> type:
            pass
