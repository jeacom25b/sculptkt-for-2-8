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
    bl_idname = "sculpttk.voxel_remesh"
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
        ob = context.active_object
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
            self._smooth_reproject(bm)
        surfacce_snap(bm.verts, tree)
        bm.to_mesh(ob.data)
        return {"FINISHED"}


@register_class
class CombRemesh(bpy.types.Operator):
    bl_idname = "sculpttk.comb_remesh"
    bl_label = "Comb Remesh"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    interations: bpy.props.IntProperty(
        name="Interations",
        description="How many times to repeat",
        min=1,
        default=10
    )

    detail: bpy.props.FloatProperty(
        name="Resolution",
        description="How dense the resulting mesh will be",
        min=0.0,
        default=40
    )

    def update_topology(self, bm, edge_size):
        upper_size = (edge_size * 1.5) ** 2
        lower_size = (edge_size * 0.6) ** 2

        subdivide = [edge for edge in bm.edges if edge_length_squared(edge) > upper_size]
        bmesh.ops.subdivide_edges(bm, edges=subdivide, cuts=1)
        bmesh.ops.triangulate(bm, faces=bm.faces)

        seen_verts = set()
        collapse = []
        for edge in bm.edges:
            if edge_length_squared(edge) < lower_size:
                verts = set(edge.verts)
                if not verts & seen_verts:
                    collapse.append(edge)
                    seen_verts |= verts

        bmesh.ops.collapse(bm, edges=collapse)
        bmesh.ops.dissolve_verts(bm, verts=[vert for vert in bm.verts if len(vert.link_edges) < 5])
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.beautify_fill(bm, faces=bm.faces)

    def relax_topology(self, bm, target_length):
        for vert in bm.verts:
            edge = max(vert.link_edges, key=edge_length_squared)
            other = edge.other_vert(vert)
            vec = (vert.co + other.co * 0.1) / 1.1
            vert.co = vec
            vec -= vert.co
            vec *= (vert.co - other.co).length - target_length
            vec -= vert.normal.dot(vec) * vert.normal
            vert.co += vec

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        ob = context.active_object
        size = max(ob.dimensions) / self.detail
        bm = bmesh.new()
        bm.from_mesh(ob.data)

        self.update_topology(bm, size)
        self.relax_topology(bm, size)
        bm.to_mesh(ob.data)
        context.area.tag_redraw()
        return {"FINISHED"}


@register_class
class Decimate(bpy.types.Operator):
    bl_idname = "sculpttk.decimate"
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
