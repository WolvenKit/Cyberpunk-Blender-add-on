from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterator, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ImportResult(Generic[T]):
    """Structured importer result with fatal failures separated from warnings.

    ``failures`` is reserved for conditions that invalidate the complete
    operation. Recoverable content omissions belong in ``warnings``.
    """

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
