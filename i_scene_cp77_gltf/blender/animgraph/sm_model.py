import uuid

from ...animation.model.animgraph.schema import enums

INTERPOLATION_TYPE_ENUM = "animAnimStateInterpolationType"


INTERPOLATION_TYPE_ITEMS = tuple(enums.enum_items(INTERPOLATION_TYPE_ENUM))


BLEND_INTERPOLATOR_TYPE = "animAnimStateTransitionInterpolator_Blend"


def new_handle_id():
    """Placeholder id unique across sessions"""
    return f"new:{uuid.uuid4().hex}"
