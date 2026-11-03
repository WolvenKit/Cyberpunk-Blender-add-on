import inspect
from collections.abc import Mapping

import bpy


_REGISTERABLE_TYPE_NAMES = (
    "PropertyGroup",
    "NodeSocket",
    "NodeTree",
    "Node",
    "UIList",
    "Operator",
    "Menu",
    "Header",
    "Panel",
    "AddonPreferences",
    "RenderEngine",
    "KeyingSetInfo",
    "Gizmo",
    "GizmoGroup",
    "AssetShelf",
    "FileHandler",
)

_TYPE_PRIORITY = {
    "PropertyGroup": 0,
    "NodeSocket": 10,
    "NodeTree": 20,
    "Node": 30,
    "UIList": 40,
    "Operator": 50,
    "Menu": 60,
    "Header": 60,
    "Panel": 70,
    "AddonPreferences": 80,
    "RenderEngine": 90,
    "KeyingSetInfo": 90,
    "Gizmo": 90,
    "GizmoGroup": 90,
    "AssetShelf": 90,
    "FileHandler": 90,
}


def _registerable_bases():
    return tuple(
        base
        for name in _REGISTERABLE_TYPE_NAMES
        if inspect.isclass(base := getattr(bpy.types, name, None))
    )


def _is_registerable_class(value, bases):
    if not inspect.isclass(value):
        return False
    try:
        return bool(bases) and issubclass(value, bases)
    except TypeError:
        return False


def _validate_deferred_annotations(classes):
    invalid = []
    for cls in classes:
        for name, value in getattr(cls, "__annotations__", {}).items():
            if isinstance(value, str):
                invalid.append(f"{cls.__module__}.{cls.__name__}.{name}")
    if invalid:
        joined = ", ".join(sorted(invalid))
        raise RuntimeError(
            "Blender registration properties cannot use string annotations: "
            f"{joined}. Remove postponed annotation evaluation from the "
            "registerable module."
        )


def _iter_property_types(value):
    keywords = getattr(value, "keywords", None)
    if isinstance(keywords, Mapping):
        dependency = keywords.get("type")
        if inspect.isclass(dependency):
            yield dependency

    if isinstance(value, Mapping):
        dependency = value.get("type")
        if inspect.isclass(dependency):
            yield dependency
        return

    if isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            yield from _iter_property_types(item)


def _class_dependencies(cls, class_set, classes_by_idname):
    dependencies = {
        base
        for base in cls.__bases__
        if base in class_set and base is not cls
    }

    for value in getattr(cls, "__annotations__", {}).values():
        dependencies.update(
            dependency
            for dependency in _iter_property_types(value)
            if dependency in class_set and dependency is not cls
        )

    for value in vars(cls).values():
        dependencies.update(
            dependency
            for dependency in _iter_property_types(value)
            if dependency in class_set and dependency is not cls
        )

    parent_id = getattr(cls, "bl_parent_id", "")
    parent = classes_by_idname.get(parent_id)
    if parent is not None and parent is not cls:
        dependencies.add(parent)

    return dependencies


def _class_priority(cls):
    for name in _REGISTERABLE_TYPE_NAMES:
        base = getattr(bpy.types, name, None)
        if not inspect.isclass(base):
            continue
        try:
            if issubclass(cls, base):
                return _TYPE_PRIORITY[name]
        except TypeError:
            continue
    return 100


def get_classes(module, *, extra_classes=()):
    bases = _registerable_bases()
    module_classes = tuple(
        value
        for _, value in inspect.getmembers(module)
        if _is_registerable_class(value, bases)
        and value.__module__ == module.__name__
    )
    explicit_classes = tuple(extra_classes)
    invalid_explicit = tuple(
        value
        for value in explicit_classes
        if not _is_registerable_class(value, bases)
    )
    if invalid_explicit:
        names = ", ".join(
            getattr(value, "__name__", repr(value))
            for value in invalid_explicit
        )
        raise TypeError(f"Non-registerable explicit Blender classes: {names}")
    classes = tuple(dict.fromkeys((*module_classes, *explicit_classes)))
    _validate_deferred_annotations(classes)
    class_set = set(classes)
    classes_by_idname = {
        bl_idname: cls
        for cls in classes
        if (bl_idname := getattr(cls, "bl_idname", ""))
    }
    dependencies = {
        cls: _class_dependencies(cls, class_set, classes_by_idname)
        for cls in classes
    }

    ordered = []
    remaining = set(classes)
    while remaining:
        ready = [
            cls
            for cls in remaining
            if not (dependencies[cls] & remaining)
        ]
        if not ready:
            cycle = ", ".join(sorted(cls.__name__ for cls in remaining))
            raise RuntimeError(
                f"Cyclic Blender class registration dependencies: {cycle}"
            )
        ready.sort(key=lambda cls: (_class_priority(cls), cls.__name__))
        ordered.extend(ready)
        remaining.difference_update(ready)

    return tuple(ordered)

class RegistrationOwnershipError(RuntimeError):
    pass


def register_owned_classes(classes):
    registered = []
    try:
        for cls in classes:
            existing = getattr(bpy.types, cls.__name__, None)
            if existing is cls:
                continue
            if existing is not None:
                raise RegistrationOwnershipError(
                    f"Blender class name already owned by another addon: {cls.__name__}"
                )
            bpy.utils.register_class(cls)
            registered.append(cls)
    except Exception:
        unregister_owned_classes(reversed(registered))
        raise
    return tuple(registered)


def unregister_owned_classes(classes):
    failures = []
    for cls in classes:
        if getattr(bpy.types, cls.__name__, None) is not cls:
            continue
        try:
            bpy.utils.unregister_class(cls)
        except Exception as error:
            failures.append((cls, error))
    return tuple(failures)


class RegistrationLedger:
    def __init__(self, name):
        self.name = str(name)
        self._cleanup = []

    def add_cleanup(self, label, callback):
        self._cleanup.append((str(label), callback))

    def register_classes(self, classes):
        registered = register_owned_classes(classes)
        for cls in registered:
            self.add_cleanup(
                f"class {cls.__name__}",
                lambda cls=cls: unregister_owned_classes((cls,)),
            )
        return registered

    def add_property(self, owner, name, value):
        if hasattr(owner, name):
            raise RegistrationOwnershipError(
                f"RNA property already exists: {owner.__name__}.{name}"
            )
        setattr(owner, name, value)
        self.add_cleanup(
            f"property {owner.__name__}.{name}",
            lambda owner=owner, name=name: delattr(owner, name)
            if hasattr(owner, name) else None,
        )

    def add_handler(self, handlers, callback):
        if callback in handlers:
            return
        handlers.append(callback)
        self.add_cleanup(
            f"handler {getattr(callback, '__name__', callback)}",
            lambda handlers=handlers, callback=callback: handlers.remove(callback)
            if callback in handlers else None,
        )

    def add_timer(self, callback, **kwargs):
        if not bpy.app.timers.is_registered(callback):
            bpy.app.timers.register(callback, **kwargs)
        self.add_cleanup(
            f"timer {getattr(callback, '__name__', callback)}",
            lambda callback=callback: bpy.app.timers.unregister(callback)
            if bpy.app.timers.is_registered(callback) else None,
        )

    def cleanup(self):
        failures = []
        remaining = []
        for label, callback in reversed(self._cleanup):
            try:
                result = callback()
                if result:
                    failures.append((label, RuntimeError(str(result))))
                    remaining.append((label, callback))
            except Exception as error:
                failures.append((label, error))
                remaining.append((label, callback))
        self._cleanup[:] = list(reversed(remaining))
        return tuple(failures)

    @property
    def active(self):
        return bool(self._cleanup)
