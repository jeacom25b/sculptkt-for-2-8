import bpy
import bgl
import gpu
from mathutils import Vector
from gpu_extras.batch import batch_for_shader
from math import sin, cos, pi

bl_info = {
    'name': 'test',
    'description': 'test',
    'author': 'Jean Da Costa Machado',
    'version': (1, 5, 0),
    'blender': (2, 90, 0),
    'wiki_url': '',
    'category': 'Sculpt',
    'location': 'test'}

BLEND = 0
MULTIPLY_BLEND = 1
ADDITIVE_BLEND = 2

SMOOTH_3D_COLOR_VERT = '''

uniform mat4 ModelViewProjectionMatrix;

#ifdef USE_WORLD_CLIP_PLANES
uniform mat4 ModelMatrix;
#endif

in vec3 pos;
in vec4 color;
uniform float z_offset;

out vec4 finalColor;

void main()
{
  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
  gl_Position.z += z_offset;
  finalColor = color;

#ifdef USE_WORLD_CLIP_PLANES
  world_clip_planes_calc_clip_distance((ModelMatrix * vec4(pos, 1.0)).xyz);
#endif
}'''

SMOOTH_3D_COLOR_FRAG = '''


in vec4 finalColor;
out vec4 fragColor;

void main()
{
  fragColor = finalColor;
  fragColor = blender_srgb_to_framebuffer_space(fragColor);
}
'''

SMOOTH_3D_COLOR_FRAG_POINT = '''


in vec4 finalColor;
in vec4 fragCoord;
uniform float feather=0.5;
out vec4 fragColor;

void main()
{
  vec2 coord = (gl_PointCoord - vec2(0.5, 0.5)) * 2.0;
  float fac = 1 - dot(coord, coord);
  if (fac < 0){
    discard;
  }

  fragColor = finalColor;
  fragColor.w = min(fac / feather, 1);
  fragColor = blender_srgb_to_framebuffer_space(fragColor);
}
'''


class Draw3D:
    line_shader = gpu.types.GPUShader(
        SMOOTH_3D_COLOR_VERT, SMOOTH_3D_COLOR_FRAG)
    point_shader = gpu.types.GPUShader(
        SMOOTH_3D_COLOR_VERT, SMOOTH_3D_COLOR_FRAG_POINT)

    def __init__(self):
        self.line_verts = []
        self.line_colors = []
        self.points = []
        self.points_colors = []
        self.z_offset = -0.0002
        self.line_width = 2
        self.point_size = 5
        self.draw_handler = None
        self.depth_test = True

        self.line_batch = None
        self.point_batch = None
        self.blend_mode = BLEND

    def setup_handler(self):
        # Utility function to easily add it as a draw handler
        if not self.draw_handler:
            self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                self, (), "WINDOW", "POST_VIEW")

    def remove_handler(self):
        # Utility function to remove the handler
        if self.draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(
                self.draw_handler, "WINDOW")
            self.draw_handler = None

    def clear(self):
        self.points.clear()
        self.points_colors.clear()
        self.line_verts.clear()
        self.line_colors.clear()

    def add_point(self, pos, color=(1, 0, 0, 1)):
        self.points.append(pos)
        self.colors.append(color)

    def add_line(self, pa, pb, color_a=(1, 0, 0, 0), color_b=None):
        if not color_b:
            color_b = color_a

        self.line_verts.append(pa)
        self.line_verts.append(pb)
        self.line_colors.append(color_a)
        self.line_colors.append(color_b)

    def add_circle(self, center, normal, radius, resolution=20, color=(1, 0, 0, 1)):
        u = normal.orthogonal().normalized()
        v = u.cross(normal).normalized()
        for i in range(resolution):
            a = i / resolution * 2 * pi
            b = (i + 1) / resolution * 2 * pi
            self.add_line(u * sin(a) + v * cos(a) + center,
                          u * sin(b) + v * cos(b) + center,
                          color)

    def update_batch(self):
        self.line_batch = batch_for_shader(
            self.line_shader, 'LINES', {'pos': self.line_verts, 'color': self.line_colors})

        self.point_batch = batch_for_shader(
            self.line_shader, 'POINTS', {'pos': self.points, 'color': self.points_colors})

    def __call__(self, *args):
        self.draw()

    def draw(self):
        if self.depth_test:
            bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glEnable(bgl.GL_BLEND)

        if self.blend_mode == BLEND:
            bgl.glEnable(bgl.GL_BLEND)

        elif self.blend_mode == MULTIPLY_BLEND:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_DST_COLOR, bgl.GL_ZERO)

        elif self.blend_mode == ADDITIVE_BLEND:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE)

        if self.line_batch:
            self.line_shader.bind()
            self.line_shader.uniform_float('z_offset', self.z_offset)
            bgl.glLineWidth(self.line_width)
            self.line_batch.draw(self.line_shader)

        if self.point_batch:
            self.point_shader.bind()
            self.point_shader.uniform_float('z_offset', self.z_offset)
            bgl.glPointSize(self.point_size)
            self.point_batch.draw(self.point_shader)

        bgl.glDisable(bgl.GL_BLEND)
        if self.depth_test:
            bgl.glDisable(bgl.GL_DEPTH_TEST)


draw = Draw3D()


def register():
    draw.line_verts = [Vector((0, 0, 0)), Vector((0, 0, 1))]
    draw.line_colors = [(0, 0, 0, 1), (0, 0, 1, 1)]
    draw.points = [Vector((0, 0, 2)), Vector((0, 0, 3))]
    draw.points_colors = [(0, 0, 1, 1), (1, 0, 0, 1)]
    draw.add_circle(Vector((0, 0, 0)), Vector((0, 0, 1)), 1)
    draw.update_batch()
    draw.setup_handler()


def unregister():
    draw.remove_handler()
