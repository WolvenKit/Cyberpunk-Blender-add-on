import json
from typing import Any

from ....core.log import get_logger, log_once
from .. import variables
from ..access import get_idprop

_LOG = get_logger(__name__)


def root_tree(tree: Any) -> Any:
    try:
        return variables.root_tree_for(tree) or tree
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("root_tree", type(error).__name__),
            "root tree: fell back after %s",
            error,
            exc_info=True,
        )
        return tree


def append_limited(items: list[str], text: str, *, limit: int) -> None:
    if len(items) < limit:
        items.append(str(text))


def write_report(
    tree: Any,
    report: dict,
    *,
    report_key: str,
    summary_key: str,
    ready_key: str,
    summary_field: str = "summary",
) -> None:
    root = root_tree(tree)
    if root is None:
        return
    try:
        root[report_key] = json.dumps(report, ensure_ascii=False, sort_keys=True)
        root[summary_key] = str(
            report.get(summary_field, "") or report.get("summary", "")
        )
        root[ready_key] = bool(report.get("ready", False))
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("write_report", type(error).__name__),
            "write report: fell back after %s",
            error,
            exc_info=True,
        )


def report_text(tree: Any, *, report_key: str) -> str:
    return str(get_idprop(root_tree(tree), report_key, "") or "")
