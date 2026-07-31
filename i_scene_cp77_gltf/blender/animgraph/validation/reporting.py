import json
from typing import Any, List

from ..access import get_idprop
from .. import variables


def root_tree(tree: Any) -> Any:
    try:
        return variables.root_tree_for(tree) or tree
    except Exception:
        return tree


def append_limited(items: List[str], text: str, *, limit: int) -> None:
    if len(items) < limit:
        items.append(str(text))


def write_report(
    tree: Any,
    report: dict,
    *,
    report_key: str,
    summary_key: str,
    ready_key: str,
    summary_field: str = 'summary',
) -> None:
    root = root_tree(tree)
    if root is None:
        return
    try:
        root[report_key] = json.dumps(report, ensure_ascii=False, sort_keys=True)
        root[summary_key] = str(report.get(summary_field, '') or report.get('summary', ''))
        root[ready_key] = bool(report.get('ready', False))
    except Exception:
        pass


def load_report(tree: Any, *, report_key: str) -> dict:
    root = root_tree(tree)
    raw = get_idprop(root, report_key, '')
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}
