"""Blender 后台建模公共库：几何拼装、程序化材质、UV、烘焙（底色 + AO）、导出 glb。

坐标约定（Blender 内）：Z 向上，模型“正面”朝 +Y（导出 glTF 后即 Godot 的 -Z），单位米。
每个资源 = 若干 Part：
  * bake=True 的 Part 共用一张底色图和一张 AO 图、一个材质（M_<资源名>）；
  * bake=False 的 Part 保留自己的材质（玻璃）或没有材质（碰撞体，名字带 -convcolonly）。
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


# ---------------------------------------------------------------- 颜色与材质

def lin(c):
    """sRGB(0~1) → 线性。色板按 sRGB 写，进 Blender 前转换。"""
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# 名称 → (类型, 参数...)。颜色是 sRGB。
PALETTE = {
    # 木
    'wood_desk': ('wood', (0.86, 0.68, 0.46), (0.74, 0.54, 0.34), 1.0),
    'wood_dark': ('wood', (0.56, 0.36, 0.22), (0.44, 0.27, 0.16), 1.0),
    'wood_door': ('wood', (0.80, 0.62, 0.42), (0.68, 0.49, 0.31), 1.4),
    # 漆面金属
    'steel_frame': ('noise', (0.47, 0.61, 0.65), (0.44, 0.58, 0.62), 60.0),
    'steel_light': ('noise', (0.83, 0.83, 0.79), (0.80, 0.80, 0.76), 30.0),
    'steel_dark': ('flat', (0.28, 0.31, 0.33)),
    'alu': ('flat', (0.76, 0.78, 0.80)),
    'rubber': ('flat', (0.13, 0.13, 0.14)),
    # 黑板与粉笔
    'board_green': ('smudge', (0.13, 0.30, 0.23), (0.20, 0.38, 0.31), 2.5),
    'chalk': ('flat', (0.96, 0.96, 0.93)),
    'felt': ('flat', (0.25, 0.27, 0.30)),
    # 墙地
    'wall_white': ('flat', (0.93, 0.92, 0.88)),
    'wall_blue': ('flat', (0.56, 0.74, 0.80)),
    'trim': ('flat', (0.33, 0.47, 0.54)),
    'sill': ('noise', (0.86, 0.85, 0.82), (0.78, 0.77, 0.74), 12.0),
    'floor_tile': ('tile', (0.84, 0.82, 0.77), (0.66, 0.64, 0.60), 0.6),
    'window_frame': ('flat', (0.90, 0.91, 0.91)),
    # 杂项
    'white_plastic': ('flat', (0.94, 0.94, 0.92)),
    'beige_plastic': ('flat', (0.86, 0.81, 0.70)),
    'black': ('flat', (0.07, 0.07, 0.08)),
    'grill': ('flat', (0.22, 0.22, 0.24)),
    'clock_rim': ('flat', (0.78, 0.30, 0.26)),
    'fan_green': ('flat', (0.70, 0.82, 0.74)),
    'tube_white': ('flat', (0.98, 0.98, 0.96)),
    'book_red': ('flat', (0.76, 0.28, 0.24)),
    'book_blue': ('flat', (0.25, 0.42, 0.68)),
    'book_green': ('flat', (0.36, 0.62, 0.40)),
    'book_yellow': ('flat', (0.93, 0.78, 0.35)),
    'book_white': ('flat', (0.92, 0.91, 0.86)),
    'book_teal': ('flat', (0.25, 0.60, 0.62)),
    # 布 / 塑料 / 屏幕（宿舍、机房、食堂）
    'mattress': ('noise', (0.88, 0.89, 0.92), (0.84, 0.85, 0.88), 20.0),
    'blanket_blue': ('noise', (0.33, 0.50, 0.76), (0.29, 0.45, 0.70), 14.0),
    'pillow': ('flat', (0.95, 0.95, 0.93)),
    'screen': ('flat', (0.05, 0.06, 0.08)),
    'stainless': ('noise', (0.78, 0.79, 0.80), (0.72, 0.73, 0.75), 40.0),
    'plastic_orange': ('flat', (0.92, 0.55, 0.20)),
}


def _ramp(nt, src, a, b, lo=0.35, hi=0.65):
    r = nt.nodes.new('ShaderNodeValToRGB')
    r.color_ramp.elements[0].position = lo
    r.color_ramp.elements[0].color = (*lin(b), 1)
    r.color_ramp.elements[1].position = hi
    r.color_ramp.elements[1].color = (*lin(a), 1)
    nt.links.new(src, r.inputs['Fac'])
    return r.outputs['Color']


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 1.0
    if name == 'glass':
        bsdf.inputs['Base Color'].default_value = (*lin((0.72, 0.86, 0.90)), 1)
        bsdf.inputs['Alpha'].default_value = 0.28
        m.surface_render_method = 'BLENDED'
        return m
    spec = PALETTE[name]
    kind = spec[0]
    if kind == 'flat':
        bsdf.inputs['Base Color'].default_value = (*lin(spec[1]), 1)
        return m
    tc = nt.nodes.new('ShaderNodeTexCoord')
    a, b, s = spec[1], spec[2], spec[3]
    if kind == 'wood':
        # 沿 X 拉长的噪声 = 木纹
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (1.2 * s, 22 * s, 22 * s)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        wv = nt.nodes.new('ShaderNodeTexWave')
        wv.wave_type = 'BANDS'
        wv.bands_direction = 'Y'
        wv.inputs['Scale'].default_value = 0.5
        wv.inputs['Distortion'].default_value = 12.0
        wv.inputs['Detail'].default_value = 4.0
        wv.inputs['Detail Scale'].default_value = 1.5
        nt.links.new(mp.outputs['Vector'], wv.inputs['Vector'])
        col = _ramp(nt, wv.outputs['Fac'], a, b, 0.0, 0.45)  # 浅底 + 细深纹
    elif kind in ('noise', 'smudge'):
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = s
        nz.inputs['Detail'].default_value = 4.0 if kind == 'noise' else 8.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        col = _ramp(nt, nz.outputs['Fac'], a, b, 0.42, 0.62) if kind == 'noise' else _ramp(nt, nz.outputs['Fac'], a, b, 0.5, 0.75)
    elif kind == 'tile':
        br = nt.nodes.new('ShaderNodeTexBrick')
        br.offset = 0.0
        br.inputs['Color1'].default_value = (*lin(a), 1)
        br.inputs['Color2'].default_value = (*lin(tuple(x * 0.97 for x in a)), 1)
        br.inputs['Mortar'].default_value = (*lin(b), 1)
        br.inputs['Scale'].default_value = 1.0
        br.inputs['Mortar Size'].default_value = 0.004
        br.inputs['Brick Width'].default_value = s
        br.inputs['Row Height'].default_value = s
        nt.links.new(tc.outputs['Object'], br.inputs['Vector'])
        col = br.outputs['Color']
    else:
        raise ValueError(kind)
    nt.links.new(col, bsdf.inputs['Base Color'])
    return m


# ---------------------------------------------------------------- 几何

class Part:
    """一个导出对象。几何按材质索引累加到同一个 bmesh。坐标用资源坐标（世界），origin 是该对象的枢轴。"""

    def __init__(self, name, bake=True, origin=(0, 0, 0), parent=None):
        self.name = name
        self.bake = bake
        self.origin = Vector(origin)
        self.parent = parent
        self.bm = bmesh.new()
        self.mats = []
        self.obj = None

    def _merge(self, tmp, mat):
        if mat is not None:
            if mat not in self.mats:
                self.mats.append(mat)
            mi = self.mats.index(mat)
            for f in tmp.faces:
                f.material_index = mi
        me = bpy.data.meshes.new('_tmp')
        tmp.to_mesh(me)
        tmp.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        return self

    def box(self, size, loc, mat, bevel=0.004, rot=(0, 0, 0)):
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        bmesh.ops.scale(tmp, vec=Vector(size), verts=tmp.verts)
        bw = min(bevel, min(size) * 0.45)
        if bw > 0:
            bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=bw, segments=1, affect='EDGES', profile=0.5)
        if any(rot):
            bmesh.ops.rotate(tmp, verts=tmp.verts, cent=(0, 0, 0), matrix=Euler(rot).to_matrix())
        bmesh.ops.translate(tmp, verts=tmp.verts, vec=Vector(loc))
        return self._merge(tmp, mat)

    def cyl(self, r, p0, p1, mat, seg=12, r2=None):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        tmp = bmesh.new()
        bmesh.ops.create_cone(tmp, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=d.length)
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        bmesh.ops.rotate(tmp, verts=tmp.verts, cent=(0, 0, 0), matrix=q.to_matrix())
        bmesh.ops.translate(tmp, verts=tmp.verts, vec=(p0 + p1) / 2)
        return self._merge(tmp, mat)

    def tube(self, pts, r, mat, fillet=0.03, res=1):
        """沿折线的圆管（钢管家具），拐角自动倒圆。"""
        pts = _fillet([Vector(p) for p in pts], fillet)
        cu = bpy.data.curves.new('_c', 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = r
        cu.bevel_resolution = res
        cu.use_fill_caps = True
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p.x, p.y, p.z, 1)
        ob = bpy.data.objects.new('_c', cu)
        bpy.context.scene.collection.objects.link(ob)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        bpy.data.meshes.remove(me)
        return self._merge(tmp, mat)

    def build(self):
        bmesh.ops.translate(self.bm, verts=self.bm.verts, vec=-self.origin)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(get_mat(m))
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(35))
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        if self.parent is not None:
            ob.parent = self.parent.obj
            ob.location = self.origin - self.parent.origin
        else:
            ob.location = self.origin
        self.obj = ob
        return ob


def _fillet(pts, rad, n=4):
    if rad <= 0 or len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u, v = (a - b), (c - b)
        rr = min(rad, u.length * 0.45, v.length * 0.45)
        p0 = b + u.normalized() * rr
        p1 = b + v.normalized() * rr
        for k in range(n + 1):
            t = k / n  # 二次贝塞尔近似圆角
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1)
    out.append(pts[-1])
    return out


def collider(name, size, loc, parent=None, origin=(0, 0, 0)):
    """凸包碰撞体（Godot 导入时按 -convcolonly 后缀生成 StaticBody3D）。"""
    p = Part(name + '-convcolonly', bake=False, origin=origin, parent=parent)
    p.box(size, loc, None, bevel=0)
    return p


# ---------------------------------------------------------------- 烘焙与导出

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scn.cycles.device = 'GPU'
    except Exception:
        scn.cycles.device = 'CPU'
    if scn.world is None:
        scn.world = bpy.data.worlds.new('World')
    random.seed(7)


def _gltf_group():
    g = bpy.data.node_groups.get('glTF Material Output')
    if g:
        return g
    g = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    return g


def _set_bake_target(objs, img):
    for o in objs:
        for m in o.data.materials:
            nt = m.node_tree
            n = nt.nodes.get('BAKE') or nt.nodes.new('ShaderNodeTexImage')
            n.name = 'BAKE'
            n.image = img
            for x in nt.nodes:
                x.select = False
            n.select = True
            nt.nodes.active = n


def _select(objs, active=None):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def finish(name, parts, out_path, res=1024, ao_dist=0.4, tmp_dir=None):
    """构建全部 Part → UV → 烘焙底色 / AO → 换成单一材质 → 导出 glb。返回三角面数。"""
    for p in parts:
        p.build()
    bake_objs = [p.obj for p in parts if p.bake]
    other = [p.obj for p in parts if not p.bake]
    tmp_dir = tmp_dir or os.path.join(os.path.dirname(out_path), '.bake')
    os.makedirs(tmp_dir, exist_ok=True)

    # UV：所有烘焙对象一起展开，共用一张图
    _select(bake_objs)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')

    scn = bpy.context.scene
    for o in other:
        o.hide_render = True
    alb = bpy.data.images.new('albedo', res, res)  # Godot 解出贴图时命名为 <资源>_albedo.png
    ao = bpy.data.images.new('ao', res, res)
    ao.colorspace_settings.name = 'Non-Color'

    _select(bake_objs)
    _set_bake_target(bake_objs, alb)
    scn.cycles.samples = 4
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=True)
    _set_bake_target(bake_objs, ao)
    scn.cycles.samples = 64
    scn.world.light_settings.distance = ao_dist
    bpy.ops.object.bake(type='AO', margin=8, use_clear=True)

    os.makedirs(os.path.join(tmp_dir, name), exist_ok=True)
    for img in (alb, ao):
        img.filepath_raw = os.path.join(tmp_dir, name, img.name + '.png')  # glTF 图片名取文件名
        img.file_format = 'PNG'
        img.save()

    # 最终材质：底色图 + AO（glTF occlusion 通道）
    m = bpy.data.materials.new('M_' + name)
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Metallic'].default_value = 0.0
    ta = nt.nodes.new('ShaderNodeTexImage')
    ta.image = alb
    nt.links.new(ta.outputs['Color'], bsdf.inputs['Base Color'])
    to = nt.nodes.new('ShaderNodeTexImage')
    to.image = ao
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(to.outputs['Color'], sep.inputs['Color'])
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = _gltf_group()
    nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])
    for o in bake_objs:
        o.data.materials.clear()
        o.data.materials.append(m)
        for poly in o.data.polygons:
            poly.material_index = 0

    for o in other:
        o.hide_render = False
    all_objs = bake_objs + other
    _select(all_objs)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=out_path, export_format='GLB', use_selection=True, export_yup=True,
        export_apply=False, export_image_format='AUTO', export_texcoords=True, export_normals=True,
        export_materials='EXPORT', export_animations=False)
    tris = 0
    for o in bake_objs + [o for o in other if not o.name.endswith('-convcolonly')]:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    return tris
