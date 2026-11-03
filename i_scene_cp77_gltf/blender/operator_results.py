from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..core.log import get_logger
from ..core.notifications import report


@dataclass(frozen=True, slots=True)
class OperationResult:
    ok: bool
    message: str = ""
    level: str = "INFO"
    warnings: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    error: BaseException | None = None

    @property
    def blender_status(self) -> set[str]:
        return {"FINISHED"} if self.ok else {"CANCELLED"}

    @classmethod
    def finished(cls, message: str = "", level: str = "INFO", warnings=(), **details):
        return cls(True, message, level, tuple(warnings), details)

    @classmethod
    def cancelled(
        cls,
        message: str = "",
        level: str = "ERROR",
        *,
        error: BaseException | None = None,
        **details,
    ):
        return cls(False, message, level, details=details, error=error)


def _operator_logger(operator):
    return get_logger(type(operator).__module__)


def finish_operator(operator, result):
    logger = _operator_logger(operator)
    if result.message:
        report(
            operator,
            result.level,
            result.message,
            error=result.error,
            logger=logger,
            stacklevel=2,
        )
    for warning in result.warnings:
        report(operator, "WARNING", warning, logger=logger, stacklevel=2)
    return result.blender_status


def require_finished(result, operation):
    """Raise RuntimeError("<operation> was cancelled") unless a Blender operator call returned FINISHED"""
    if "FINISHED" not in result:
        raise RuntimeError(f"{operation} was cancelled")


def execute_operation(operator, label, operation, *args, **kwargs):
    """Run one service call for an operator, reporting its result or the error it raised"""
    try:
        result = operation(*args, **kwargs)
    except Exception as error:
        # Logged once, with the traceback, by the report.
        report(
            operator,
            "ERROR",
            f"{label} failed: {error}",
            error=error,
            logger=_operator_logger(operator),
            stacklevel=2,
        )
        return {"CANCELLED"}
    return finish_operator(operator, result)
