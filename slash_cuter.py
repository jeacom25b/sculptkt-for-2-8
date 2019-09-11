import bpy
import bmesh
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d, region_2d_to_location_3d
from mathutils import Vector
from .multifile import register_class
from .draw_2d import Draw2D, lerp, circle_point


def screen_space_to_3d(location, distance, context):
    region = context.region
    data = context.space_data.region_3d
    if data.is_perspective:
        vec = region_2d_to_vector_3d(region, data, location)
        origin = region_2d_to_origin_3d(region, data, location, distance)
    else:
        vec = data.view_rotation @ Vector((0, 0, -1))
        origin = region_2d_to_location_3d(region, data, location, -vec * data.view_distance)
    location = vec * distance + origin
    return location


def cut(context, points, thickness=0.0001, distance_multiplier=10, ciclic=True):
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

    if ciclic and len(points) > 2:
        a, b = verts[0]
        c, d = verts[-1]
        bm.faces.new((a, b, d, c))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thickness)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name="cuter_mesh")
    bm.to_mesh(mesh)
    cuter = bpy.data.objects.new(name="cuter_object", object_data=mesh)
    context.scene.collection.objects.link(cuter)

    for ob in context.view_layer.objects.selected:
        context.view_layer.objects.active = ob
        md = ob.modifiers.new(type="BOOLEAN", name="Cut")
        md.object = cuter
        md.operation = "DIFFERENCE"
        bpy.ops.object.modifier_apply(modifier=md.name)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.holes_fill(bm, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=[face for face in bm.faces if len(face.verts) > 4])
        bm.to_mesh(ob.data)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.data.objects.remove(cuter)
    bpy.data.meshes.remove(mesh)


class PolyCut:
    snap_vecs = (
        Vector((1, 0)),
        Vector((0, 1)),
        Vector((-1, 0)),
        Vector((0, -1)),
        Vector((1, 1)).normalized(),
        Vector((1, -1)).normalized(),
        Vector((-1, -1)).normalized(),
        Vector((-1, 1)).normalized()
    )

    def __init__(self, renderer):
        self.renderer = renderer
        self.confirm_distance = 20
        self.points = []

        self.ciclic = False
        self.mode = "DRAW"
        self.left = False
        self.right = False
        self.ctrl = False
        self.undo = False

        self.true_mouse_co = Vector((0, 0))
        self.mouse_co = Vector((0, 0))
        self.last_co = Vector((0, 0))

        context = bpy.context
        self.color = Vector(list(context.preferences.themes['Default'].view_3d.wire) + [1])
        self.active_color = Vector(list(context.preferences.themes['Default'].view_3d.object_active) + [1])
        self.seam_color = Vector(list(context.preferences.themes['Default'].view_3d.edge_seam) + [1])

    def update_states(self, event):

        self.ctrl = event.ctrl

        if event.type == "MOUSEMOVE" and event.value == "RELEASE":
            self.left = False
            self.right = False

        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                self.left = True
            elif event.value == "RELEASE":
                self.left = False

        if event.type == "RIGHTMOUSE":
            if event.value == "PRESS":
                self.right = True
            elif event.value == "RELEASE":
                self.right = False

        if event.value == "PRESS":
            if event.type == "C":
                self.ciclic = not self.ciclic

            elif event.type == "G" and not self.left:
                self.mode = "MOVE" if self.mode == "DRAW" else "MOVE"

            elif event.type == "Z" and self.ctrl:
                self.undo = True

        self.last_co = self.mouse_co
        co = Vector((event.mouse_region_x, event.mouse_region_y))
        self.true_mouse_co = co
        if self.ctrl and self.points:
            d = co - self.points[-1]
            co = max(((vec * d.dot(vec), d.dot(vec)) for vec in self.snap_vecs),
                     key=lambda x: x[1])[0] + self.points[-1]
        self.mouse_co = co

    def handle_event(self, context, event):
        self.update_states(event)

        if self.undo:
            if self.points:
                self.points.pop(-1)
            self.undo = False

        elif self.left and self.mode == "DRAW":

            if not self.points:
                self.points.append(self.mouse_co)
                return {"RUNNING_MODAL"}

            dist = (self.mouse_co - self.points[-1]).length
            if dist > self.confirm_distance:
                self.points.append(self.mouse_co)
                return {"RUNNING_MODAL"}

            elif event.type == "LEFTMOUSE" and event.value == "PRESS" and dist < self.confirm_distance:
                self.cut(context)
                return {"FINISHED"}

        elif self.mode == "MOVE":
            self.translate_points(self.mouse_co - self.last_co)
            if self.left:
                self.mode = "DRAW"

            return {"RUNNING_MODAL"}

        elif event.type == "RET":
            self.cut(context)
            return {"FINISHED"}

        if self.right or event.type == "ESC":
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def translate_points(self, direction):
        for i in range(len(self.points)):
            self.points[i] += direction

    def cut(self, context):
        cut(context, self.points, ciclic=self.ciclic)

    def draw(self):
        self.renderer.clear()

        for i in range(len(self.points) - 1):
            a = self.points[i]
            b = self.points[i + 1]
            self.renderer.add_line(a, b, self.color)

        if self.points:
            d = (self.mouse_co - self.points[-1]).length
            t = 1 - min(max(d / self.confirm_distance, 0), 1)
            cut = d <= self.confirm_distance

            if self.ciclic and len(self.points) > 2:
                self.renderer.add_line(self.points[0],
                                       self.points[-1] if cut else self.mouse_co,
                                       self.color)

            line_col = lerp(self.active_color, self.seam_color, t)
            mid_col = line_col.copy()
            text_col = line_col.copy()
            mid_col[3] = t
            text_col[3] = (t + 1) / 2

            if cut and not self.left and len(self.points) > 1:
                self.renderer.add_text("Click to Cut", self.points[-1] + Vector((5, 5)), 15, text_col)

            self.renderer.add_line(self.points[-1], self.mouse_co, line_col)
            self.renderer.add_circle(self.mouse_co, 5, 6, color=line_col)
            self.renderer.add_circle(self.points[-1], 5, 6, color=mid_col)
            self.renderer.update_batch()
        else:
            self.renderer.add_circle(self.mouse_co, 5, 6, color=self.seam_color)


class RectangleCut(PolyCut):
    snap_vecs = (
        Vector((1, 1)).normalized(),
        Vector((1, -1)).normalized(),
        Vector((-1, -1)).normalized(),
        Vector((-1, 1)).normalized(),
    )

    def handle_event(self, context, event):
        self.update_states(event)

        if self.mode == "DRAW":

            if (self.left or event.type == "RET") and event.value == "PRESS":
                if not event.type == "MOUSEMOVE":
                    print("append Point")
                    self.points.append(self.mouse_co)
                return {"RUNNING_MODAL"}

            if len(self.points) >= 2:
                self.cut(context)
                return {"FINISHED"}

            elif self.undo and self.points:
                self.points.pop(-1)
                return {"RUNNING_MODAL"}

        elif self.mode == "MOVE":
            self.translate_points(self.mouse_co - self.last_co)
            if self.left:
                self.mode = "DRAW"

        if self.left or event.type == "ESC":
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def get_rect_corners(self, pa, pb):
        x_zes = [pa[0], pb[0]]
        y_zes = [pa[1], pb[1]]
        max_x = max(x_zes)
        max_y = max(y_zes)
        min_x = min(x_zes)
        min_y = min(y_zes)

        points = [
            Vector((min_x, min_y)),
            Vector((max_x, min_y)),
            Vector((max_x, max_y)),
            Vector((min_x, max_y)),
        ]
        return points

    def cut(self, context):
        cut(context, self.get_rect_corners(self.points[0], self.points[1]), ciclic=True)

    def draw(self):
        self.renderer.clear()
        self.renderer.add_circle(self.mouse_co, 5, 6, self.seam_color)
        if self.points:
            corners = self.get_rect_corners(self.points[0], self.mouse_co)
            for i in range(len(corners)):
                self.renderer.add_line(corners[i], corners[i - 1], self.color)
            self.renderer.add_line(self.points[0], self.mouse_co, self.seam_color)
            self.renderer.add_circle(self.points[0], 5, 6, self.seam_color)


class EllipseCut(PolyCut):
    circle_resolution = 30

    def handle_event(self, context, event):
        self.update_states(event)
        if self.mode == "DRAW":

            if (self.left or event.type == "RET") and event.value == "PRESS":
                if not event.type == "MOUSEMOVE":
                    self.points.append(self.true_mouse_co)
                return {"RUNNING_MODAL"}

            if len(self.points) > 1:
                self.cut(context)
                return {"FINISHED"}

            elif self.undo:
                if self.points:
                    self.points.pop(0)
                    return {"RUNNING_MODAL"}

        if event.type == "WHEELUPMOUSE":
            self.circle_resolution += 1

        elif event.type == "WHEELDOWNMOUSE":
            self.circle_resolution -= 1

        if self.circle_resolution < 3:
            self.circle_resolution = 3

        if self.mode == "MOVE":
            self.translate_points(self.mouse_co - self.last_co)
            if self.left:
                self.mode = "DRAW"
            return {"RUNNING_MODAL"}

        if self.left or event.type == "ESC":
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def get_circle_points(self, a, b):
        d = a - b
        if not self.ctrl:
            dx = d[0] * 1.41421356237
            dy = d[1] * 1.41421356237
        else:
            dx = d.length
            dy = dx

        points = []
        for i in range(self.circle_resolution):
            p = circle_point(t=i / self.circle_resolution)
            p[0] *= dx
            p[1] *= dy
            points.append(p + self.points[0])
        return points

    def cut(self, context):
        points = self.get_circle_points(self.points[0], self.points[1])
        cut(context, points, ciclic=True)

    def draw(self):
        self.renderer.clear()
        if self.points:
            points = self.get_circle_points(self.points[0], self.true_mouse_co)
            for i in range(len(points)):
                p0 = points[i - 1]
                p1 = points[i]
                self.renderer.add_line(p0, p1, self.color)
            self.renderer.add_circle(self.points[0], 5, 6, self.seam_color)

        self.renderer.add_circle(self.true_mouse_co, 5, 6, self.seam_color)


class SplineCut(PolyCut):
    spline_resolution = 2

    def handle_event(self, context, event):
        self.update_states(event)
        if self.mode == "DRAW":
            if (self.left or event.type == "RET") and event.value == "PRESS":
                if not event.type == "MOUSEMOVE":
                    self.points.append(self.mouse_co)
                    pass
                return {"RUNNING_MODAL"}

            if event.type == "RET":
                self.cut(context)
                return {"FINISHED"}

            elif self.undo:
                if self.points:
                    self.points.pop(-1)
                    self.undo = False
                    return {"RUNNING_MODAL"}

        if event.type == "WHEELUPMOUSE":
            self.spline_resolution += 1

        elif event.type == "WHEELDOWNMOUSE":
            self.spline_resolution -= 1

        if self.spline_resolution > 5:
            self.spline_resolution = 5

        if self.mode == "MOVE":
            self.translate_points(self.mouse_co - self.last_co)
            if self.left:
                self.mode = "DRAW"
            return {"RUNNING_MODAL"}

        if self.left or event.type == "ESC":
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    @staticmethod
    def subdiv_points(points):
        new_points = []
        for i in range(len(points)-1):
            p1 = points[i]
            p3 = points[i+1]
            p2 = (p1 + p3) * 0.5
            new_points.append(p1)
            new_points.append(p2)
        if len(points) > 1:
            new_points.append(p3)
        return new_points

    @staticmethod
    def points_smooth(points, swrink=False, inflate=True):
        vecs = [Vector((0, 0)) for _ in range(len(points))]
        for i in range(len(vecs) - 3):
            p0 = points[i ]
            p1 = points[i + 1]
            p2 = points[i + 2]
            d = (p1 - ((p0 + p2) * 0.5)) * 0.3
            if inflate:
                vecs[i] += d
                vecs[i + 2] += d
            if swrink:
                vecs[i + 1] -= d
        return [points[i] + vecs[i] for i in range(len(points))]

    def draw(self):
        self.renderer.clear()
        points = self.points.copy()
        points.append(self.mouse_co)
        for point in points:
            self.renderer.add_circle(point, 5, 6, self.seam_color)

        for i in range(self.spline_resolution):
            points = self.points_smooth(self.subdiv_points(points))

        for i in range(len(points) - 1):
            self.renderer.add_line(points[i], points[i + 1], self.color)

        self.renderer.update_batch

    def cut(self, context):
        points = self.points.copy()
        points.append(self.mouse_co)
        for i in range(self.spline_resolution):
            points = self.points_smooth(self.subdiv_points(points))
        cut(context, points, ciclic=False)


@register_class
class Slash(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.slash"
    bl_label = "Slash Cuter"
    bl_description = "Draw shapes to slice"
    bl_options = {"REGISTER", "UNDO"}
    default_tool = PolyCut
    _timer = None

    help_text = [
        "Mode: PolyLine = [D], Ellipse = [E], Rectangle = [R], Spline = [S]",
        "Move Around: [G]",
        "Toggle Ciclic: [C]",
        "Regular Mode: [Ctrl]",
        "Undo: [Ctrl] + [Z]"
    ]

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == "MESH"

    @classmethod
    def set_default_tool(cls, tool):
        cls.default_tool = tool

    def invoke(self, context, event):
        self.draw_callback_px = Draw2D()
        self.draw_callback_px.setup_handler()
        self.tool = self.default_tool(self.draw_callback_px)
        self.left = False
        self.right = False
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.value == "PRESS":
            if event.type == "E":
                self.tool = EllipseCut(self.draw_callback_px)
                self.set_default_tool(EllipseCut)

            elif event.type == "D":
                self.tool = PolyCut(self.draw_callback_px)
                self.set_default_tool(PolyCut)

            elif event.type == "R":
                self.tool = RectangleCut(self.draw_callback_px)
                self.set_default_tool(RectangleCut)

            elif event.type == "S":
                self.tool = SplineCut(self.draw_callback_px)
                self.set_default_tool(SplineCut)

        ret = self.tool.handle_event(context, event)
        self.tool.draw()

        n = len(self.help_text)
        for i, line in enumerate(self.help_text):
            self.draw_callback_px.add_text(line, (100, 20 * (n - i + 1)), 15, (1, 0.5, 0, 1))

        context.area.tag_redraw()

        if ret == {"FINISHED"} or ret == {"CANCELLED"}:
            self.draw_callback_px.remove_handler()
        return ret
