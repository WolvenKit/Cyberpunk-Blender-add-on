"""
Blender 5.0 Action API compatibility layer.

Blender 5.0 replaced ``action.fcurves`` (which now returns **None**)
with a layered structure:

    action.layers[i].strips[j].channelbags[k].fcurves

The :func:`get_action_fcurves` helper returns the correct FCurves
collection regardless of Blender version so that call-sites can use
a single API for iteration, ``find()``, ``new()``, and ``remove()``.
"""


def get_action_fcurves(action):
    """Return the FCurves collection for *action*, or ``None``.

    * **Blender ≤ 4.x** – returns ``action.fcurves`` directly.
    * **Blender 5.0+**  – navigates the layered structure and returns
      ``channelbag.fcurves`` from the first strip of the first layer.

    The returned object supports ``find()``, ``new()``, ``remove()``,
    ``clear()``, and standard iteration.
    """
    # Blender 4.x: action.fcurves is a real collection
    try:
        fc = action.fcurves
        if fc is not None:
            return fc
    except AttributeError:
        pass

    # Blender 5.0+: layered action API
    try:
        cb_fc = action.layers[0].strips[0].channelbags[0].fcurves
        return cb_fc
    except (IndexError, AttributeError):
        return None
