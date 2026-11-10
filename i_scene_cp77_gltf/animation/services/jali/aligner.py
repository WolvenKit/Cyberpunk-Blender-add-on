import os

from ....assetio.arrays import read_npz_arrays
from ....assetio.resources import get_jali_dir
from ....core.log import get_logger
from ...domain.jali.alignment import aligner_model_from_arrays

_LOG = get_logger(__name__)
_MODELS = {}


def bundled_aligner_model():
    path = os.path.join(get_jali_dir(), "aligner_model.npz")
    model = _MODELS.get(path)
    if model is None:
        raw = read_npz_arrays(path)
        if raw is None:
            _LOG.warning("Aligner model missing or unreadable: %s", path)
            return None
        model = _MODELS[path] = aligner_model_from_arrays(raw)
    return model
