from pydantic import BaseModel


class Disconnect(BaseModel):
    """Disconnect result."""

    code: int
    """Disconnect code."""
    reason: str
    """Disconnect reason."""
