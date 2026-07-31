from dataclasses import dataclass
from enum import Enum


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ResourceIssue:
    severity: IssueSeverity
    code: str
    path: str
    message: str
    resource_kind: str = ""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    issues: tuple[ResourceIssue, ...] = ()

    @property
    def valid(self):
        return not any(issue.severity is IssueSeverity.ERROR for issue in self.issues)

    def messages(self, minimum=IssueSeverity.WARNING):
        ranks = {
            IssueSeverity.INFO: 0,
            IssueSeverity.WARNING: 1,
            IssueSeverity.ERROR: 2,
        }
        threshold = ranks[IssueSeverity(minimum)]
        return tuple(
            issue.message
            for issue in self.issues
            if ranks[issue.severity] >= threshold
        )
