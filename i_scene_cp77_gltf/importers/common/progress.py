from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)


class _NullProgressCounter:
    __slots__ = ()

    def advance(self, units: int = 1, *, detail: str = "", force: bool = False) -> None:
        return None

    def note(self, detail: str = "", *, force: bool = False) -> None:
        return None

    def finish(self, *, detail: str = "") -> None:
        return None


class NullImportProgress:
    __slots__ = ()

    def __enter__(self) -> NullImportProgress:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False

    def begin(self) -> None:
        return None

    def end(self) -> None:
        return None

    def set(self, value: float, message: str = "", *, force: bool = False) -> None:
        return None

    def span(
        self,
        start: float,
        end: float,
        *,
        label: str = "",
    ) -> NullImportProgress:
        return self

    def counter(self, label: str, total: int) -> _NullProgressCounter:
        return _NullProgressCounter()


NO_PROGRESS = NullImportProgress()


class BlenderImportProgress:
    __slots__ = (
        "_clock",
        "_label",
        "_last_emit_time",
        "_last_status",
        "_last_value",
        "_min_interval",
        "_min_percent",
        "_owns_lifecycle",
        "_progress_started",
        "_root",
        "_root_end",
        "_root_start",
        "_scope_labels",
        "_started",
        "_window_manager",
        "_workspace",
    )

    def __init__(
        self,
        context: Any = None,
        label: str = "Import",
        *,
        min_interval: float = 0.1,
        min_percent: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        _root: BlenderImportProgress | None = None,
        _root_start: float = 0.0,
        _root_end: float = 100.0,
        _scope_labels: tuple[str, ...] = (),
    ):
        if _root is None:
            self._root = self
            self._root_start = 0.0
            self._root_end = 100.0
            self._scope_labels = ()
            self._window_manager = getattr(context, "window_manager", None)
            self._workspace = getattr(context, "workspace", None)
            self._label = str(label or "Import")
            self._clock = clock
            self._min_interval = max(0.0, float(min_interval))
            self._min_percent = max(0.0, float(min_percent))
            self._started = False
            self._progress_started = False
            self._last_value = -1.0
            self._last_emit_time = float("-inf")
            self._last_status = ""
            self._owns_lifecycle = True
            return

        self._root = _root
        self._root_start = float(_root_start)
        self._root_end = float(_root_end)
        self._scope_labels = tuple(_scope_labels)
        self._window_manager = None
        self._workspace = None
        self._label = ""
        self._clock = clock
        self._min_interval = 0.0
        self._min_percent = 0.0
        self._started = False
        self._progress_started = False
        self._last_value = -1.0
        self._last_emit_time = float("-inf")
        self._last_status = ""
        self._owns_lifecycle = False

    def __enter__(self) -> BlenderImportProgress:
        self.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if self._owns_lifecycle:
            self.end()
        return False

    def begin(self) -> None:
        root = self._root
        if root._started:
            return
        root._last_value = -1.0
        root._last_emit_time = float("-inf")
        root._last_status = ""
        root._started = True
        progress_begin = getattr(root._window_manager, "progress_begin", None)
        if callable(progress_begin):
            try:
                progress_begin(0.0, 100.0)
                root._progress_started = True
            except (
                AttributeError,
                ReferenceError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("BlenderImportProgress.begin", type(error).__name__),
                    "begin: fell back after %s",
                    error,
                    exc_info=True,
                )
                root._progress_started = False
        root._emit(0.0, root._label, force=True)

    def end(self) -> None:
        if not self._owns_lifecycle:
            return
        root = self._root
        if not root._started:
            return
        try:
            root._emit(100.0, root._label, force=True)
        finally:
            if root._last_status:
                status_text_set = getattr(root._workspace, "status_text_set", None)
                if callable(status_text_set):
                    try:
                        status_text_set(None)
                    except (
                        AttributeError,
                        ReferenceError,
                        RuntimeError,
                        TypeError,
                        ValueError,
                    ) as error:
                        log_once(
                            _LOG,
                            "DEBUG",
                            ("BlenderImportProgress.end 1", type(error).__name__),
                            "end: fell back after %s",
                            error,
                            exc_info=True,
                        )
            if root._progress_started:
                progress_end = getattr(root._window_manager, "progress_end", None)
                if callable(progress_end):
                    try:
                        progress_end()
                    except (
                        AttributeError,
                        ReferenceError,
                        RuntimeError,
                        TypeError,
                        ValueError,
                    ) as error:
                        log_once(
                            _LOG,
                            "DEBUG",
                            ("BlenderImportProgress.end 2", type(error).__name__),
                            "end: fell back after %s",
                            error,
                            exc_info=True,
                        )
            root._started = False
            root._progress_started = False
            root._last_status = ""

    def set(self, value: float, message: str = "", *, force: bool = False) -> None:
        root = self._root
        if not root._started:
            root.begin()
        root_value = self._map_to_root(value)
        root._emit(root_value, self._status(message), force=force)

    def span(
        self,
        start: float,
        end: float,
        *,
        label: str = "",
    ) -> BlenderImportProgress:
        start_value = self._map_to_root(start)
        end_value = self._map_to_root(end)
        if end_value < start_value:
            start_value, end_value = end_value, start_value
        labels = self._scope_labels
        if label:
            labels = (*labels, str(label))
        return BlenderImportProgress(
            _root=self._root,
            _root_start=start_value,
            _root_end=end_value,
            _scope_labels=labels,
        )

    def counter(self, label: str, total: int) -> ImportProgressCounter:
        return ImportProgressCounter(self, label, total)

    def _map_to_root(self, value: float) -> float:
        value = max(0.0, min(100.0, float(value)))
        return self._root_start + (self._root_end - self._root_start) * (value / 100.0)

    def _status(self, message: str) -> str:
        parts = [self._root._label]
        parts.extend(label for label in self._scope_labels if label)
        if message:
            parts.append(str(message))
        return " — ".join(parts)

    def _emit(self, value: float, status: str, *, force: bool) -> None:
        root = self._root
        value = max(0.0, min(100.0, float(value)))
        if root._last_value >= 0.0:
            value = max(root._last_value, value)
        now = root._clock()
        value_delta = value - root._last_value
        elapsed = now - root._last_emit_time
        if (
            not force
            and root._last_value >= 0.0
            and value_delta < root._min_percent
            and elapsed < root._min_interval
        ):
            return

        if root._progress_started:
            progress_update = getattr(root._window_manager, "progress_update", None)
            if callable(progress_update):
                try:
                    progress_update(value)
                except (
                    AttributeError,
                    ReferenceError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as error:
                    log_once(
                        _LOG,
                        "DEBUG",
                        ("BlenderImportProgress._emit 1", type(error).__name__),
                        "emit: fell back after %s",
                        error,
                        exc_info=True,
                    )

        if status != root._last_status:
            status_text_set = getattr(root._workspace, "status_text_set", None)
            if callable(status_text_set):
                try:
                    status_text_set(status)
                except (
                    AttributeError,
                    ReferenceError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as error:
                    log_once(
                        _LOG,
                        "DEBUG",
                        ("BlenderImportProgress._emit 2", type(error).__name__),
                        "emit: fell back after %s",
                        error,
                        exc_info=True,
                    )

        root._last_value = value
        root._last_emit_time = now
        root._last_status = status


class ImportProgressCounter:
    __slots__ = ("current", "label", "progress", "total")

    def __init__(self, progress: BlenderImportProgress, label: str, total: int):
        self.progress = progress
        self.label = str(label or "Importing")
        self.total = max(0, int(total))
        self.current = 0
        self.note(force=True)

    def advance(self, units: int = 1, *, detail: str = "", force: bool = False) -> None:
        self.current = min(self.total, self.current + max(0, int(units)))
        self._update(detail=detail, force=force)

    def note(self, detail: str = "", *, force: bool = False) -> None:
        self._update(detail=detail, force=force)

    def finish(self, *, detail: str = "") -> None:
        self.current = self.total
        self._update(detail=detail, force=True)

    def _update(self, *, detail: str, force: bool) -> None:
        if self.total > 0:
            value = 100.0 * self.current / self.total
            message = f"{self.label} {self.current:,} / {self.total:,}"
        else:
            value = 100.0
            message = self.label
        if detail:
            message = f"{message} — {detail}"
        self.progress.set(value, message, force=force)
