import contextlib
import contextvars
import copy
import linecache
import logging
import queue
import sys
import threading
import time
import traceback
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "i_scene_cp77_gltf"
TRACE = 5
logging.addLevelName(TRACE, "TRACE")
_DEFAULT_LEVEL = "INFO"
_MAX_LOG_BYTES = 8 * 1024 * 1024
_BACKUP_COUNT = 4
_FILE_QUEUE_CAPACITY = 2048
_FILE_QUEUE_IMPORTANT_RESERVE = 64
_FILE_LISTENER_STOP_TIMEOUT = 0.5
_FILE_QUEUE_SHUTDOWN_IMPORTANT_CAPACITY = 512
_FILE_QUEUE_SHUTDOWN_TRIM_THRESHOLD = 256
_FILE_QUEUE_SHUTDOWN_LOW_PRIORITY_RETAIN = 32

_CONTEXT = contextvars.ContextVar("cp77_log_context", default=())
_CONFIG_LOCK = threading.RLock()
_ONCE_LOCK = threading.RLock()
_ONCE_KEYS = set()
_LAST_MESSAGES = {}
_ONCE_LIMIT = 4096
_LEVEL_NAMES = {
    "TRACE": TRACE,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    # Blender's report types.
    "OPERATOR": logging.INFO,
    "PROPERTY": logging.INFO,
    "ERROR_OUT_OF_MEMORY": logging.ERROR,
    # A refusal (wrong selection, missing input) is not a failure.
    "ERROR_INVALID_INPUT": logging.INFO,
    "ERROR_INVALID_CONTEXT": logging.INFO,
}
_CURRENT_LOG_PATH = globals().get("_CURRENT_LOG_PATH")
_FILE_LISTENER = globals().get("_FILE_LISTENER")
_FILE_HANDLER = globals().get("_FILE_HANDLER")
_ORPHANED_FILE_PIPELINES = globals().get("_ORPHANED_FILE_PIPELINES", [])

_BASE_LOGGER = logging.getLogger(LOGGER_NAME)
if not any(
    isinstance(handler, logging.NullHandler) for handler in _BASE_LOGGER.handlers
):
    _BASE_LOGGER.addHandler(logging.NullHandler())


def _exception_source_span(frame_summary):
    filename = str(getattr(frame_summary, "filename", "") or "")
    start = int(getattr(frame_summary, "lineno", 0) or 0)
    end = int(getattr(frame_summary, "end_lineno", 0) or start)
    if not filename or start <= 0 or filename.startswith("<"):
        return ()
    end = max(end, start)
    try:
        linecache.checkcache(filename)
        source = linecache.getlines(filename)
    except Exception:
        source = ()
    if not source or start > len(source):
        text = str(getattr(frame_summary, "line", "") or "").rstrip()
        return ((start, text),) if text else ()
    end = min(end, len(source))
    return tuple(
        (line_number, source[line_number - 1].rstrip("\r\n"))
        for line_number in range(start, end + 1)
    )


def _format_traceback_frames(traceback_obj):
    if traceback_obj is None:
        return []
    lines = ["Traceback (most recent call last):"]
    try:
        frames = traceback.extract_tb(traceback_obj)
    except Exception:
        frames = ()
    if not frames:
        return lines
    for frame in frames:
        lines.append(f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}')
        span = _exception_source_span(frame)
        if span:
            width = max(4, len(str(span[-1][0])))
            for line_number, source_line in span:
                lines.append(f"    {line_number:>{width}} | {source_line}")
    return lines


def _format_exception_only_complete(exc_type, exc):
    if isinstance(exc, AttributeError):
        # Attribute suggestions call dir() on exc.obj, which can be removed RNA.
        name = exc_type.__qualname__
        if exc_type.__module__ not in {"builtins", "__main__"}:
            name = f"{exc_type.__module__}.{name}"
        return [f"{name}: {exc}", *getattr(exc, "__notes__", ())]
    try:
        rendered = "".join(traceback.format_exception_only(exc_type, exc)).rstrip("\n")
    except Exception:
        rendered = f"{getattr(exc_type, '__name__', str(exc_type))}: {exc}"
    return rendered.splitlines() or [str(exc)]


def _format_exception_node(exc_type, exc, traceback_obj, ancestry):
    identity = id(exc)
    if identity in ancestry:
        return [f"<exception cycle: {type(exc).__name__}: {exc}>"]
    ancestry = set(ancestry)
    ancestry.add(identity)

    lines = []
    cause = getattr(exc, "__cause__", None)
    context = getattr(exc, "__context__", None)
    if cause is not None:
        lines.extend(
            _format_exception_node(type(cause), cause, cause.__traceback__, ancestry)
        )
        lines.extend(
            (
                "",
                "The above exception was the direct cause of the following exception:",
                "",
            )
        )
    elif context is not None and not bool(getattr(exc, "__suppress_context__", False)):
        lines.extend(
            _format_exception_node(
                type(context), context, context.__traceback__, ancestry
            )
        )
        lines.extend(
            (
                "",
                "During handling of the above exception, another exception occurred:",
                "",
            )
        )

    lines.extend(_format_traceback_frames(traceback_obj))
    lines.extend(_format_exception_only_complete(exc_type, exc))

    try:
        group_type = BaseExceptionGroup
    except NameError:
        group_type = None
    if group_type is not None and isinstance(exc, group_type):
        children = tuple(getattr(exc, "exceptions", ()) or ())
        for index, child in enumerate(children, 1):
            lines.append("")
            lines.append(
                f"ExceptionGroup item {index}/{len(children)} ({type(child).__name__}):"
            )
            child_lines = _format_exception_node(
                type(child), child, child.__traceback__, ancestry
            )
            lines.extend(f"  {line}" if line else "" for line in child_lines)
    return lines


def _format_exception_complete(exc_info):
    try:
        exc_type, exc, traceback_obj = exc_info
    except Exception:
        return "<exception traceback unavailable>"
    if exc_type is None or exc is None:
        return "<exception traceback unavailable>"
    try:
        return "\n".join(_format_exception_node(exc_type, exc, traceback_obj, set()))
    except Exception:
        try:
            return "".join(traceback.format_tb(traceback_obj)) + "\n".join(
                _format_exception_only_complete(exc_type, exc)
            )
        except Exception:
            return f"{getattr(exc_type, '__name__', str(exc_type))}: {exc}"


def _record_has_exception(record):
    return bool(getattr(record, "exc_info", None) or getattr(record, "exc_text", None))


def _record_is_important(record):
    return bool(
        getattr(record, "levelno", logging.NOTSET) >= logging.WARNING
        or _record_has_exception(record)
    )


def _record_priority(record):
    if _record_has_exception(record):
        return 4
    level = getattr(record, "levelno", logging.NOTSET)
    if level >= logging.ERROR:
        return 3
    if level >= logging.WARNING:
        return 2
    return 1


class _LocalQueueHandler(QueueHandler):
    def __init__(self, record_queue):
        super().__init__(record_queue)
        self._cp77_dropped_low_priority = 0
        self._cp77_dropped_important = 0
        self._cp77_dropped_exceptions = 0
        self._cp77_drop_lock = threading.Lock()
        self._cp77_shutdown_lock = threading.Lock()
        self._cp77_shutdown_records = []
        self._cp77_stopping = False

    def prepare(self, record):
        queued = copy.copy(record)
        try:
            queued.msg = record.getMessage()
        except Exception as error:
            queued.msg = f"<unformattable log message: {type(error).__name__}: {error}>"
        queued.args = None
        queued.message = str(queued.msg)
        if queued.exc_info:
            try:
                queued.exc_text = _format_exception_complete(queued.exc_info)
            except Exception:
                queued.exc_text = "<exception traceback unavailable>"
            queued.exc_info = None
        return queued

    def _record_drop(self, record=None, count=1):
        if count <= 0:
            return
        with self._cp77_drop_lock:
            if _record_has_exception(record):
                self._cp77_dropped_exceptions += int(count)
            elif _record_is_important(record):
                self._cp77_dropped_important += int(count)
            else:
                self._cp77_dropped_low_priority += int(count)

    def clear_drop_counts(self):
        with self._cp77_drop_lock:
            counts = (
                self._cp77_dropped_low_priority,
                self._cp77_dropped_important,
                self._cp77_dropped_exceptions,
            )
            self._cp77_dropped_low_priority = 0
            self._cp77_dropped_important = 0
            self._cp77_dropped_exceptions = 0
            return counts

    def begin_shutdown(self):
        self._cp77_stopping = True

    def take_shutdown_records(self):
        with self._cp77_shutdown_lock:
            records = tuple(self._cp77_shutdown_records)
            self._cp77_shutdown_records.clear()
            return records

    def _retain_shutdown_record(self, record):
        if not _record_is_important(record):
            self._record_drop(record)
            return
        with self._cp77_shutdown_lock:
            records = self._cp77_shutdown_records
            if len(records) < _FILE_QUEUE_SHUTDOWN_IMPORTANT_CAPACITY:
                records.append(record)
                return
            incoming_priority = _record_priority(record)
            candidate = next(
                (
                    index
                    for index, existing in enumerate(records)
                    if _record_priority(existing) < incoming_priority
                ),
                None,
            )
            if candidate is None and incoming_priority >= 4:
                candidate = next(
                    (
                        index
                        for index, existing in enumerate(records)
                        if _record_priority(existing) == incoming_priority
                    ),
                    None,
                )
            if candidate is None:
                self._record_drop(record)
                return
            evicted = records[candidate]
            records[candidate] = record
            self._record_drop(evicted)

    def _low_priority_limit_reached(self):
        maxsize = int(getattr(self.queue, "maxsize", 0) or 0)
        if maxsize <= 0:
            return False
        reserve = min(
            _FILE_QUEUE_IMPORTANT_RESERVE,
            max(1, maxsize // 8),
        )
        return self.queue.qsize() >= maxsize - reserve

    def _enqueue_important(self, record):
        try:
            self.queue.put_nowait(record)
            return True
        except queue.Full:
            pass
        try:
            evicted = self.queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.queue.task_done()
            self._record_drop(evicted)
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            return False
        return True

    def enqueue(self, record):
        if self._cp77_stopping:
            self._retain_shutdown_record(record)
            return

        if not _record_is_important(record):
            if self._low_priority_limit_reached():
                self._record_drop(record)
                return
            try:
                self.queue.put_nowait(record)
            except queue.Full:
                self._record_drop(record)
            return

        if not self._enqueue_important(record):
            self._record_drop(record)


class _LocalQueueListener(QueueListener):
    def enqueue_sentinel(self):
        self.queue.put_nowait(self._sentinel)

    def stop_bounded(self, timeout=_FILE_LISTENER_STOP_TIMEOUT):
        thread = self._thread
        if thread is None:
            return False
        try:
            self.enqueue_sentinel()
        except queue.Full:
            return True
        thread.join(max(0.0, float(timeout)))
        alive = thread.is_alive()
        if not alive:
            self._thread = None
        return alive


def _stop_listener_pipeline(listener, timeout=_FILE_LISTENER_STOP_TIMEOUT):
    thread = getattr(listener, "_thread", None) if listener is not None else None
    if listener is None or thread is None:
        return False
    stop_bounded = getattr(listener, "stop_bounded", None)
    if callable(stop_bounded):
        try:
            return bool(stop_bounded(timeout))
        except Exception:
            return bool(thread.is_alive())
    try:
        listener.enqueue_sentinel()
    except Exception:
        return bool(thread.is_alive())
    thread.join(max(0.0, float(timeout)))
    alive = thread.is_alive()
    if not alive:
        try:
            listener._thread = None
        except Exception:
            pass
    return alive


def _drain_queue(record_queue):
    pending = []
    task_done = getattr(record_queue, "task_done", None)
    while True:
        try:
            record = record_queue.get_nowait()
        except queue.Empty:
            break
        if callable(task_done):
            task_done()
        if record is not None:
            pending.append(record)
    return pending


def _select_shutdown_records(records):
    records = list(records)
    if len(records) <= _FILE_QUEUE_SHUTDOWN_TRIM_THRESHOLD:
        return records, 0

    low_priority_indexes = [
        index
        for index, record in enumerate(records)
        if not _record_is_important(record)
    ]
    retain = max(0, int(_FILE_QUEUE_SHUTDOWN_LOW_PRIORITY_RETAIN))
    keep_low_priority = set(low_priority_indexes[-retain:]) if retain > 0 else set()
    retained = [
        record
        for index, record in enumerate(records)
        if index not in low_priority_indexes or index in keep_low_priority
    ]
    return retained, len(records) - len(retained)


def _fit_shutdown_records(records, capacity):
    records = list(records)
    if capacity <= 0:
        return [], records
    if len(records) <= capacity:
        return records, []
    ranked = sorted(
        enumerate(records),
        key=lambda item: (_record_priority(item[1]), item[0]),
        reverse=True,
    )[:capacity]
    keep = {index for index, _record in ranked}
    retained = [record for index, record in enumerate(records) if index in keep]
    dropped = [record for index, record in enumerate(records) if index not in keep]
    return retained, dropped


def _drop_summary_record(low_priority, important, exceptions):
    if low_priority <= 0 and important <= 0 and exceptions <= 0:
        return None
    record = logging.LogRecord(
        f"{LOGGER_NAME}.log",
        logging.WARNING,
        __file__,
        0,
        "File logging dropped %d diagnostic, %d warning/error, and %d exception-trace record(s) during queue saturation or shutdown",
        (low_priority, important, exceptions),
        None,
    )
    record.cp77_module = "log"
    record.cp77_context = ""
    return record


def _close_file_handler(handler):
    if handler is None:
        return
    try:
        handler.flush()
        handler.close()
    except Exception:
        pass


def _remember_orphaned_pipeline(listener, handler, path=""):
    identity = id(listener)
    if any(id(item[0]) == identity for item in _ORPHANED_FILE_PIPELINES):
        return
    _ORPHANED_FILE_PIPELINES.append((listener, handler, str(path or "")))


def _reap_orphaned_pipelines():
    retained = []
    for listener, handler, path in tuple(_ORPHANED_FILE_PIPELINES):
        thread = getattr(listener, "_thread", None)
        if thread is not None and thread.is_alive():
            retained.append((listener, handler, path))
            continue
        _close_file_handler(handler)
    _ORPHANED_FILE_PIPELINES[:] = retained
    return len(retained)


def _has_live_orphaned_pipeline():
    _reap_orphaned_pipelines()
    return bool(_ORPHANED_FILE_PIPELINES)


def _stop_file_listener(logger=None):
    global _FILE_LISTENER, _FILE_HANDLER
    logger = logger or logging.getLogger(LOGGER_NAME)
    _reap_orphaned_pipelines()
    seen_listeners = set()
    for queue_handler in tuple(logger.handlers):
        listener = getattr(queue_handler, "_cp77_listener", None)
        if listener is None:
            continue
        handler = queue_handler._cp77_file_handler
        queue_handler.begin_shutdown()
        logger.removeHandler(queue_handler)
        try:
            queue_handler.acquire()
            queue_handler.release()
        except Exception:
            pass

        pending = _drain_queue(queue_handler.queue)
        pending.extend(queue_handler.take_shutdown_records())
        retained, trimmed = _select_shutdown_records(pending)

        low_dropped, important_dropped, exception_dropped = (
            queue_handler.clear_drop_counts()
        )
        low_dropped += trimmed

        maxsize = int(getattr(queue_handler.queue, "maxsize", 0) or 0)
        if maxsize > 0:
            summary_slots = (
                1 if (low_dropped or important_dropped or exception_dropped) else 0
            )
            retained, overflow_records = _fit_shutdown_records(
                retained,
                max(0, maxsize - 1 - summary_slots),
            )
            for record in overflow_records:
                if _record_has_exception(record):
                    exception_dropped += 1
                elif _record_is_important(record):
                    important_dropped += 1
                else:
                    low_dropped += 1
        for record in retained:
            try:
                queue_handler.queue.put_nowait(record)
            except queue.Full:
                if _record_has_exception(record):
                    exception_dropped += 1
                elif _record_is_important(record):
                    important_dropped += 1
                else:
                    low_dropped += 1
        summary = _drop_summary_record(
            low_dropped, important_dropped, exception_dropped
        )
        if summary is not None:
            try:
                queue_handler.queue.put_nowait(summary)
            except queue.Full:
                pass

        seen_listeners.add(id(listener))
        thread_alive = _stop_listener_pipeline(listener)
        if handler is not None:
            if thread_alive:
                _remember_orphaned_pipeline(
                    listener,
                    handler,
                    queue_handler._cp77_log_path,
                )
            else:
                _close_file_handler(handler)
        try:
            queue_handler.close()
        except Exception:
            pass

    listener = _FILE_LISTENER
    handler = _FILE_HANDLER
    _FILE_LISTENER = None
    _FILE_HANDLER = None
    if listener is not None and id(listener) not in seen_listeners:
        thread_alive = _stop_listener_pipeline(listener)
        if handler is not None:
            if thread_alive:
                _remember_orphaned_pipeline(listener, handler, _CURRENT_LOG_PATH or "")
            else:
                _close_file_handler(handler)
    _reap_orphaned_pipelines()


class _ContextFilter(logging.Filter):
    def filter(self, record):
        name = record.name
        prefix = LOGGER_NAME + "."
        record.cp77_module = name.removeprefix(prefix)
        fields = _CONTEXT.get()
        if fields:

            def _format_value(value):
                text = str(value)
                if any(char.isspace() for char in text) or "=" in text:
                    return repr(text)
                return text

            record.cp77_context = (
                " ["
                + " ".join(f"{key}={_format_value(value)}" for key, value in fields)
                + "]"
            )
        else:
            record.cp77_context = ""
        return True


class _ConsoleFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            "[CP77][%(levelname)s][%(cp77_module)s] %(message)s%(cp77_context)s"
        )

    def format(self, record):
        console_record = copy.copy(record)
        console_record.exc_info = None
        console_record.exc_text = None
        console_record.stack_info = None
        return super().format(console_record)


class _FileFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            "%(asctime)s.%(msecs)03d %(levelname)-8s "
            "%(name)s:%(lineno)d %(message)s%(cp77_context)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def formatException(self, exc_info):
        return _format_exception_complete(exc_info)


class _Operation:
    def __init__(self, logger, label, level, fields):
        self._logger = logger
        self._label = str(label)
        self._level = level
        self._fields = fields
        self._context = None
        self._started = 0.0

    def __enter__(self):
        self._context = log_context(**self._fields)
        self._context.__enter__()
        self._started = time.perf_counter()
        self._logger.log(self._level, "Beginning %s", self._label, stacklevel=2)
        return self

    def __exit__(self, exc_type, exc, exc_traceback):
        elapsed = time.perf_counter() - self._started
        try:
            if exc_type is None:
                self._logger.log(
                    self._level,
                    "Finished %s in %.3f seconds",
                    self._label,
                    elapsed,
                    stacklevel=2,
                )
            else:
                # The caller handles or reports the exception; this only records the elapsed time.
                self._logger.debug(
                    "%s failed after %.3f seconds",
                    self._label,
                    elapsed,
                    exc_info=(exc_type, exc, exc_traceback),
                    stacklevel=2,
                )
        finally:
            self._context.__exit__(exc_type, exc, exc_traceback)
        return False


def get_logger(name=None):
    if not name:
        return logging.getLogger(LOGGER_NAME)
    name = str(name)
    if name == LOGGER_NAME or name.startswith(LOGGER_NAME + "."):
        return logging.getLogger(name)
    extension_marker = "." + LOGGER_NAME
    marker_index = name.find(extension_marker)
    if marker_index >= 0:
        suffix = name[marker_index + len(extension_marker) :].lstrip(".")
        normalized = LOGGER_NAME if not suffix else f"{LOGGER_NAME}.{suffix}"
        return logging.getLogger(normalized)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def level_from_name(name):
    """The level of a logging level name or a Blender report type"""
    if isinstance(name, int):
        return name
    level = _LEVEL_NAMES.get(str(name).upper())
    if level is None:
        raise ValueError(f"Unsupported CP77 log level: {name!r}")
    return level


class RotatingLogFile(RotatingFileHandler):
    """Rotates by size, waiting while another process holds the log open"""

    def __init__(self, *args, retry_seconds=60.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._retry_seconds = float(retry_seconds)
        self._retry_at = 0.0

    def shouldRollover(self, record):
        if time.monotonic() < self._retry_at:
            return False
        return super().shouldRollover(record)

    def doRollover(self):
        try:
            super().doRollover()
        except OSError:
            self._retry_at = time.monotonic() + self._retry_seconds
            if self.stream is None:
                self.stream = self._open()


def _default_log_directory():
    reason = None
    try:
        from .addon_identity import user_config_dir

        configured = user_config_dir("logs")
        if configured:
            return Path(configured), None
    except Exception as error:
        reason = error
    return Path.home() / ".cp77_io_suite" / "logs", reason


def configure_logging(
    *,
    console_level=_DEFAULT_LEVEL,
    console=True,
    file=True,
    log_directory=None,
):
    """The console shows console_level and the file records one step more"""
    global _CURRENT_LOG_PATH, _FILE_LISTENER, _FILE_HANDLER
    console_level_value = level_from_name(console_level)
    file_level_value = TRACE if console_level_value <= logging.DEBUG else logging.DEBUG
    with _CONFIG_LOCK:
        logger = logging.getLogger(LOGGER_NAME)
        _stop_file_listener(logger)
        clear_once_messages()
        file_blocked = bool(file and _has_live_orphaned_pipeline())
        file_enabled = bool(file and not file_blocked)
        if file_enabled:
            logger.setLevel(min(file_level_value, console_level_value))
        elif console:
            logger.setLevel(console_level_value)
        else:
            logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False

        for handler in tuple(logger.handlers):
            if getattr(handler, "_cp77_owned", False):
                logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass

        context_filter = _ContextFilter()
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler._cp77_owned = True
            console_handler.setLevel(console_level_value)
            console_handler.addFilter(context_filter)
            console_handler.setFormatter(_ConsoleFormatter())
            logger.addHandler(console_handler)

        _CURRENT_LOG_PATH = None
        if file_blocked:
            logger.warning(
                "File logging is temporarily disabled because the previous log writer is still shutting down"
            )
        if file_enabled:
            try:
                fallback_reason = None
                if log_directory:
                    directory = Path(log_directory)
                else:
                    directory, fallback_reason = _default_log_directory()
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / "cp77_io_suite.log"
                file_handler = RotatingLogFile(
                    path,
                    maxBytes=_MAX_LOG_BYTES,
                    backupCount=_BACKUP_COUNT,
                    encoding="utf-8",
                    delay=True,
                )
                file_handler._cp77_owned = True
                file_handler.setLevel(file_level_value)
                file_handler.setFormatter(_FileFormatter())

                record_queue = queue.Queue(maxsize=_FILE_QUEUE_CAPACITY)
                queue_handler = _LocalQueueHandler(record_queue)
                queue_handler._cp77_owned = True
                queue_handler.setLevel(file_level_value)
                queue_handler.addFilter(context_filter)
                logger.addHandler(queue_handler)

                listener = _LocalQueueListener(
                    record_queue,
                    file_handler,
                    respect_handler_level=True,
                )
                queue_handler._cp77_listener = listener
                queue_handler._cp77_file_handler = file_handler
                queue_handler._cp77_log_path = str(path)
                try:
                    listener.start()
                except RuntimeError as error:
                    logger.removeHandler(queue_handler)
                    queue_handler.close()
                    file_handler.close()
                    if console:
                        logger.setLevel(console_level_value)
                    else:
                        logger.setLevel(logging.CRITICAL + 1)
                    logger.warning("File logging could not be started: %s", error)
                else:
                    _FILE_LISTENER = listener
                    _FILE_HANDLER = file_handler
                    _CURRENT_LOG_PATH = path
                    if fallback_reason is not None:
                        logger.warning(
                            "The add-on's log folder is unavailable; logging to %s",
                            directory,
                            exc_info=fallback_reason,
                        )
            except OSError as error:
                if console:
                    logger.setLevel(console_level_value)
                else:
                    logger.setLevel(logging.CRITICAL + 1)
                logger.warning("File logging is unavailable: %s", error)

        return logger


def configure_from_preferences(context=None):
    level = _DEFAULT_LEVEL
    write_file = True
    try:
        from .addon_identity import get_addon_preferences

        preferences = get_addon_preferences(context, required=False)
        if preferences is not None:
            level = getattr(preferences, "log_level", _DEFAULT_LEVEL)
            write_file = bool(getattr(preferences, "log_to_file", True))
    except Exception:
        get_logger(__name__).debug(
            "Logging preferences unavailable; using defaults",
            exc_info=True,
        )
    return configure_logging(console_level=level, file=write_file)


def shutdown_logging():
    global _CURRENT_LOG_PATH
    with _CONFIG_LOCK:
        logger = logging.getLogger(LOGGER_NAME)
        _stop_file_listener(logger)
        for handler in tuple(logger.handlers):
            if not getattr(handler, "_cp77_owned", False):
                continue
            logger.removeHandler(handler)
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
        clear_once_messages()
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False
        _CURRENT_LOG_PATH = None


def current_log_path():
    logger = logging.getLogger(LOGGER_NAME)
    for handler in tuple(logger.handlers):
        path = getattr(handler, "_cp77_log_path", None)
        if path:
            return str(path)
    return str(_CURRENT_LOG_PATH) if _CURRENT_LOG_PATH is not None else ""


def is_enabled(level, logger=None):
    return (logger or get_logger()).isEnabledFor(level_from_name(level))


@contextlib.contextmanager
def log_context(**fields):
    cleaned = tuple(
        (str(key), str(value))
        for key, value in fields.items()
        if value is not None and value != ""
    )
    token = _CONTEXT.set((*_CONTEXT.get(), *cleaned))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def operation(logger, label, *, level=logging.INFO, **fields):
    return _Operation(logger, label, level_from_name(level), fields)


def _from_caller(kwargs):
    """kwargs with stacklevel raised by one, so the record names the helper's caller"""
    kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
    return kwargs


def log_once(logger, level, key, message, *args, **kwargs):
    identity = (logger.name, str(key))
    with _ONCE_LOCK:
        if identity in _ONCE_KEYS:
            return False
        if len(_ONCE_KEYS) >= _ONCE_LIMIT:
            _ONCE_KEYS.clear()
        _ONCE_KEYS.add(identity)
    logger.log(level_from_name(level), message, *args, **_from_caller(kwargs))
    return True


def log_on_change(logger, level, key, message, *args, **kwargs):
    """Log message for key only when its text differs from the last one logged for that key"""
    identity = (logger.name, str(key))
    text = message % args if args else str(message)
    with _ONCE_LOCK:
        if _LAST_MESSAGES.get(identity) == text:
            return False
        if len(_LAST_MESSAGES) >= _ONCE_LIMIT:
            _LAST_MESSAGES.clear()
        _LAST_MESSAGES[identity] = text
    logger.log(level_from_name(level), message, *args, **_from_caller(kwargs))
    return True


def clear_once_messages():
    with _ONCE_LOCK:
        _ONCE_KEYS.clear()
        _LAST_MESSAGES.clear()


class LogLimiter:
    """Logs the first limit records of each key at level and the rest at DEBUG"""

    def __init__(self, logger, level, limit, summary):
        self._logger = logger
        self._level = level_from_name(level)
        self._limit = max(1, int(limit))
        self._summary = summary
        self._counts = {}
        self._first = {}

    def log(self, key, message, *args, **kwargs):
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        if count == 1:
            self._first[key] = message % args if args else str(message)
        level = self._level if count <= self._limit else logging.DEBUG
        self._logger.log(level, message, *args, **_from_caller(kwargs))
        return count <= self._limit

    def flush(self):
        omitted_total = 0
        for key, count in self._counts.items():
            omitted = count - self._limit
            if omitted > 0:
                omitted_total += omitted
                self._logger.log(
                    self._level, self._summary, omitted, self._first[key], stacklevel=2
                )
        self._counts.clear()
        self._first.clear()
        return omitted_total


def debug_exception(logger, message, *args, **kwargs):
    kwargs["exc_info"] = True
    logger.debug(message, *args, **_from_caller(kwargs))
