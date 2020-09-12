import bpy
from random import choice
import traceback
import importlib

from .multifile import register, unregister, add_modules, import_modules

bl_info = {
    'name': 'Sculpt Tool Kit',
    'description': 'Sculpting tools to improve workflow',
    'author': 'Jean Da Costa Machado',
    'version': (1, 5, 0),
    'blender': (2, 80, 0),
    'wiki_url': '',
    'category': 'Sculpt',
    'location': '3D View > Properties (shortcut : N) > SculpTKt tab'}

add_modules(['booleans',
            'draw_2d',
            'envelope_builder',
            'interface',
            'mask_tools',
            'mesh_ops',
            'remesh',
            'interactive',
            'slash_cut',
            'symmetry_tools'])
import_modules()
