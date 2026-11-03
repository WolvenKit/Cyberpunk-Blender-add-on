from __future__ import annotations

<<<<<<< Updated upstream
from dataclasses import dataclass
from typing import Generic, Iterator, TypeVar

=======
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar
>>>>>>> Stashed changes

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ImportResult(Generic[T]):
<<<<<<< Updated upstream
    """Structured importer result with fatal failures separated from warnings.

    ``failures`` is reserved for conditions that invalidate the complete
    operation. Recoverable content omissions belong in ``warnings``.
    """
=======
    """Structured importer result with fatal failures separated from warnings"""
>>>>>>> Stashed changes

    created_items: tuple[T, ...] = ()
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    label: str = ""

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def blender_status(self) -> set[str]:
        return {"FINISHED"} if self.ok else {"CANCELLED"}

    def __bool__(self) -> bool:
        return self.ok

    def __iter__(self) -> Iterator[T]:
        return iter(self.created_items)

    def __len__(self) -> int:
        return len(self.created_items)

    def __getitem__(self, index):
        return self.created_items[index]


def unique_messages(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))
<<<<<<< Updated upstream
=======


def summarize_messages(values, *, root: str = "", limit: int = 8) -> str:
    """Bounded issue summary with paths shown relative to root"""
    messages = unique_messages(values)
    if not messages:
        return ""
    prefixes = ()
    if root:
        normalized = root.replace("\\", "/").rstrip("/") + "/"
        prefixes = tuple(
            dict.fromkeys(
                (
                    "//?/" + normalized,
                    "\\\\?\\" + normalized.replace("/", "\\"),
                    normalized,
                    normalized.replace("/", "\\"),
                )
            )
        )

    def shorten(message):
        for prefix in prefixes:
            message = message.replace(prefix, "")
        return message

    lines = [f"{len(messages)} issue(s) during import:"]
    lines.extend(f"  {shorten(message)}" for message in messages[:limit])
    if len(messages) > limit:
        lines.append(f"  ... and {len(messages) - limit} more in the IO Suite log")
    return "\n".join(lines)
>>>>>>> Stashed changes
