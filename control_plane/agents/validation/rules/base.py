"""UCVE Agent Builder - Base Validation Rule Interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from control_plane.agents.models.agent_config import AgentConfig


class ValidationErrorItem:
    """Individual validation failure detail."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code, "message": self.message, "field": self.field}

    def __repr__(self) -> str:
        return f"ValidationErrorItem({self.code}: {self.message})"


class BaseValidationRule(ABC):
    """Abstract base class for all agent config validation rules."""

    @abstractmethod
    def validate(self, config: AgentConfig) -> list[ValidationErrorItem]:
        """Validate the configuration and return any error items."""
        raise NotImplementedError
