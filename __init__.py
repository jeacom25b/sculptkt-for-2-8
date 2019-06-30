import bpy
from random import choice
import traceback
import importlib

from .multifile import register, unregister, add_module, import_modules, register_class

bl_info = {
    "name": "Sculpt Tool Kit",
    "description": "Sculpting tools to improve workflow",
    "author": "Jean Da Costa Machado",
    "version": (1, 28, 1),
    "blender": (2, 80, 0),
    "wiki_url": "",
    "category": "Sculpt",
    "location": "3D View > Properties (shortcut : N) > SculpTKt tab"}

add_module("mask_tools")
add_module("remesh")
add_module("slash_cuter")
add_module("interface")
add_module("booleans")
add_module("envelope_builder")
add_module("symmetry_tools")
import_modules()
