def register_default_handlers():
    from . import (
        aim_constraint,
        direct_conn,
        orient_constraint,
        point_constraint,
        set_bone_transform,
        simple_bounce,
        simple_spline,
        translation_limit,
        twist_constraint,
    )

    return (
        aim_constraint,
        direct_conn,
        orient_constraint,
        point_constraint,
        set_bone_transform,
        simple_bounce,
        simple_spline,
        translation_limit,
        twist_constraint,
    )
