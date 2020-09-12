import bpy
from . interactive import InteractiveOperator
from . multifile import register_class, topbar_mt_app_system_add
from mathutils import Vector
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d, region_2d_to_location_3d
import bmesh
from math import sin, cos, pi


BLACK = Vector((0, 0, 0, 1))
RED = Vector((1, 0, 0, 1))
GREEN = Vector((0, 1, 0, 1))
BLUE = Vector((0, 0, 1, 1))
ALPHA = Vector((0, 0, 0, 1))


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


def cut(context, points, thickness=0.0001, distance_multiplier=10, cyclic=True):
    origin = screen_space_to_3d((0, 0), 0, context)
    dist = context.region_data.view_distance
    end = context.space_data.clip_end
    bm = bmesh.new()
    verts = []
    for point in points:
        p1 = screen_space_to_3d(point, 1, context)
        p2 = screen_space_to_3d(point, dist * distance_multiplier, context)
        verts.append((bm.verts.new(p1), bm.verts.new(p2)))

    for i in range(len(verts) - 1):
        a, b = verts[i]
        c, d = verts[i + 1]
        bm.faces.new((a, b, d, c))

    if cyclic and len(points) > 2:
        a, b = verts[0]
        c, d = verts[-1]
        bm.faces.new((a, b, d, c))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thickness)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name='cuter_mesh')
    bm.to_mesh(mesh)
    cuter = bpy.data.objects.new(name='cuter_object', object_data=mesh)
    context.scene.collection.objects.link(cuter)

    for ob in list(context.view_layer.objects.selected):
        context.view_layer.objects.active = ob
        md = ob.modifiers.new(type='BOOLEAN', name='Cut')
        md.object = cuter
        md.operation = 'DIFFERENCE'
        bpy.ops.object.modifier_apply(modifier=md.name)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.holes_fill(bm, edges=bm.edges)
        bmesh.ops.triangulate(
            bm, faces=[face for face in bm.faces if len(face.verts) > 4])
        bm.to_mesh(ob.data)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.data.objects.remove(cuter)
    bpy.data.meshes.remove(mesh)


def lerp(a, b, t):
    return a + (b - a) * t


def bezier_interpolate(a, b, c, d, t):
    # todo: optimize later :/
    ab, bc, cd = lerp(a, b, t),  lerp(b, c, t), lerp(c, d, t)
    abbc = lerp(ab, bc, t)
    bccd = lerp(bc, cd, t)
    return lerp(abbc, bccd, t)


def bezier_curve_points(a, b, c, d, resolution):
    for i in range(resolution):
        yield bezier_interpolate(a, b, c, d, i / resolution)


class SlashToolBase:
    ortho_vecs = (Vector((0, 1)),
                  Vector((1, 0)),
                  Vector((1, 1)),
                  Vector((1, -1)))

    def __init__(self):
        self.points = []
        self.cyclic = False
        self.orthogonal = False
        self.done = False

    def update(self):
        pass

    def ortho_project(self, mouse_co):
        if not self.points:
            return mouse_co

        vec = mouse_co - self.points[-1]
        return max((vec.project(orth) for orth in self.ortho_vecs), key=lambda v: v.dot(vec)) + self.points[-1]

    def grab_mode(self, mouse_co):

        old_points = self.points
        while True:
            print('grab mode')
            new_co = yield
            print(new_co)
            print(mouse_co)
            self.points = [pt + new_co - mouse_co for pt in old_points]

    def on_click(self, mouse_co):
        pass

    def on_drag(self, mouse_co):
        pass

    def on_mousemove(self, mouse_co):
        pass

    def on_enter(self, mouse_co):
        self.done = True

    def on_wheel(self, dir):
        pass

    def draw(self, draw_2d, mouse_co):
        raise

    def undo(self, mouse_co):
        pass

    def cut(self, context, thickness=0.0001):
        cut(context, self.points, thickness, 50, self.cyclic)


class PolyCut(SlashToolBase):
    min_point_dist = 10

    def on_drag(self, mouse_co):
        print('drag')
        if self.points:
            d = (mouse_co - self.points[-1]).length
            if d > self.min_point_dist * 2:
                self.points.append(0.5 * (mouse_co + self.points[-1]))
        else:
            self.points.append(mouse_co)

    def on_click(self, mouse_co):
        print('click')
        if self.points:
            end1 = self.points[0]
            end2 = self.points[-1]

            if (end1 - mouse_co).length < (end2 - mouse_co).length:
                closest_end = end1
                self.cyclic = True
            else:
                closest_end = end2
                self.cyclic = False

            d = (mouse_co - closest_end).length
            if d <= self.min_point_dist:
                self.done = True
                return

        self.points.append(mouse_co)

    def undo(self, mouse_co):
        if self.points:
            self.points.pop(-1)

    def draw(self, draw_2d, mouse_co):
        print('draw')
        if len(self.points) > 1:
            for i in range(len(self.points) - 1):
                p1 = self.points[i]
                p2 = self.points[i + 1]
                draw_2d.add_line(p1, p2, color_a=BLACK)

        draw_2d.add_circle(mouse_co, 3, 16, RED)

        if self.points:
            draw_2d.add_line(self.points[-1], mouse_co, color_a=(1, 0.5, 0, 1))

            draw_2d.add_circle(
                self.points[-1], self.min_point_dist, 10, color=(1, 0, 0, 0.5))
            draw_2d.add_circle(
                self.points[0], self.min_point_dist, 10, color=(0, 0.2, 1, 0.5))

            end1 = self.points[0]
            end2 = self.points[-1]

            if (end1 - mouse_co).length < (end2 - mouse_co).length:
                closest_end = end1
                color = (0, 0.2, 1, 1)
            else:
                closest_end = end2
                color = (1, 0.2, 0, 1)

            d = (mouse_co - closest_end).length
            if d <= self.min_point_dist:
                draw_2d.add_text('click to cut', mouse_co +
                                 Vector((10, 10)), color=color, size=20)


class EllipseCut(SlashToolBase):

    resolution = 20

    def cut(self, context, thickness=0.0001):
        cut(context, list(self.ellipse_points(None)), thickness, 50, True)

    def ortho_project(self, mouse_co):
        if not self.points:
            return mouse_co

        if len(self.points) == 2:
            u = self.points[1] - self.points[0]
            u = u.yx
            u.x *= -1

            ortho_vecs = [u]

        else:
            ortho_vecs = self.ortho_vecs

        vec = mouse_co - self.points[0]
        return max((vec.project(orth) for orth in ortho_vecs), key=lambda v: v.dot(vec)) + self.points[0]

    def on_click(self, mouse_co):
        self.points.append(mouse_co)

        if len(self.points) == 3:
            self.done = True

    def on_wheel(self, dir):
        self.resolution += dir
        self.resolution = max(self.resolution, 1)

    def ellipse_points(self, mouse_co):
        n = len(self.points)
        if 1 <= n <= 3:
            if n == 1:
                u = mouse_co - self.points[0]
                v = u.yx
                v.x *= -1

            elif n == 2:
                u = self.points[1] - self.points[0]
                v = (mouse_co - self.points[0])
                print(u.dot(v))

            elif n == 3:
                u = self.points[1] - self.points[0]
                v = self.points[2] - self.points[0]

            for i in range(self.resolution):
                a = (i * 2 * pi) / self.resolution

                yield u * sin(a) + v * cos(a) + self.points[0]

    def undo(self, mouse_co):
        if self.points:
            self.points.pop(-1)

    def draw(self, draw_2d, mouse_co):

        ellipse = list(self.ellipse_points(mouse_co))

        draw_2d.add_line_loop(ellipse, BLACK, cyclic=True)

        n = len(self.points)

        if n >= 1:
            draw_2d.add_circle(self.points[0], 3, 16, RED)

        if n >= 2:
            draw_2d.add_circle(self.points[1], 3, 16, GREEN)

        if n >= 3:
            draw_2d.add_circle(self.points[2], 3, 16, BLUE)

        if n < 3:
            mouse_color = (RED, GREEN, BLUE)[n]
            draw_2d.add_circle(mouse_co, 3, 16, mouse_color)


class RectangleCut(SlashToolBase):

    def rectangle_points(self, a, b):
        x_min = min(a.x, b.x)
        x_max = max(a.x, b.x)
        y_min = min(a.y, b.y)
        y_max = max(a.y, b.y)

        return [Vector((x_min, y_min)), Vector((x_max, y_min)),
                Vector((x_max, y_max)), Vector((x_min, y_max))]

    def on_click(self, mouse_co):
        self.points.append(mouse_co)

        if len(self.points) == 2:
            self.done = True

    def undo(self, mouse_co):
        if self.points:
            self.points.pop(-1)

    def draw(self, draw_2d, mouse_co):

        n = len(self.points)

        if n == 0:
            draw_2d.add_circle(mouse_co, 3, 16, RED)
            points = None

        elif n == 1:
            draw_2d.add_circle(self.points[0], 3, 16, RED)
            draw_2d.add_circle(mouse_co, 3, 16, GREEN)
            points = self.rectangle_points(self.points[0], mouse_co)

        elif n == 2:
            draw_2d.add_circle(self.points[0], 3, 16, RED)
            draw_2d.add_circle(self.points[1], 3, 16, GREEN)
            points = self.rectangle_points(self.points[0], self.points[1])

        if points:
            draw_2d.add_line_loop(points, BLACK, cyclic=True)

    def cut(self, context, thickness=0.0001):
        cut(context, self.rectangle_points(
            self.points[0], self.points[1]), thickness, 50, cyclic=True)



class SplineCut(SlashToolBase):

    resolution = 10
    confirm_dist = 10

    def on_click(self, mouse_co):
        if self.points:
            d = (self.points[-1] - mouse_co).length
            d1 = (self.points[0] - mouse_co).length

            if min(d, d1) < self.confirm_dist:
                self.done = True
                if d1 < d:
                    self.cyclic = True

                else:
                    self.cyclic = False
                return

        self.points.append(mouse_co)

    def on_enter(self, mouse_co):
        self.points.append(mouse_co)
        self.done = True

    def on_wheel(self, dir):
        self.resolution += dir
        self.resolution = max(self.resolution, 1)

    def spline_points(self, points, resolution, cyclic=False):

        if len(points) <= 2:
            return points

        if cyclic:
            points = [points[-1], *points, points[0], points[1]]

        controll_points = self.auto_bezier_control_points(points)
        new_points = []

        for i in range(len(controll_points) // 3):
            i *= 3
            for p in bezier_curve_points(*controll_points[i:i + 4], resolution):
                new_points.append(p)


        if cyclic:
            new_points = new_points[resolution: -resolution]

        else:
            new_points.append(controll_points[-1])


        return new_points

    def auto_bezier_control_points(self, points):

        if len(points) < 3:
            return points

        new_points = [points[0], points[0]]

        for i in range(len(points) - 2):
            i += 1

            da = points[i - 1] - points[i]
            db = points[i + 1] - points[i]
            n = da.normalized() + db.normalized()
            if n.length_squared == 0:
                n = da.yx
                n.x *= -1

            da -= da.project(n)
            db -= db.project(n)

            new_points.append(da * 0.42 + points[i])
            new_points.append(points[i])
            new_points.append(db * 0.42 + points[i])

        new_points.append(points[-1])
        new_points.append(points[-1])
        return new_points

    def draw(self, draw_2d, mouse_co):

        d = float('inf')
        d1 = float('inf')
        if self.points:
            d = (self.points[-1] - mouse_co).length
            d1 = (self.points[0] - mouse_co).length

            if d1 < d and d1 < self.confirm_dist:
                self.cyclic = True
            else:
                self.cyclic = False

            draw_2d.add_circle(self.points[0], self.confirm_dist, 16, GREEN)
            draw_2d.add_circle(self.points[-1], self.confirm_dist, 16, RED)

            if min(d, d1) < self.confirm_dist:
                draw_2d.add_text('click to cut', mouse_co + Vector((10, 10)), color=RED, size=20)

        if min(d, d1) < self.confirm_dist:
            points = self.spline_points(self.points, self.resolution, self.cyclic)
        else:
            points = self.spline_points(self.points + [mouse_co], self.resolution, self.cyclic)

        draw_2d.add_line_loop(points, BLACK, self.cyclic)

        for point in self.points:
            draw_2d.add_circle(point, 3, 16, RED)

        draw_2d.add_circle(mouse_co, 3, 16, GREEN)

    def undo(self, mouse_co):
        if self.points:
            self.points.pop(-1)

    def cut(self, context, thickness=0.0001):
        cut(context, self.spline_points(self.points, self.resolution, self.cyclic), thickness, 50, self.cyclic)

last_tool = PolyCut

@topbar_mt_app_system_add
@register_class
class SlashCutter(InteractiveOperator):
    bl_idname = 'sculpt_tool_kit.slash'
    bl_label = 'Slash Cutter'


    def loop(self, context):
        global last_tool
        tool = last_tool()

        while True:
            event = yield {'RUNNING_MODAL'}
            self.draw_2d.clear()

            print(event.type, event.value, event.ctrl)

            if event.ctrl:
                mouse_co = tool.ortho_project(self.mouse_co)
                tool.orthogonal = True
            else:
                mouse_co = self.mouse_co
                tool.orthogonal = False

            if not self.wheel == 0:
                tool.on_wheel(self.wheel)

            if event.type == 'D':
                tool = PolyCut()
                last_tool = PolyCut

            elif event.type == 'E':
                tool = EllipseCut()
                last_tool = EllipseCut

            elif event.type == 'S':
                tool = SplineCut()
                last_tool = SplineCut

            elif event.type == 'R':
                tool = RectangleCut()
                last_tool = RectangleCut

            elif event.type == 'PAGE_UP' and event.value == 'PRESS':
                tool.on_wheel(1)

            elif event.type == 'PAGE_DOWN' and event.value == 'PRESS':
                tool.on_wheel(-1)

            elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                tool.on_click(mouse_co)

            elif event.type == 'Z' and event.ctrl and event.value == "PRESS":
                tool.undo(mouse_co)

            elif event.type == 'MOUSEMOVE' and self.lmb:
                tool.on_drag(mouse_co)

            elif event.type == 'MOUSEMOVE':
                tool.on_mousemove(mouse_co)

            elif event.type == 'RET':
                tool.on_enter(mouse_co)

            elif event.type == 'G' and event.value == 'PRESS':
                grab_mode = tool.grab_mode(mouse_co)
                next(grab_mode)
                while True:
                    grab_mode.send(self.mouse_co)
                    self.draw_2d.clear()
                    tool.draw(self.draw_2d, mouse_co)

                    event = yield {'RUNNING_MODAL'}
                    mouse_co = self.mouse_co
                    if event.type == 'RET' or self.lmb:
                        break

            elif event.type == 'C' and event.value == 'PRESS':
                tool.cyclic = not tool.cyclic

            elif event.type == 'ESC':
                return {'CANCELLED'}

            help_text = f'''
            Current tool: {tool.__class__.__name__}
            D: PolyCut, E: EllipseCut, S: SplineCut, R: RectangleCut
            cyclic mode (C): {'enabled' if tool.cyclic else 'disabled'}
            orthogonal mode (ctrl): {'enabled' if tool.orthogonal else 'disabled'}
            undo: (ctrl + Z)
            '''

            for i, line in enumerate(reversed(help_text.split('\n'))):
                self.draw_2d.add_text(line, Vector((10, i*25)), 20, Vector((0.9, 0.8, 0, 1)))

            tool.update()
            tool.draw(self.draw_2d, mouse_co)

            if tool.done:
                tool.cut(context)
                return {'FINISHED'}
