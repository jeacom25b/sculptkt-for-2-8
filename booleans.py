import bpy
import bmesh
from .multifile import register_class


@register_class
class Boolean(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.boolean"
    bl_label = "Boolean"
    bl_description = "Boolean operation"
    bl_options = {"REGISTER", "UNDO"}

    operation: bpy.props.EnumProperty(
        items=(
            ("UNION", "Union", "Union"),
            ("INTERSECT", "Intersect", "Union"),
            ("DIFFERENCE", "Difference", "Difference"),
        ),
        name="Operation"
    )

    remove_objects: bpy.props.BoolProperty(
        name="Remove Objects",
        default=True
    )

    fix_ngons: bpy.props.FloatProperty(name="Fix Ngons", default=True)

    @classmethod
    def poll(cls, context):
        if context.active_object and context.active_object.type == "MESH":
            return len(context.view_layer.objects.selected) > 1

    def execute(self, context):
        objects = list(context.view_layer.objects.selected)
        active = context.view_layer.objects.active
        objects.remove(active)
        for obj in objects:
            if not obj.type == "MESH":
                continue
            md = active.modifiers.new(type="BOOLEAN", name="BOOL")
            md.object = obj
            md.operation = self.operation
            bpy.ops.object.modifier_apply(modifier=md.name)

        if self.fix_ngons:
            bm = bmesh.new()
            bm.from_mesh(active.data)
            n_gons = [face for face in bm.faces if len(face.verts) > 4]
            bmesh.ops.triangulate(bm, faces=n_gons)
            bm.to_mesh(active.data)

        if self.remove_objects:
            for obj in objects:
                if not obj.type == "MESH":
                    continue
                bpy.data.meshes.remove(obj.data)

        return {"FINISHED"}


@register_class
class Slice(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.slice_boolean"
    bl_label = "Mesh Slice"
    bl_description = "Cut selected objects using active object as a knife"
    bl_options = {"REGISTER", "UNDO"}

    thickness: bpy.props.FloatProperty(
        name="Thickness",
        default=0.0001,
        min=0.000001
    )

    remove_objects: bpy.props.BoolProperty(
        name="Remove Objects",
        default=False
    )

    @classmethod
    def poll(cls, context):
        if context.active_object and context.active_object.type == "MESH":
            return len(context.view_layer.objects.selected) > 1

    def execute(self, context):
        knife = context.active_object
        knife.select_set(False)
        objs = [obj for obj in context.view_layer.objects.selected if obj.type == "MESH" and obj is not knife]

        solid = knife.modifiers.new(type="SOLIDIFY", name="Solid")
        solid.thickness = self.thickness

        for obj in objs:
            context.view_layer.objects.active = obj
            bool = obj.modifiers.new(type="BOOLEAN", name="Bool")
            bool.operation = "DIFFERENCE"
            bool.object = knife
            bpy.ops.object.modifier_apply(modifier=bool.name)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.separate(type="LOOSE")
            bpy.ops.object.mode_set(mode="OBJECT")

        if self.remove_objects:
            bpy.data.meshes.remove(knife.data)
        else:
            knife.modifiers.remove(solid)

        return {"FINISHED"}
