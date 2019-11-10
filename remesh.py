import bpy
import bmesh
from .multifile import register_class
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import barycentric_transform
from random import shuffle, random


def is_mesh_pool(context):
    return context.active_object and context.active_object.type == "MESH"


def random_vector():
    return Vector((random() - 0.5, random() - 0.5, random() - 0.5,))


def surfacce_snap(vertices, tree):
    for vert in vertices:
        location, normal, index, dist = tree.find_nearest(vert.co)
        if location:
            vert.co = location


def average_vert_curvature(vert):
    return sum((abs(edge.other_vert(vert).normal.dot(vert.normal)) for edge in vert.link_edges)) / len(
        vert.link_edges)


def get_vert_curvature_vector(vert):
    other = min(vert.link_edges, key=lambda e: e.other_vert(vert).normal.dot(vert.normal)).other_vert(vert)
    return other.normal.cross(vert.normal)


def edge_length_squared(edge):
    return (edge.verts[0].co - edge.verts[1].co).length_squared


@register_class
class VoxelRemesh(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.voxel_remesh"
    bl_label = "Voxel Remesh"
    bl_description = "Remesh using remesh modifier."
    bl_options = {"REGISTER", "UNDO"}

    depth: bpy.props.IntProperty(
        name="Depth",
        description="The resolution relative to object bounding box",
        min=1,
        default=6
    )

    clean_topology: bpy.props.BoolProperty(
        name="Clean Topology",
        description="Run a cleaning algorith to make topology simpler and smoother",
        default=True
    )

    smooth_shading: bpy.props.BoolProperty(
        name="Smooth Shading",
        description="Add Smooth Shading",
        default=False
    )

    def _topology_optimize(self, bm):
        bm.verts.ensure_lookup_table()
        edge_counts = [len(vert.link_edges) for vert in bm.verts]

        mergeable_faces = {}
        star_faces = {}
        for face in bm.faces:
            three_edge_verts = []
            star_edge_verts = []
            for vert in face.verts:
                if edge_counts[vert.index] == 3:
                    three_edge_verts.append(vert)
                elif edge_counts[vert.index] == 6:
                    star_edge_verts.append(vert)
            if len(three_edge_verts) == 2:
                mergeable_faces[face] = three_edge_verts
            if len(star_edge_verts) == 2:
                star_faces[face] = star_edge_verts

        seen_verts = set()
        t_map = {}
        for face in mergeable_faces.keys():
            vert0 = mergeable_faces[face][0]
            vert1 = mergeable_faces[face][1]
            vert0.select = True
            vert1.select = True
            merge = True
            if face in star_faces:
                hex_face_count = 0
                for edge in face.edges:
                    for l_face in edge.link_faces:
                        if l_face is not face:
                            if l_face in star_faces:
                                hex_face_count += 1
                if hex_face_count > 2:
                    vec = vert0.co - vert1.co
                    if False in (abs(vec.z) > val for val in (abs(vec.x), abs(vec.y))):
                        merge = False
            if merge and vert0 not in seen_verts and vert1 not in seen_verts:
                seen_verts.add(vert0)
                seen_verts.add(vert1)
                co = (vert0.co + vert1.co) / 2
                vert0.co = co
                vert1.co = co
                t_map[vert0] = vert1
        bmesh.ops.weld_verts(bm, targetmap=t_map)

    def _smooth_reproject(self, bm):
        for vert in bm.verts:
            co = Vector()
            for edge in vert.link_edges:
                co += edge.other_vert(vert).co
            co /= len(vert.link_edges)
            co -= vert.co
            co -= vert.normal * vert.normal.dot(co)
            vert.co += co

    @classmethod
    def poll(cls, context):
        return is_mesh_pool(context)

    def invoke(self, context, event):
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.ed.undo_push()
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        for ob in context.view_layer.objects.selected:
            if not ob.type == "MESH":
                continue
            context.view_layer.objects.active = ob
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            tree = BVHTree.FromBMesh(bm)
            md = ob.modifiers.new(type="REMESH", name="Remesh")
            md.mode = "SMOOTH"
            md.mode = "SMOOTH"
            md.use_remove_disconnected = False
            md.octree_depth = self.depth
            bpy.ops.object.modifier_apply(modifier=md.name)
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            if self.clean_topology:
                self._topology_optimize(bm)
                self._topology_optimize(bm)
                self._smooth_reproject(bm)
            surfacce_snap(bm.verts, tree)
            bm.to_mesh(ob.data)
        if self.smooth_shading:
            bpy.ops.object.shade_smooth()
        return {"FINISHED"}


@register_class
class Decimate(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.decimate"
    bl_label = "Simple Decimate"
    bl_description = "Simple uniform decimation"
    bl_options = {"REGISTER", "UNDO"}

    ratio: bpy.props.FloatProperty(
        name="Ratio",
        description="Percentage to decimate",
        min=0,
        max=1,
        default=0.5
    )

    @classmethod
    def poll(cls, context):
        return is_mesh_pool(context)

    def invoke(self, context, event):
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.ed.undo_push()
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.ed.undo_push()
        ob = context.active_object
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.decimate(ratio=self.ratio)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {"FINISHED"}


# @register_class
class BoundaryLockedRemesh(bpy.types.Operator):
    bl_idname = "sculpt_tool_kit.bdremesh"
    bl_label = "Boundary Locked Remesh"
    bl_description = "Remesh meshes with boundaries"
    bl_options = {"REGISTER", "UNDO"}

    bm = None
    Iterations: bpy.props.IntProperty(name="Iterations", default=15)

    def pool(self, context):
        return context.active_object and context.active_object.type == "MESH"

    def execute(self, context):
        ob = context.active_object
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        for i in range(self.Iterations):
            self.edge_length_soften_from_bd(bm)
            self.edge_length_equalize(bm)
        bm.to_mesh(ob.data)
        bpy.context.area.tag_redraw()
        return {"FINISHED"}

    @staticmethod
    def edge_length_soften_from_bd(bm):
        seen_verts = set()
        split = []
        collapse = []
        e_lengths = [e.calc_length() for e in bm.edges]
        bm.edges.ensure_lookup_table()
        for edge in bm.edges:
            if edge.is_boundary:
                continue
            avg_le = 0
            tot = 0
            for face in edge.link_faces:
                for o_edge in face.edges:
                    if o_edge is not edge:
                        avg_le += e_lengths[o_edge.index]
                        tot += 1
            avg_le /= tot
            if e_lengths[edge.index] > 1.5 * avg_le:
                split.append(edge)

            elif e_lengths[edge.index] < 0.5 * avg_le:
                verts = set(edge.verts)
                if not verts & seen_verts and not True in (v.is_boundary for v in verts):
                    collapse.append(edge)
                    seen_verts |= verts

        bmesh.ops.collapse(bm, edges=collapse)
        bmesh.ops.subdivide_edges(bm, edges=[e for e in split if e.is_valid], cuts=1)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.dissolve_verts(bm, verts=[v for v in bm.verts if not v.is_boundary and len(v.link_edges) < 4])

    @staticmethod
    def edge_length_equalize(bm):
        for vert in bm.verts:
            if not vert.is_boundary:
                edge = max(vert.link_edges, key=lambda e: (e.other_vert(vert).co - vert.co).length_squared)
                d = vert.co - edge.other_vert(vert).co
                d -= vert.normal.dot(d) * vert.normal
                vert.co -= d * 0.05
