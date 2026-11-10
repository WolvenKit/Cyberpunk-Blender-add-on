import os
from functools import cache

from ....assetio.arrays import read_npz_arrays
from ....assetio.resources import get_jali_dir
from ...domain.jali.alignment import aligner_model_from_arrays


@cache
def bundled_aligner_model():
    raw = read_npz_arrays(os.path.join(get_jali_dir(), "aligner_model.npz"))
    return None if raw is None else aligner_model_from_arrays(raw)
