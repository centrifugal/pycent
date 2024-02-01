from pydantic import BaseModel


class BoolValue(BaseModel):
    """Bool value."""

    value: bool
    """Bool value."""
