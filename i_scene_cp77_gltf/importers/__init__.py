def register_importers():
    from .operators import register_importers as _register_importers

    return _register_importers()


def unregister_importers():
    from .operators import unregister_importers as _unregister_importers

    return _unregister_importers()


def menu_func_import(self, context):
    from .operators import menu_func_import as _menu_func_import

    return _menu_func_import(self, context)


__all__ = ("menu_func_import", "register_importers", "unregister_importers")
