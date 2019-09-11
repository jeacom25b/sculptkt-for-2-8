from .multifile import register_class
import bpy


@register_class
class SSmooth(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.s_smooth"
    bl_label = "Smooth"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    repeat: bpy.props.IntProperty(name="Repeat", default=10, min=1)
    factor: bpy.props.FloatProperty(name="Factor", default=0.5, min=0, max=1)
    recovery_repeat: bpy.props.IntProperty(name="Recovery Repeat", default=2, min=1)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        ob = context.active_object
        last_mode = ob.mode
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.duplicate()
        nob = context.active_object
        context.view_layer.objects.active = ob
        smooth = ob.modifiers.new(type="SMOOTH", name="Smooth")
        smooth.factor = self.factor
        smooth.iterations = self.repeat
        bpy.ops.object.modifier_apply(modifier=smooth.name)
        swrink = ob.modifiers.new(type="SHRINKWRAP", name="Snap")
        swrink.target = nob
        swrink.wrap_method="PROJECT"
        swrink.use_negative_direction = True
        swrink.use_positive_direction = True
        recover = ob.modifiers.new(type="CORRECTIVE_SMOOTH", name="recover")
        recover.iterations=self.recovery_repeat
        recover.smooth_type="LENGTH_WEIGHTED"
        recover.factor=1
        for sob in context.view_layer.objects.selected:
            sob.select_set(False)
        ob.select_set(True)
        bpy.ops.object.convert()
        bpy.data.meshes.remove(nob.data)
        bpy.ops.object.mode_set(mode=last_mode)
        return {"FINISHED"}
