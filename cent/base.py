from abc import ABC, abstractmethod
from typing import TypeVar, Any, Generic, TYPE_CHECKING, ClassVar, Optional

from pydantic import BaseModel, ConfigDict


CentType = TypeVar("CentType", bound=Any)


class Error(BaseModel):
    code: int
    message: str


class Response(BaseModel, Generic[CentType]):
    error: Optional[Error] = None
    result: Optional[CentType] = None


class CentResult(BaseModel, ABC):
    model_config = ConfigDict(
        use_enum_values=True,
        extra="allow",
        validate_assignment=True,
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        defer_build=True,
    )


class CentRequest(BaseModel, Generic[CentType], ABC):
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


class NestedModel(BaseModel, ABC):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
