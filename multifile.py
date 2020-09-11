import bpy
import importlib
import traceback


class RegisterStuff:
    all_classes = []
    register_fncs = []
    unregister_fncs = []
    imported_modules = []
    registered_classes = []
    module_names = []
    menu_entries = []

    def __init__(self):
        raise RuntimeError("cant instantiate")

    def clear_classes():
        RegisterStuff.all_classes.clear()
        RegisterStuff.register_fncs.clear()
        RegisterStuff.unregister_fncs.clear()
        for menu_cls, entry in RegisterStuff.menu_entries:
            menu_cls.remove(entry)


def register_class(cls=None):
    RegisterStuff.all_classes.append(cls)
    return cls


def topbar_mt_app_system_add(op):
    def draw(self, context):
        layout = self.layout
        layout.operator(op.bl_idname)
    bpy.types.TOPBAR_MT_app_system.append(draw)
    RegisterStuff.menu_entries.append((bpy.types.TOPBAR_MT_app_system, draw))
    return op


def register_function(func):
    RegisterStuff.register_fncs.append(func)
    return func


def unregister_function(func):
    RegisterStuff.unregister_fncs.append(func)
    return func


def register():
    print('register')
    for cls in RegisterStuff.all_classes:
        bpy.utils.register_class(cls)
        print('register', cls)
        RegisterStuff.registered_classes.append(cls)

    for func in RegisterStuff.register_fncs:
        func()


def unregister():
    print('unregister')
    for cls in RegisterStuff.registered_classes:
        print('unregister', cls)
        bpy.utils.unregister_class(cls)

    RegisterStuff.registered_classes.clear()

    for func in RegisterStuff.unregister_fncs:
        func()


def import_modules():
    RegisterStuff.clear_classes()

    if RegisterStuff.imported_modules:
        print('reload')
        unregister()
        for module in RegisterStuff.imported_modules:
            importlib.reload(module)
        RegisterStuff.imported_modules.clear()

    for mdname in RegisterStuff.module_names:
        try:
            exec(f'from . import {mdname}')
            RegisterStuff.imported_modules.append(locals()[mdname])
            print('importing', locals()[mdname])
        except Exception as e:
            print(e)
            raise e


def add_modules(modules):
    for modname in modules:
        if modname not in RegisterStuff.module_names:
            RegisterStuff.module_names.append(modname)

    import_modules()


__all__ = [
    'register_class',
    'register_function',
    'unregister_function',
    'register',
    'unregister',
    'maybe_reload',
]
