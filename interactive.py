import bpy
from mathutils import Vector
from . draw_2d import Draw2D


class InteractiveOperator(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}

    _loop = None
    draw_2d = None

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
        self.draw_2d.setup_handler()
        return next(self._loop)

    def modal(self, context, event):
        try:
            context.area.tag_redraw()
            self.event_handle(event)
            ret = self._loop.send(event)

        except StopIteration:
            ret = {'FINISHED'}
            self.draw_2d.remove_handler()

        except:
            self.draw_2d.remove_handler()
            raise

        return ret

    def loop(self, context):
        raise NotImplementedError
