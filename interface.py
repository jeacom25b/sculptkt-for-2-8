import bpy
from .multifile import register_class, register_function, unregister_function, ReloadStorage
from .envelope_builder import get_armature_filenames


def space(layout, length=5):
    for _ in range(length):
        layout.separator()


def draw_mask_tools(layout, context):
    ob = context.active_object
    layout.label(text="Mask Tools")
    layout.operator("sculpttk.mask_extract")
    layout.operator("sculpttk.mask_split")
    layout.operator("sculpttk.mask_decimate")
    if ob:
        if not ob.get("MASK_RIG"):
            layout.operator("sculpttk.mask_deform_add")
        else:
            layout.operator("sculpttk.mask_deform_remove")


def draw_remesh_tools(layout, context):
    layout.label(text="Remesh")
    layout.operator("sculpttk.voxel_remesh")
    layout.operator("sculpttk.decimate")


def draw_booleans(layout, context):
    ob = context.active_object
    layout.label(text="Booleans")
    layout.operator("sculpttk.boolean", text="Union", icon="MOD_OPACITY").operation = "UNION"
    layout.operator("sculpttk.boolean", text="Difference", icon="MOD_BOOLEAN").operation = "DIFFERENCE"
    layout.operator("sculpttk.boolean", text="Intersect", icon="MOD_MASK").operation = "INTERSECT"
    layout.operator("sculpttk.slice_boolean", icon="MOD_MIRROR")
    layout.operator("sculpttk.slash", icon="GREASEPENCIL")


@register_class
class SCTK_PT_envelope_list(bpy.types.Panel):
    bl_idname = "sculpttk.envelope_list"
    bl_label = "Add Envelope Base"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout
        for file, name, path in reversed(list(get_armature_filenames())):
            row = layout.row(align=True)
            row.operator("sculpttk.load_envelope_armature", text=name, text_ctxt=path).type = file
            row.operator("sculpttk.delete_envelope_armature", text="", text_ctxt=path, icon="CANCEL").name = name


def draw_envelope_builder(layout, context):
    layout.label(text="Envelope Builder")
    layout.popover("sculpttk.envelope_list")
    layout.operator("sculpttk.save_envelope_armature")
    layout.operator("sculpttk.convert_envelope_armature")


class Self:
    def __init__(self, other_self):
        self.self = other_self

    def __getattr__(self, item):
        print(item)
        return self.self.__getattr__(item)


# I am lazy XD
@register_class
class SCTK_PT_brush_panel(bpy.types.Panel):
    bl_idname = "sculpttk.brush_panel"
    bl_label = "Brush"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    def __getattribute__(self, item):
        if item == "is_popover":
            return False
        else:
            return super().__getattribute__(item)

    def paint_settings(self, context):
        settings = bpy.types.VIEW3D_PT_tools_brush.paint_settings(context)
        return settings

    def draw(self, context):
        bpy.types.VIEW3D_PT_tools_brush.draw(self, context)


def draw_sculpt_panels(layout, context):
    layout.popover("sculpttk.brush_panel")
    layout.popover("VIEW3D_PT_tools_brush_texture")
    layout.popover("VIEW3D_PT_tools_brush_stroke")
    layout.popover("VIEW3D_PT_tools_brush_curve")
    layout.popover("VIEW3D_PT_sculpt_options")
    layout.popover("VIEW3D_PT_sculpt_dyntopo")
    layout.popover("VIEW3D_PT_sculpt_symmetry")


def draw_symmetry(layout, context):
    ob = context.active_object
    sculpt = context.scene.tool_settings.sculpt

    if ob and ob.mode == "SCULPT":
        layout.label(text="Symmetry")
        row = layout.row(align=True)
        row.prop(sculpt, "use_symmetry_x", text="X")
        row.prop(sculpt, "use_symmetry_y", text="Y")
        row.prop(sculpt, "use_symmetry_z", text="Z")

    layout.label(text="Symmetrize")
    identifiers = [sign + axis for sign in ("POSITIVE_", "NEGATIVE_") for axis in "XYZ"]
    texts = [sign + axis for sign in ("+ ", "- ") for axis in "XYZ"]
    row = layout.row()
    for i in range(6):
        if i % 3 == 0:
            col = row.column()
        col.operator("sculpttk.symmetrize", text=texts[i]).axis = identifiers[i]


@register_class
class SCTK_MT_sculpt_menu(bpy.types.Menu):
    bl_idname = "sculpttk.sculpt_menu"
    bl_label = "Sculpt"
    bl_region_type = "VIEW_3D"

    def draw(self, context):
        pie = self.layout.menu_pie()

        row = pie.row()

        box = row.box()
        draw_mask_tools(box, context)

        box = row.box()
        draw_remesh_tools(box, context)

        box = pie.box()
        draw_symmetry(box, context)

        box = pie.box()
        row = box.row()
        draw_sculpt_panels(row, context)

        pie.separator()


@register_class
class SCTK_MT_object_menu(bpy.types.Menu):
    bl_idname = "sculpttk.object_menu"
    bl_label = "Sculpt Toolkit Object menu"
    bl_region_type = "VIEW_3D"

    def draw(self, context):
        pie = self.layout.menu_pie()

        row = pie.row()

        col = row.column()
        box = col.box()
        draw_remesh_tools(box, context)

        box = row.box()
        draw_booleans(box, context)

        box = pie.box()
        draw_symmetry(box, context)

        pie.separator()

        box = col.box()
        draw_mask_tools(box, context)

        box = pie.box()
        draw_envelope_builder(box, context)


class SCKT_PT_panel_factory(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sculpt Tookit"

    drw_func = lambda layout, context: None

    @classmethod
    def create_panel(cls, label, draw_function, poll_function=None):
        class SCKT_PT_panel(cls):
            bl_idname = "sculpttk." + label.replace(" ", "_").lower()
            bl_label = label

            @classmethod
            def poll(cls, context):
                if poll_function:
                    return poll_function(cls, context)
                return True

            def draw(self, context):
                layout = self.layout
                draw_function(layout, context)

        return SCKT_PT_panel


register_class(SCKT_PT_panel_factory.create_panel("Booleans", draw_booleans))
register_class(SCKT_PT_panel_factory.create_panel("Envelope Builder", draw_envelope_builder))
register_class(SCKT_PT_panel_factory.create_panel("Mask Tools", draw_mask_tools))
register_class(SCKT_PT_panel_factory.create_panel("Remesh", draw_remesh_tools))
register_class(SCKT_PT_panel_factory.create_panel("Symmetry", draw_symmetry))

addon_keymaps = ReloadStorage.get("keymaps")


@register_function
def register():
    kcfg = bpy.context.window_manager.keyconfigs.addon
    if kcfg:
        for k in kcfg.keymaps:
            print(k)
        km = kcfg.keymaps.new(name='Sculpt', space_type="EMPTY")
        kmi = km.keymap_items.new("wm.call_menu_pie", type="W", alt=True, value="PRESS")
        kmi.properties.name = "sculpttk.sculpt_menu"
        addon_keymaps.append((km, kmi))

        km = kcfg.keymaps.new(name='Object Mode', space_type="EMPTY")
        kmi = km.keymap_items.new("wm.call_menu_pie", type="W", alt=True, value="PRESS")
        kmi.properties.name = "sculpttk.object_menu"
        addon_keymaps.append((km, kmi))


@unregister_function
def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
