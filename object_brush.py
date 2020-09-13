import bpy
from . interactive import InteractiveOperator, screen_space_to_3d
from . multifile import register_class, topbar_mt_app_system_add
from math import sin, cos, pi
from mathutils import Vector


@topbar_mt_app_system_add
@register_class
class ObjectBrush(InteractiveOperator):
    bl_idname = 'sculpt_tool_kit.object_brush'
    bl_label = 'Object Brush'

    def loop(self, context):

        event = yield {'RUNNING_MODAL'}

        ob = bpy.context.active_object

        for other_ob in context.scene.objects:
            other_ob.select_set(False)

        ob.select_set(True)

        while True:
            self.draw_3d.clear()

            if event.type == 'ESC':
                yield {'FINISHED'}

            mouse_co = self.mouse_co

            screen_origin = screen_space_to_3d(mouse_co, 0, context)
            mouse_ray = (screen_space_to_3d(mouse_co, 1, context) - screen_origin).normalized()

            result, location, normal, index, object, matrix = context.scene.ray_cast(
                context.view_layer, screen_origin, mouse_ray)

            if not result:
                self.draw_3d.update_batch()
                event = yield {'PASS_THROUGH'}
                continue

            mat_inv = matrix.inverted()

            location = mat_inv @ location
            normal.rotate(mat_inv)

            self.draw_3d.depth_test = False

            normal_avg = normal.copy()

            for h in range(5):
                u = normal.orthogonal().normalized()
                v = u.cross(normal)

                n = 20

                hit_points = []
                for i in range(n):
                    t = 2 * pi * (i / n) + ((h + 1) / 2.5 * (pi / n))
                    point = (sin(t) * u + cos(t) * v) * ((h + 1) / 5) + location

                    result, location1, normal, index = object.closest_point_on_mesh(point)
                    if result:
                        hit_points.append(location1)

                        for vindex in object.data.polygons[index].vertices:
                            normal_avg += object.data.vertices[vindex].normal

                normal = normal_avg.normalized()

            location = matrix @ location
            normal.rotate(matrix)

            print(normal_avg.dot(normal))

            self.draw_3d.add_circle(location, normal, 2, 20, (0, 0, 0, 1))
            self.draw_3d.add_line(location, location + normal, (0, 0, 0, 1))

            self.draw_3d.update_batch()


            if event.type == 'LEFTMOUSE' and event.value == "PRESS":
                ob = bpy.context.active_object
                ob.select_set(True)
                bpy.ops.object.duplicate()

                dup = bpy.context.active_object
                dup.select_set(False)
                ob.select_set(True)
                bpy.context.view_layer.objects.active = ob

                dup.location = location

                while not (event.type == 'LEFTMOUSE' and event.value == 'RELEASE'):
                    print('pressed')
                    event = yield {'RUNNING_MODAL'}


            event = yield {'PASS_THROUGH'}

        yield {'FINISHED'}
