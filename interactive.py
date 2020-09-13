import bpy
from mathutils import Vector
from . draw_2d import Draw2D
from . draw_3d import Draw3D
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d, region_2d_to_location_3d

def screen_space_to_3d(location, distance, context):
    region = context.region
    data = context.space_data.region_3d
    if data.is_perspective:
        vec = region_2d_to_vector_3d(region, data, location)
        origin = region_2d_to_origin_3d(region, data, location, distance)
    else:
        vec = data.view_rotation @ Vector((0, 0, -1))
        origin = region_2d_to_location_3d(
            region, data, location, -vec * data.view_distance)
    location = vec * distance + origin
    return location


class InteractiveOperator(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}

    _loop = None
    draw_2d = None
    draw_3d = None

    lmb = False
    rmb = False
    mmb = False

    wheel = 0

    mouse_co = Vector((0, 0))
    last_mouse_co = Vector((0, 0))

    def event_handle(self, event):
        if event.value == 'PRESS':
            if event.type == 'LEFTMOUSE':
                self.lmb = True
            if event.type == 'RIGHTMOUSE':
                self.rmb = True
            if event.type == 'MIDDLEMOUSE':
                self.mmb = True

        elif event.value == 'RELEASE':
            if event.type == 'LEFTMOUSE':
                self.lmb = False
            if event.type == 'RIGHTMOUSE':
                self.rmb = False
            if event.type == 'MIDDLEMOUSE':
                self.mmb = False

        if event.type == 'WHEELUPMOUSE':
            self.wheel = 1

        elif event.type == 'WHEELDOWNMOUSE':
            self.wheel = -1

        else:
            self.wheel = 0

        self.last_mouse_co = self.mouse_co
        self.mouse_co = Vector((event.mouse_region_x, event.mouse_region_y))

    def invoke(self, context, event):
        wm = context.window_manager
        wm.modal_handler_add(self)
        self._loop = self.loop(context)
        self.draw_2d = Draw2D()
        self.draw_3d = Draw3D()
        self.draw_2d.setup_handler()
        self.draw_3d.setup_handler()
        return next(self._loop)

    def modal(self, context, event):
        try:
            context.area.tag_redraw()
            self.event_handle(event)
            ret = self._loop.send(event)

        except StopIteration:
            ret = {'FINISHED'}

        except:
            self.draw_2d.remove_handler()
            self.draw_3d.remove_handler()
            raise

        if ret & {'CANCELLED', 'FINISHED'}:
            self.draw_2d.remove_handler()
            self.draw_3d.remove_handler()

        return ret

    def loop(self, context):
        raise NotImplementedError
