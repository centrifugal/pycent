from abc import ABC

from pydantic import BaseModel, ConfigDict

from cent.context_controller import ClientContextController


class CentResult(ClientContextController, BaseModel, ABC):
    model_config = ConfigDict(
        use_enum_values=True,
        extra="allow",
        validate_assignment=True,
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        defer_build=True,
    )
