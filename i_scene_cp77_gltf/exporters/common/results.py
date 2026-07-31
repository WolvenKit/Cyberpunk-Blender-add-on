from dataclasses import dataclass


@dataclass(frozen=True)
class ExportResult:
    filepath: str
    exported_items: int
    warnings: tuple[str, ...] = ()
    repairs: tuple[str, ...] = ()
