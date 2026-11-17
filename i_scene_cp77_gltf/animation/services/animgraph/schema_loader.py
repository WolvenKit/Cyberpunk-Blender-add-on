import os

from ....assetio.documents import load_json_payload
from ....assetio.resources import get_animgraph_dir
from ....core.log import debug_exception, get_logger
from ...model.animgraph.schema import registry

_LOG = get_logger(__name__)


def load_animgraph_schema():
    path = os.path.join(get_animgraph_dir(), "newanimnodes.json")
    rows = []
    if os.path.exists(path):
        try:
            rows = load_json_payload(path)
        except Exception:
            debug_exception(_LOG, "AnimGraph RTTI metadata load details")
            rows = []
    registry.install_records(rows)


def clear_animgraph_schema():
    registry.install_records(())
