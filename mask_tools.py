import bpy
import bmesh
from mathutils import Vector
from os import path
from .multifile import register_class

DEFORM_RIG_PATH = path.join(path.dirname(path.realpath(__file__)), "Mask Deform Rig.blend")


def create_object_from_bm(bm, matrix_world, name="new_mesh", set_active=False):
    mesh = bpy.data.meshes.new(name=name)
    bm.to_mesh(mesh)
    obj = bpy.data.objects.new(name=name, object_data=mesh)
    obj.matrix_world = matrix_world
    bpy.context.collection.objects.link(obj)
    if set_active:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    return obj


def get_bm_and_mask(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    layer = bm.verts.layers.paint_mask.verify()

    return bm, layer


@register_class
class MaskExtract(bpy.types.Operator):
    bl_idname = "sculpttk.mask_extract"
    bl_label = "Extract Mask"
    bl_description = "Extract and solidify Masked region as a new object"
    bl_options = {"REGISTER"}
    obj = None
    solidify = None
    smooth = None
    last_mouse = 0
    click_count = 0

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.active_object.type == "MESH"

    def execute(self, context):
        self.last_mode = context.active_object.mode
        self.click_count = 0

        bm, mask = get_bm_and_mask(context.active_object.data)

        bpy.ops.object.mode_set(mode="OBJECT")

        for vert in bm.verts:
            if vert[mask] < 0.5:
                bm.verts.remove(vert)
        remove = []
        dissolve = []
        for vert in bm.verts:
            if len(vert.link_faces) < 1:
                remove.append(vert)
            elif len(vert.link_faces) == 1:
                dissolve.append(vert)
        for vert in remove:
            bm.verts.remove(vert)

        bmesh.ops.dissolve_verts(bm, verts=dissolve)

        self.obj = create_object_from_bm(bm,
                                         context.active_object.matrix_world,
                                         context.active_object.name + "_Shell")
        bm.free()
        self.obj.select_set(True)
        context.view_layer.objects.active = self.obj

        self.displace = self.obj.modifiers.new(type="DISPLACE", name="DISPLACE")
        self.displace.strength = 0
        self.solidify = self.obj.modifiers.new(type="SOLIDIFY", name="Solidify")
        self.solidify.offset = 1
        self.solidify.thickness = 0
        self.smooth = self.obj.modifiers.new(type="SMOOTH", name="SMOOTH")
        self.smooth.iterations = 5

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        dist = context.region_data.view_distance

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self.click_count += 1
        elif event.type in {"ESC", "RIGHTMOUSE"}:
            self.click_count = 3

        if event.type == "MOUSEMOVE":
            delta = self.last_mouse - event.mouse_y
            self.last_mouse = event.mouse_y
            if self.click_count == 0:
                amount = dist * delta * (0.0001 if event.shift else 0.002)
                self.solidify.thickness += amount
                self.solidify.thickness = max(self.solidify.thickness, 0)

            elif self.click_count == 1:
                self.smooth.factor -= delta * (0.0001 if event.shift else 0.004)
                self.smooth.factor = max(self.smooth.factor, 0)

            elif self.click_count == 2:
                amount = dist * delta * (0.0001 if event.shift else 0.002)
                self.displace.strength -= amount

            elif self.click_count >= 3:
                bpy.ops.object.modifier_apply(modifier=self.displace.name)
                bpy.ops.object.modifier_apply(modifier=self.solidify.name)
                bpy.ops.object.modifier_apply(modifier=self.smooth.name)
                return {"FINISHED"}

        return {"RUNNING_MODAL"}


@register_class
class MaskSplit(bpy.types.Operator):
    bl_idname = "sculpttk.mask_split"
    bl_label = "Split Mask"
    bl_description = "Sepparate masked and unmasked regions into separate objects"
    bl_options = {"REGISTER", "UNDO"}

    def split(self, obj, compare):
        bm, mask = get_bm_and_mask(obj.data)
        for vert in bm.verts:
            if compare(vert[mask]):
                bm.verts.remove(vert)

        for vert in bm.verts:
            if len(vert.link_edges) < 3:
                bm.verts.remove(vert)
        out = bmesh.ops.holes_fill(bm, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=out["faces"])
        bm.to_mesh(obj.data)
        bm.free()

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.active_object.type == "MESH"

    def execute(self, context):

        old_obj = context.active_object
        bm = bmesh.new()
        bm.from_mesh(old_obj.data)
        new_obj = create_object_from_bm(bm, old_obj.matrix_world)
        self.split(new_obj, lambda v: v < 0.5)
        self.split(old_obj, lambda v: v >= 0.5)

        return {"FINISHED"}


@register_class
class MaskDeformRemove(bpy.types.Operator):
    bl_idname = "sculpttk.mask_deform_remove"
    bl_label = "Remove Mask Deform"
    bl_description = "Remove Mask Rig"
    bl_options = {"REGISTER", "UNDO"}

    apply: bpy.props.BoolProperty(
        name="Apply",
        description="Apply Mask deform before remove",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == "MESH"

    def execute(self, context):
        if not context.active_object.get("MASK_RIG", False):
            return {"CANCELLED"}

        if self.apply:
            bpy.ops.object.convert(target="MESH")

        for item in context.active_object["MASK_RIG"]:
            if type(item) == str:
                for md in context.active_object.modifiers:
                    if md.name == md:
                        if self.apply:
                            bpy.ops.object.modifier_apply(modifier=md.name)
                        else:
                            context.active_object.modifiers.remove(md)

            elif type(item) == bpy.types.Object:
                bpy.data.objects.remove(item)
        del context.active_object["MASK_RIG"]
        context.area.tag_redraw()
        return {"FINISHED"}


@register_class
class MaskDeformAdd(bpy.types.Operator):
    bl_idname = "sculpttk.mask_deform_add"
    bl_label = "Add Mask Deform"
    bl_description = "Add a rig to deform masked region"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.active_object.type == "MESH"

    def create_rig(self, context, ob, vg, location, radius=1):

        md = ob.modifiers.new(type="LATTICE", name="MASK_DEFORM")
        md.vertex_group = vg.name
        with bpy.types.BlendDataLibraries.load(DEFORM_RIG_PATH) as (data_from, data_to):
            data_to.objects = ["Lattice", "DeformPivot", "DeformManipulator"]
        for d_ob in data_to.objects:
            context.collection.objects.link(d_ob)
        md.object = data_to.objects[0]
        data_to.objects[0].hide_viewport = True
        data_to.objects[1].location = location
        ob["MASK_RIG"] = list(data_to.objects)
        ob["MASK_RIG"].append(md.name)

    def execute(self, context):
        bpy.ops.object.mode_set(mode="OBJECT")
        ob = context.active_object
        bm, mask = get_bm_and_mask(ob.data)
        vg = ob.vertex_groups.new(name="MASK_TO_VG")
        avg_location = Vector()
        total = 0
        for vert in bm.verts:
            vg.add([vert.index], weight=vert[mask], type="REPLACE")
            avg_location += vert.co * vert[mask]
            total += vert[mask]
        avg_location /= total
        self.create_rig(context, ob, vg, avg_location)

        return {"FINISHED"}


@register_class
class MaskDecimate(bpy.types.Operator):
    bl_idname = "sculpttk.mask_decimate"
    bl_label = "Mask Decimate"
    bl_description = "Decimate masked region"
    bl_options = {"REGISTER", "UNDO"}

    ratio: bpy.props.FloatProperty(
        name="Ratio",
        description="Amount of decimation",
        default=0.7
    )

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.active_object.type == "MESH"

    def invoke(self, context, event):
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.ed.undo_push()
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.ed.undo_push()
        ob = context.active_object
        vg = ob.vertex_groups.new(name="DECIMATION_VG")

        bm, mask = get_bm_and_mask(ob.data)
        for vert in bm.verts:
            vg.add([vert.index], weight=vert[mask], type="REPLACE")
        ob.vertex_groups.active = vg
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.decimate(ratio=self.ratio, use_vertex_group=True, vertex_group_factor=10)
        bpy.ops.object.mode_set(mode="OBJECT")
        ob.vertex_groups.remove(vg)
        context.area.tag_redraw()
        return {"FINISHED"}
