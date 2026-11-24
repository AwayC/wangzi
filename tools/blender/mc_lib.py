"""MC 方块数据 → 校园模型。MC 只提供建筑的布局和体量，细节全部重新做，不是方块风格。由 build_mc_campus.py 调用，在 Blender 里运行。

建筑：
* 一格厚的墙 → 0.3 m 厚的真墙，沿 MC 墙线走；斜向台阶状的墙（圆弧立面）按对角线连成斜墙。
* 玻璃 → 窗：玻璃 + 窗框 + 中梃 + 窗台；门 → 门框 + 门扇 + 把手。
* 铁栏 / 栅栏 → 栏杆（扶手 + 立杆）；石墙 → 带压顶的矮墙。
* 成片的方块（楼板、屋面、柱墩、台阶）→ 实体，顶面按露天 / 室内分成屋面和地面材质。
* 圆塔、圆顶：按半径重新生成光滑的柱面 / 球面（材质按 MC 那一圈的方块取样）。
植物：
* 每棵树按 MC 的树干位置重新生成：渐细树干 + 分枝 + 几团树冠；树叶按离哪棵树近分配，相邻的树不会糊成一团。
* 不属于任何树的矮树叶 → 修剪过的绿篱（圆角）或灌木团，都落在下面的地面 / 台面上；悬空且下面没东西的丢掉。
* 草地靠草皮贴图，只在 MC 有高草和花的位置种草丛和花。
贴图：assets/env/campus/textures/（make_textures.py 生成），UV 按真实尺寸投影。
碰撞：同时生成一个 `-colonly` 网格（楼梯是斜坡；门、草、高处树冠不挡人）。

坐标：MC (x, y, z) → Blender (x, -z, y - 4)；导出后在 Godot 里是 (x, y - 4, z)。
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np

TEX_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'env', 'campus', 'textures'))
GROUND_Y = 4
T = 0.3  # 墙厚
PLATE_GAP = 0.6  # 薄楼板：整层 1 m 里空出下面 0.6 m，板厚 0.4 m

# ================================================================ 方块分类

PLANTS = {
    'grass', 'tall_grass', 'fern', 'large_fern', 'dandelion', 'poppy', 'azure_bluet', 'oxeye_daisy', 'cornflower', 'allium',
    'blue_orchid', 'red_tulip', 'orange_tulip', 'white_tulip', 'pink_tulip', 'lily_of_the_valley', 'lilac', 'rose_bush',
    'peony', 'sunflower', 'dead_bush', 'sugar_cane', 'brown_mushroom', 'seagrass', 'tall_seagrass', 'sea_pickle', 'lily_pad', 'vine',
}
FLOWER_COLOR = {
    'dandelion': (0.95, 0.82, 0.15), 'poppy': (0.85, 0.12, 0.10), 'azure_bluet': (0.92, 0.93, 0.96),
    'oxeye_daisy': (0.96, 0.95, 0.90), 'cornflower': (0.30, 0.45, 0.90), 'allium': (0.70, 0.45, 0.85),
    'blue_orchid': (0.25, 0.65, 0.90), 'red_tulip': (0.90, 0.20, 0.15), 'orange_tulip': (0.95, 0.55, 0.15),
    'white_tulip': (0.95, 0.95, 0.95), 'pink_tulip': (0.95, 0.60, 0.75), 'lily_of_the_valley': (0.95, 0.95, 0.95),
    'lilac': (0.80, 0.60, 0.90), 'rose_bush': (0.85, 0.15, 0.20), 'peony': (0.95, 0.65, 0.80),
}
SMALL = {
    'lever', 'end_rod', 'lantern', 'wall_torch', 'torch', 'tripwire', 'tripwire_hook', 'stone_pressure_plate', 'hopper',
    'lectern', 'cauldron', 'chest', 'cartography_table', 'zombie_head', 'bee_nest', 'moving_piston', 'light_gray_bed',
}
AIR = {'air', 'cave_air', 'void_air', 'bedrock'}


def parse(name):
    s = name.replace('minecraft:', '')
    props = {}
    if '[' in s:
        s, rest = s.split('[', 1)
        for kv in rest.rstrip(']').split(','):
            if '=' in kv:
                k, v = kv.split('=', 1)
                props[k] = v
    return s, props


def category(base):
    if base in AIR or 'coral' in base:
        return 'air'
    if base in PLANTS or base.endswith('_sapling'):
        return 'plant'
    if base == 'bamboo':
        return 'bamboo'
    if base.endswith('_leaves'):
        return 'leaves'
    if base.endswith('_log') or base.endswith('_wood') or base == 'mushroom_stem':
        return 'log'
    if base in ('water', 'bubble_column'):
        return 'water'
    if base.endswith('glass_pane'):
        return 'pane'
    if base.endswith('glass'):
        return 'glass'
    if base == 'iron_bars':
        return 'bars'
    if base.endswith('_fence'):
        return 'fence'
    if base.endswith('_wall') and not any(k in base for k in ('sign', 'banner', 'torch', 'fan')):
        return 'wall'
    if base.endswith('_slab'):
        return 'slab'
    if base.endswith('_stairs'):
        return 'stairs'
    if base.endswith('_trapdoor'):
        return 'trapdoor'
    if base.endswith('_door'):
        return 'door'
    if base.endswith('_carpet') or base == 'snow':
        return 'carpet'
    if base.endswith('_button') or base.endswith('_sign') or base.endswith('_banner') or base.startswith('potted_') or base in SMALL:
        return 'small'
    return 'solid'


# ================================================================ 材质

WORD = {
    'white': (0.94, 0.94, 0.92), 'orange': (0.90, 0.55, 0.20), 'magenta': (0.75, 0.35, 0.70), 'light_blue': (0.55, 0.72, 0.88),
    'yellow': (0.95, 0.84, 0.35), 'lime': (0.55, 0.78, 0.30), 'pink': (0.93, 0.65, 0.70), 'light_gray': (0.70, 0.70, 0.68),
    'gray': (0.42, 0.43, 0.45), 'cyan': (0.25, 0.58, 0.62), 'purple': (0.50, 0.30, 0.66), 'blue': (0.25, 0.32, 0.62),
    'brown': (0.48, 0.34, 0.22), 'green': (0.36, 0.48, 0.22), 'red': (0.70, 0.22, 0.18), 'black': (0.16, 0.16, 0.18),
}
TREE = {  # 树种 → (叶色乘数, 树皮色乘数)
    'oak': ((0.80, 0.95, 0.80), (1.0, 1.0, 1.0)), 'birch': ((1.05, 1.05, 0.85), (2.0, 2.0, 1.9)),
    'acacia': ((0.95, 1.0, 0.70), (1.1, 1.05, 1.0)), 'jungle': ((0.75, 1.05, 0.75), (1.0, 0.95, 0.85)),
    'spruce': ((0.60, 0.75, 0.65), (0.75, 0.7, 0.65)), 'dark_oak': ((0.65, 0.85, 0.60), (0.7, 0.65, 0.6)),
}
# 材质键 → (贴图, 平铺尺寸 m, 颜色乘数, 粗糙度, 金属度, 类型)
_MDEF = {
    'facade': ('facade_tile', 2.0, (1, 1, 1), 0.6, 0, 'solid'),
    'plaster': ('plaster', 4.0, (1, 1, 1), 0.9, 0, 'solid'),
    'concrete': ('concrete', 4.0, (1, 1, 1), 0.9, 0, 'solid'),
    'roof': ('roof', 4.0, (1, 1, 1), 0.95, 0, 'solid'),
    'roof_tile': ('roof_tile', 2.0, (1, 1, 1), 0.8, 0, 'solid'),
    'sandstone': ('plaster', 4.0, (0.98, 0.88, 0.66), 0.85, 0, 'solid'),
    'floor': ('paving', 2.0, (1.18, 1.18, 1.18), 0.5, 0, 'solid'),
    'paving': ('paving', 4.0, (1, 1, 1), 0.85, 0, 'solid'),
    'paving_light': ('paving', 4.0, (1.25, 1.25, 1.22), 0.85, 0, 'solid'),
    'plaza': ('plaza_stone', 4.0, (1, 1, 1), 0.85, 0, 'solid'),
    'asphalt': ('asphalt', 6.0, (1, 1, 1), 0.95, 0, 'solid'),
    'grass': ('grass', 4.0, (0.95, 0.92, 0.95), 1.0, 0, 'solid'),
    'soil': ('soil', 3.0, (1, 1, 1), 1.0, 0, 'solid'),
    'gravel': ('gravel', 2.0, (1, 1, 1), 1.0, 0, 'solid'),
    'stone': ('stone_wall', 3.0, (1, 1, 1), 0.95, 0, 'solid'),
    'wood': ('wood', 2.0, (1, 1, 1), 0.7, 0, 'solid'),
    'wood_dark': ('wood', 2.0, (0.55, 0.5, 0.48), 0.7, 0, 'solid'),
    'metal': ('metal', 2.0, (1, 1, 1), 0.4, 0.6, 'solid'),
    'metal_dark': ('metal', 2.0, (0.38, 0.40, 0.42), 0.45, 0.6, 'solid'),
    'frame': ('metal', 2.0, (0.92, 0.93, 0.94), 0.35, 0.5, 'solid'),
    'shutter': ('shutter', 2.0, (1, 1, 1), 0.5, 0.5, 'solid'),
    'water': ('water', 8.0, (1, 1, 1), 0.05, 0, 'water'),
    'glass': (None, 1, (0.70, 0.80, 0.86), 0.05, 0, 'glass'),
    'glass_blue': (None, 1, (0.45, 0.62, 0.82), 0.05, 0, 'glass'),
    'glass_dark': (None, 1, (0.25, 0.28, 0.32), 0.05, 0, 'glass'),
    'light': (None, 1, (1.0, 0.97, 0.90), 0.5, 0, 'emissive'),
    'light_warm': (None, 1, (1.0, 0.78, 0.45), 0.5, 0, 'emissive'),
    'flower_stem': (None, 1, (0.30, 0.50, 0.18), 1.0, 0, 'plant'),
    'grass_tuft': ('grass', 1.0, (0.85, 1.0, 0.8), 1.0, 0, 'plant'),
    'collision': (None, 1, (1, 0, 1), 1, 0, 'solid'),
    'red_sign': (None, 1, (0.72, 0.12, 0.10), 0.6, 0, 'solid'),
    'gold': (None, 1, (0.85, 0.68, 0.25), 0.35, 0.8, 'solid'),
    'awning': ('plaster', 2.0, (0.30, 0.45, 0.75), 0.8, 0, 'solid'),
}
for _w, _c in WORD.items():
    _MDEF['plaster_' + _w] = ('plaster', 4.0, tuple(v / 0.9 for v in _c), 0.9, 0, 'solid')
for _k, (_lc, _bc) in TREE.items():
    for _i, _f in enumerate((0.9, 1.0, 1.1)):
        _MDEF['leaves_%s_%d' % (_k, _i)] = ('leaves', 2.0, tuple(v * _f for v in _lc), 1.0, 0, 'solid')
    _MDEF['bark_' + _k] = ('bark', 1.5, _bc, 1.0, 0, 'solid')
_MDEF['hedge'] = ('leaves', 1.5, (0.80, 1.0, 0.75), 1.0, 0, 'solid')
for _n, _c in FLOWER_COLOR.items():
    _MDEF['flower_' + _n] = (None, 1, _c, 0.8, 0, 'plant')

_MATS = {}
_IMGS = {}
TILE = {}


def lin(c):
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def mat(key):
    """材质键 → Blender 材质（有贴图的走 UV；颜色乘数直接乘进贴图副本，glTF 导出不丢）。"""
    if key in _MATS:
        return _MATS[key]
    tex, tile, tint, rough, metal, kind = _MDEF.get(key, _MDEF['plaster'])
    m = bpy.data.materials.new('M_' + key)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    if tex:
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = _tinted_image(tex, tint)
        nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (*lin(tint), 1.0)
    if kind == 'glass':
        bsdf.inputs['Alpha'].default_value = 0.35
        m.blend_method = 'BLEND'
    elif kind == 'water':
        bsdf.inputs['Alpha'].default_value = 0.94
        m.blend_method = 'BLEND'
    elif kind == 'emissive':
        bsdf.inputs['Emission Color'].default_value = (*lin(tint), 1.0)
        bsdf.inputs['Emission Strength'].default_value = 2.0
    elif kind == 'plant':
        m.use_backface_culling = False
    TILE[m.name] = tile
    _MATS[key] = m
    return m


def _tinted_image(tex, tint):
    key = (tex, tuple(round(v, 3) for v in tint))
    if key in _IMGS:
        return _IMGS[key]
    src = bpy.data.images.load(os.path.join(TEX_DIR, tex + '.png'), check_existing=True)
    if tuple(tint) == (1, 1, 1):
        _IMGS[key] = src
        return src
    w, h = src.size
    px = np.empty(w * h * 4, np.float32)
    src.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    for i in range(3):
        px[:, i] = np.clip(px[:, i] * tint[i], 0, 1)
    name = '%s_%02x%02x%02x' % (tex, *(int(min(1.0, v / 2) * 255) for v in tint))
    path = os.path.join(TEX_DIR, 'tinted', name + '.png')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = bpy.data.images.new(name, w, h)
        img.pixels.foreach_set(px.ravel())
        img.filepath_raw = path
        img.file_format = 'PNG'
        img.save()
        bpy.data.images.remove(img)
    img = bpy.data.images.load(path, check_existing=True)
    _IMGS[key] = img
    return img


def block_mat(base, ground=False):
    """方块 → 材质键。ground：地面层（MC y ≤ 4）。"""
    b = base
    for suf in ('_slab', '_stairs', '_wall', '_fence', '_trapdoor', '_door', '_carpet', '_button', '_wall_sign', '_sign', '_pressure_plate'):
        if b.endswith(suf):
            b = b[: -len(suf)]
            break
    if b in ('quartz', 'smooth_quartz', 'quartz_block', 'quartz_pillar', 'chiseled_quartz_block', 'white_concrete'):
        return 'paving_light' if ground else 'facade'
    if b == 'snow_block':
        return 'paving_light' if ground else 'plaster'
    if b == 'light_gray_concrete':
        return 'paving' if ground else 'concrete'
    if b in ('gray_concrete', 'black_concrete'):
        return 'asphalt' if ground else ('plaster_gray' if b.startswith('gray') else 'plaster_black')
    if b == 'grass_block':
        return 'grass'
    if b in ('dirt', 'coarse_dirt', 'grass_path', 'farmland'):
        return 'soil'
    if b in ('gravel', 'sand'):
        return 'gravel'
    if b in ('stone_brick', 'stone_bricks', 'chiseled_stone_bricks', 'polished_andesite', 'andesite', 'diorite', 'polished_diorite',
             'polished_granite', 'smooth_stone', 'stone', 'cut_sandstone', 'sandstone'):
        return 'plaza' if ground else 'stone'
    if b in ('cobblestone', 'mossy_cobblestone', 'nether_brick'):
        return 'stone'
    if b in ('iron_block', 'iron'):
        return 'metal'
    if b == 'bookshelf' or b.startswith('dark_oak') or b.startswith('spruce'):
        return 'wood_dark'
    if b.endswith('_planks') or b in ('oak', 'birch', 'jungle', 'acacia', 'petrified_oak'):
        return 'wood'
    if b in ('glowstone', 'redstone_lamp', 'sea_lantern'):
        return 'light_warm'
    for w in sorted(WORD, key=len, reverse=True):
        if b.startswith(w + '_'):
            return 'plaster_' + w
    return 'plaster'


def glass_mat(base):
    if 'blue' in base or 'cyan' in base:
        return 'glass_blue'
    if 'black' in base or 'gray' in base:
        return 'glass_dark'
    return 'glass'


# ================================================================ 网格累加器（带 UV）

def to_bl(x, y, z):
    return (x, -z, y - GROUND_Y)


class MeshAcc:
    def __init__(self, uv=True):
        self.verts, self.faces, self.mat_idx, self.uvs = [], [], [], []
        self.mats, self._mi = [], {}
        self.uv = uv

    def _m(self, m):
        if m.name not in self._mi:
            self._mi[m.name] = len(self.mats)
            self.mats.append(m)
        return self._mi[m.name]

    def poly(self, pts, m, uvs=None):
        i = len(self.verts)
        self.verts.extend(pts)
        self.faces.append(tuple(range(i, i + len(pts))))
        self.mat_idx.append(self._m(m))
        if self.uv:
            self.uvs.extend(uvs if uvs else _project(pts, TILE.get(m.name, 1.0)))

    def box(self, x0, y0, z0, x1, y1, z1, m, skip=()):
        """MC 坐标轴对齐盒子。"""
        P = to_bl
        if '-y' not in skip:
            self.poly([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], m)
        if '+y' not in skip:
            self.poly([P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0)], m)
        if '-x' not in skip:
            self.poly([P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0)], m)
        if '+x' not in skip:
            self.poly([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], m)
        if '-z' not in skip:
            self.poly([P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0)], m)
        if '+z' not in skip:
            self.poly([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], m)

    def obox(self, cx, cz, length, width, y0, y1, ang, m):
        """绕竖轴旋转的盒子：中心 (cx, cz)，沿 ang 方向长 length、垂直方向宽 width（ang 从 +x 往 +z 转）。"""
        ca, sa = math.cos(ang), math.sin(ang)
        hl, hw = length / 2, width / 2
        cs = [(cx + ca * a - sa * b, cz + sa * a + ca * b) for a, b in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]
        P = to_bl
        bot = [P(x, y0, z) for x, z in cs]
        top = [P(x, y1, z) for x, z in cs]
        self.poly([top[0], top[3], top[2], top[1]], m)
        self.poly([bot[0], bot[1], bot[2], bot[3]], m)
        for i in range(4):
            j = (i + 1) % 4
            self.poly([bot[i], bot[j], top[j], top[i]], m)

    def build(self, name, coll, smooth=False):
        if not self.faces:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        for m in self.mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.mat_idx)
        if self.uv:
            uvl = me.uv_layers.new(name='UVMap')
            uvl.data.foreach_set('uv', np.array(self.uvs, np.float32).ravel())
        me.validate()
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        bm.to_mesh(me)
        bm.free()
        if smooth:
            me.shade_smooth()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def _project(pts, tile):
    """按面的朝向做平面投影 UV（Blender 坐标），tile = 一张贴图对应的米数。"""
    a, b, c = np.array(pts[0]), np.array(pts[1]), np.array(pts[-1])
    n = np.cross(b - a, c - a)
    ax = int(np.argmax(np.abs(n)))
    out = []
    for p in pts:
        if ax == 2:
            u, v = p[0], p[1]
        elif ax == 0:
            u, v = p[1], p[2]
        else:
            u, v = p[0], p[2]
        out.append((u / tile, v / tile))
    return out


# ================================================================ 贪心合并

def greedy2d(mask):
    rects, open_runs = [], {}
    H = mask.shape[0]
    for r in range(H + 1):
        runs = set()
        if r < H and mask[r].any():
            d = np.diff(np.concatenate(([0], mask[r].astype(np.int8), [0])))
            runs = set(zip(np.where(d == 1)[0].tolist(), np.where(d == -1)[0].tolist()))
        for k in list(open_runs):
            if k not in runs:
                rects.append((open_runs.pop(k), k[0], r, k[1]))
        for k in runs:
            if k not in open_runs:
                open_runs[k] = r
    return rects


def shift(a, axis, sign, fill):
    """每个格子看 axis 方向 sign 一侧的邻居值。"""
    out = np.full_like(a, fill)
    dst = [slice(None)] * 3
    src = [slice(None)] * 3
    if sign > 0:
        dst[axis], src[axis] = slice(0, -1), slice(1, None)
    else:
        dst[axis], src[axis] = slice(1, None), slice(0, -1)
    out[tuple(dst)] = a[tuple(src)]
    return out


def greedy_faces(acc, occ, hide, m, origin, face_mat=None, boundary_hidden=True, bottom_hidden=True, raise_bottom=0.0):
    """occ 的露出面合并成大面。face_mat(axis, sign, s, mask) 返回 None / 材质 / (mask_a, mat_a, mask_b, mat_b)。"""
    for axis in range(3):
        for sign in (-1, 1):
            fill = boundary_hidden
            if axis == 0:
                fill = False if sign > 0 else bottom_hidden
            face = occ & ~shift(hide, axis, sign, fill)
            if not face.any():
                continue
            for s in range(face.shape[axis]):
                sl = face[s] if axis == 0 else (face[:, s] if axis == 1 else face[:, :, s])
                if not sl.any():
                    continue
                mm = face_mat(axis, sign, s, sl) if face_mat else None
                if isinstance(mm, tuple):
                    for msk, mt in ((mm[0], mm[1]), (mm[2], mm[3])):
                        for r in greedy2d(msk):
                            _emit(acc, axis, sign, s, *r, origin, mt, raise_bottom)
                    continue
                for r in greedy2d(sl):
                    _emit(acc, axis, sign, s, *r, origin, mm or m, raise_bottom)


def _emit(acc, axis, sign, s, r0, c0, r1, c1, origin, m, rb=0.0):
    x0, y0, z0 = origin
    P = to_bl
    if axis == 0:
        y = y0 + s + (1 if sign > 0 else rb)
        a, b, c, d = (x0 + c0, z0 + r0), (x0 + c1, z0 + r0), (x0 + c1, z0 + r1), (x0 + c0, z0 + r1)
        pts = [P(a[0], y, a[1]), P(d[0], y, d[1]), P(c[0], y, c[1]), P(b[0], y, b[1])] if sign > 0 else \
              [P(a[0], y, a[1]), P(b[0], y, b[1]), P(c[0], y, c[1]), P(d[0], y, d[1])]
    elif axis == 1:
        z = z0 + s + (1 if sign > 0 else 0)
        ya, yb, xa, xb = y0 + r0 + rb, y0 + r1, x0 + c0, x0 + c1
        pts = [P(xa, ya, z), P(xb, ya, z), P(xb, yb, z), P(xa, yb, z)] if sign > 0 else \
              [P(xa, ya, z), P(xa, yb, z), P(xb, yb, z), P(xb, ya, z)]
    else:
        x = x0 + s + (1 if sign > 0 else 0)
        ya, yb, za, zb = y0 + r0 + rb, y0 + r1, z0 + c0, z0 + c1
        pts = [P(x, ya, za), P(x, yb, za), P(x, yb, zb), P(x, ya, zb)] if sign > 0 else \
              [P(x, ya, za), P(x, ya, zb), P(x, yb, zb), P(x, yb, za)]
    acc.poly(pts, m)


# ================================================================ 地块

FACING = {'north': (0, -1), 'south': (0, 1), 'west': (-1, 0), 'east': (1, 0)}
DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


class Plot:
    def __init__(self, scan_dir, spec):
        vol = np.load(os.path.join(scan_dir, 'blocks.npy'), mmap_mode='r')
        names = json.load(open(os.path.join(scan_dir, 'palette.json')))
        x0, z0, x1, z1 = spec['box']
        self.y_min = spec.get('y_min', 3)
        self.origin = (x0, self.y_min, z0)
        self.v = np.array(vol[self.y_min:spec.get('y_max', vol.shape[0]), z0:z1, x0:x1])
        self.v_orig = self.v.copy()
        self.parsed = [parse(n) for n in names]
        self.cat_of = np.array([category(p[0]) for p in self.parsed])
        self.spec = spec
        self.doors = []
        self.grass_id = next(i for i, p in enumerate(self.parsed) if p[0] == 'grass_block')
        for b in spec.get('strip', []):
            self._clear(b, keep_veg=True)
        for b in spec.get('clear', []):
            self._clear(b, keep_veg=False)
        for r in spec.get('replace', []):
            self._clear_cyl(r)
        self.roofs = [self._take_roof(rf) for rf in spec.get('roofs', [])]
        for b in spec.get('dry', []):
            sub = self.v[:, max(0, b[1] - z0):b[3] - z0, max(0, b[0] - x0):b[2] - x0]
            sub[self.cat_of[sub] == 'water'] = self.grass_id
        self.c = self.cat_of[self.v]
        self.rooms = []
        self.pane_id = next(i for i, p in enumerate(self.parsed) if p[0] == 'glass_pane')
        self.rings = [r for r in spec.get('replace', []) if r['type'] == 'tower' and 'ring_radius' in r]

    # ------------------------------------------------------------ 房间

    def detect_rooms(self, rules):
        """在每层楼板上方第 3 格（家具够不到、天花板下面那一格）找封闭的房间，按规则分类型。
        分了类型的房间清掉 MC 里的方块家具（之后在场景里摆套件家具）。楼梯间、不可进的楼不动。"""
        c, v = self.c, self.v
        X0, Y0, Z0 = self.origin
        Y, Z, X = v.shape
        struct = np.isin(c, ['solid', 'glass', 'pane', 'bars', 'fence', 'wall', 'door', 'leaves', 'log'])
        solid = c == 'solid'
        roof = solid | (c == 'small') | (c == 'slab')  # 天花板里嵌的灯、开关也算天花板
        for R in range(4, Y - 1):
            cand = ~struct[R] & solid[R - 3]
            if not cand.any():
                continue
            for cells in _components(cand):
                area = len(cells)
                if area < 12 or area > 2500:
                    continue
                zz, xx = cells[:, 0], cells[:, 1]
                if zz.min() == 0 or xx.min() == 0 or zz.max() == Z - 1 or xx.max() == X - 1:
                    continue
                ceil_l = R + 1 if roof[R + 1][zz, xx].mean() >= 0.85 else (R + 2 if R + 2 < Y and roof[R + 2][zz, xx].mean() >= 0.85 else -1)
                if ceil_l < 0:
                    continue
                if (c[R - 1:R + 1][:, zz, xx] == 'stairs').any():  # 高处有楼梯块 = 楼梯间（地上的楼梯块是椅子）
                    continue
                floor_top = Y0 + R - 3 + 1 - GROUND_Y  # 游戏高度
                fl = int(round((floor_top - 2) / 4.0)) + 1
                bx0, bz0, bx1, bz1 = int(xx.min()) + X0, int(zz.min()) + Z0, int(xx.max()) + 1 + X0, int(zz.max()) + 1 + Z0
                room = {'plot': self.spec['id'], 'box': [bx0, bz0, bx1, bz1], 'y': floor_top, 'ceil': Y0 + ceil_l - GROUND_Y + PLATE_GAP, 'floor': fl, 'area': area,
                        'fill': round(area / float((bx1 - bx0) * (bz1 - bz0)), 2)}
                room['type'] = _room_type(room, rules)
                # 摆家具用的矩形：先按 1F 高度的玻璃门 / 栏杆把阳台切开，取最大一块，再找里面最大的内接矩形
                low = np.isin(c[R - 2][zz, xx], ['glass', 'pane', 'door', 'bars', 'fence', 'wall'])
                low |= (c[R - 2][zz, xx] == 'solid') & np.isin(c[R - 1][zz, xx], ['solid', 'glass', 'pane'])  # 墙 / 柱 / 窗下墙
                m2 = np.zeros((Z, X), bool)
                m2[zz[~low], xx[~low]] = True
                parts = _components(m2)
                if parts:
                    big = max(parts, key=len)
                    m3 = np.zeros((Z, X), bool)
                    m3[big[:, 0], big[:, 1]] = True
                    rz0, rx0, rz1, rx1 = _max_rect(m3)
                    room['rect'] = [int(rx0 + X0), int(rz0 + Z0), int(rx1 + X0), int(rz1 + Z0)]
                if room['type'] and 'rect' in room:
                    rw, rd = room['rect'][2] - room['rect'][0], room['rect'][3] - room['rect'][1]
                    if min(rw, rd) < 2.5 or rw * rd < 0.5 * area:
                        room['type'] = ''
                doors = []
                cs = set(map(tuple, cells.tolist()))
                for (z, x) in cs:
                    for dx, dz in DIRS4:
                        zz2, xx2 = z + dz, x + dx
                        if 0 <= zz2 < Z and 0 <= xx2 < X and c[R - 2, zz2, xx2] == 'door':
                            doors.append([xx2 + X0 + 0.5, zz2 + Z0 + 0.5])
                room['doors'] = doors
                if room['type']:
                    # 封窗：房间边缘只有栏杆（上面敞开）的格子，栏杆以上补落地玻璃
                    inside = np.zeros((Z, X), bool)
                    inside[zz, xx] = True
                    edge = inside & ~(shift2(inside, 1, 0) & shift2(inside, -1, 0) & shift2(inside, 0, 1) & shift2(inside, 0, -1))
                    railed = edge & np.isin(c[R - 2], ['bars', 'pane', 'glass', 'fence', 'wall'])
                    for ly in (R - 1, R):
                        lay = v[ly]
                        open_ = railed & np.isin(c[ly], ['air', 'plant'])
                        lay[open_] = self.pane_id
                    # 窗户上方 MC 留的空格：窗往上延伸到顶
                    top_gap = edge & np.isin(c[R - 1], ['glass', 'pane']) & (c[R] == 'air')
                    v[R][top_gap] = self.pane_id
                    # 清家具：房间格子上方 3 层里的非结构方块
                    for ly in range(R - 2, R + 1):
                        layer = v[ly]
                        cats = c[ly][zz, xx]
                        kill = np.isin(cats, ['solid', 'slab', 'stairs', 'carpet', 'small', 'trapdoor', 'fence', 'bars', 'plant'])
                        layer[zz[kill], xx[kill]] = 0
                    # 天花板上嵌的灯 / 开关也清掉（套件会摆吸顶灯）
                    top = v[R + 1]
                    small = c[R + 1][zz, xx] == 'small'
                    if small.any():
                        nb = v[R + 1][zz[~small], xx[~small]]
                        top[zz[small], xx[small]] = np.bincount(nb).argmax() if len(nb) else 0
                self.rooms.append(room)
        self.c = self.cat_of[self.v]
        return self.rooms

    def _clear(self, b, keep_veg):
        X0, Y0, Z0 = self.origin
        bx0, bz0, bx1, bz1 = b[:4]
        ylo = b[4] if len(b) > 4 else Y0 + 2
        sub = self.v[max(0, ylo - Y0):, max(0, bz0 - Z0):bz1 - Z0, max(0, bx0 - X0):bx1 - X0]
        cats = self.cat_of[sub]
        kill = ~np.isin(cats, ['plant', 'leaves', 'log', 'bamboo', 'water']) if keep_veg else np.ones_like(cats, bool)
        sub[kill] = 0
        if ylo <= Y0 + 1:
            g = self.v[0, max(0, bz0 - Z0):bz1 - Z0, max(0, bx0 - X0):bx1 - X0]
            g[self.cat_of[g] != 'water'] = self.grass_id

    def _take_roof(self, rf):
        """坡屋顶：记下 box 范围里屋檐层以上每一列的顶面高度，然后把这些方块清掉，之后用连续斜面重做。"""
        X0, Y0, Z0 = self.origin
        bx0, bz0, bx1, bz1 = rf['box']
        sub = self.v[:, bz0 - Z0:bz1 - Z0, bx0 - X0:bx1 - X0]
        cats = self.cat_of[sub]
        occ = np.isin(cats, ['solid', 'slab', 'stairs'])
        ymin = rf.get('y_min', 8) - Y0
        cover = occ[ymin:].any(axis=0)
        total = cover.sum()
        eave = ymin
        for ly in range(ymin, occ.shape[0]):
            if occ[ly][cover].mean() >= rf.get('eave_cover', 0.6):
                eave = ly
                break
        top = np.full(cover.shape, np.nan)
        for lz, lx in np.argwhere(cover).tolist():
            col = np.where(occ[eave:, lz, lx])[0]
            if len(col) == 0:
                continue
            ly = eave + col.max()
            base, props = self.parsed[sub[ly, lz, lx]]
            h = ly + (0.5 if (category(base) == 'slab' and props.get('type') == 'bottom') else 1.0)
            top[lz, lx] = h + Y0
        sub[eave:][occ[eave:]] = 0
        return {'box': rf['box'], 'eave': eave + Y0, 'top': top, 'mat': rf.get('material', 'roof_tile')}

    def build_roofs(self, acc, col):
        """坡屋顶重做：格点高度取相邻格顶面的平均，连成连续斜面；底面是屋檐板，四周有封檐。"""
        cm = mat('collision')
        for rf in self.roofs:
            bx0, bz0 = rf['box'][0], rf['box'][1]
            top = rf['top']
            Zn, Xn = top.shape
            has = ~np.isnan(top)
            corner = np.zeros((Zn + 1, Xn + 1))
            for cz in range(Zn + 1):
                for cx in range(Xn + 1):
                    vals = [top[z, x] for z in (cz - 1, cz) for x in (cx - 1, cx) if 0 <= z < Zn and 0 <= x < Xn and has[z, x]]
                    if vals:
                        corner[cz, cx] = min(vals) if len(vals) < 4 else sum(vals) / 4.0
            eave = rf['eave']
            tm, um, fm = mat(rf['mat']), mat('wood_dark'), mat('wood_dark')
            for z, x in np.argwhere(has).tolist():
                X, Z = bx0 + x, bz0 + z
                h = [corner[z, x], corner[z, x + 1], corner[z + 1, x + 1], corner[z + 1, x]]
                pts = [(X, h[0], Z), (X + 1, h[1], Z), (X + 1, h[2], Z + 1), (X, h[3], Z + 1)]
                for a_ in (acc, col):
                    a_.poly([to_bl(*pts[0]), to_bl(*pts[3]), to_bl(*pts[2]), to_bl(*pts[1])], tm if a_ is acc else cm)
                acc.poly([to_bl(X, eave - 0.3, Z), to_bl(X + 1, eave - 0.3, Z), to_bl(X + 1, eave - 0.3, Z + 1), to_bl(X, eave - 0.3, Z + 1)], um)
                for (dx, dz), (i0, i1) in (((0, -1), (0, 1)), ((1, 0), (1, 2)), ((0, 1), (2, 3)), ((-1, 0), (3, 0))):
                    zz, xx = z + dz, x + dx
                    if 0 <= zz < Zn and 0 <= xx < Xn and has[zz, xx]:
                        continue
                    p0, p1 = pts[i0], pts[i1]
                    acc.poly([to_bl(p0[0], eave - 0.3, p0[2]), to_bl(p1[0], eave - 0.3, p1[2]), to_bl(p1[0], p1[1], p1[2]), to_bl(p0[0], p0[1], p0[2])], fm)

    def _clear_cyl(self, r):
        X0, Y0, Z0 = self.origin
        cx, cz, rad = r['center'][0], r['center'][1], r['radius']
        ya, yb = r.get('clear_y', r['y'])
        Y, Z, X = self.v.shape
        zz, xx = np.mgrid[0:Z, 0:X]
        msk = np.hypot(xx + X0 + 0.5 - cx, zz + Z0 + 0.5 - cz) <= rad + r.get('clear_pad', 0.9)
        for y in range(max(ya, Y0), min(yb + 1, Y0 + Y)):
            self.v[y - Y0][msk] = 0

    def sample(self, x, y, z):
        X0, Y0, Z0 = self.origin
        lx, ly, lz = x - X0, y - Y0, z - Z0
        if 0 <= ly < self.v_orig.shape[0] and 0 <= lz < self.v_orig.shape[1] and 0 <= lx < self.v_orig.shape[2]:
            return self.parsed[self.v_orig[ly, lz, lx]]
        return ('air', {})

    def _xyz(self, lx, ly, lz):
        return lx + self.origin[0], ly + self.origin[1], lz + self.origin[2]

    # ------------------------------------------------------------ 建筑

    def build(self, coll):
        """返回 (建筑对象, 碰撞累加器)。"""
        c, v = self.c, self.v
        Y, Z, X = v.shape
        acc = MeshAcc()
        col = MeshAcc(uv=False)
        cm = mat('collision')
        solid = c == 'solid'
        for idx in np.unique(v[c == 'slab']):
            if self.parsed[idx][1].get('type') == 'double':
                solid |= v == idx
        ground = np.zeros_like(solid)
        ground[:2] = True  # MC y=3、4：地面和铺装
        sq = solid & shift(solid, 2, 1, False) & shift(solid, 1, 1, False) & shift(shift(solid, 2, 1, False), 1, 1, False)
        mass = sq | shift(sq, 2, -1, False) | shift(sq, 1, -1, False) | shift(shift(sq, 2, -1, False), 1, -1, False)
        mass |= ground & solid
        thin = solid & ~mass
        glass = np.isin(c, ['glass', 'pane'])
        door = c == 'door'
        link = thin | glass | mass | door
        nlink = sum(shift(link, ax, sg, False).astype(np.int8) for ax in (1, 2) for sg in (-1, 1))
        lone = thin & (nlink == 0)
        mass |= lone
        thin &= ~lone
        # 薄楼板：上下都不是实体的整层楼板，只做顶上 0.4 m；下面的墙、窗往上长到板底，柱子顶上补一段
        plate = mass & ~shift(mass, 0, 1, False) & ~shift(mass, 0, -1, False)
        plate[:2] = False
        # 楼板层里嵌的灯 / 开关（四邻至少两格是楼板）→ 补成楼板，灯另外贴在板底
        nplate = sum(shift(plate, ax, sg, False).astype(np.int8) for ax in (1, 2) for sg in (-1, 1))
        holes = (c == 'small') & (nplate >= 2)
        self._ceiling_lights = [(lx, ly, lz) for ly, lz, lx in np.argwhere(holes & np.isin(v, [i for i, p in enumerate(self.parsed) if p[0] in ('end_rod', 'lantern')])).tolist()]
        if holes.any():
            for ly, lz, lx in np.argwhere(holes).tolist():
                for dx, dz in DIRS4:
                    if 0 <= lz + dz < Z and 0 <= lx + dx < X and plate[ly, lz + dz, lx + dx]:
                        v[ly, lz, lx] = v[ly, lz + dz, lx + dx]
                        break
            c[holes] = 'solid'
            solid |= holes
            mass |= holes
            plate |= holes
        # 圆塔四周的圆环阳台：环内的楼板格交给圆塔重做
        for r in self.rings:
            zz_, xx_ = np.mgrid[0:Z, 0:X]
            ring = np.hypot(xx_ + self.origin[0] + 0.5 - r['center'][0], zz_ + self.origin[2] + 0.5 - r['center'][1]) <= r['ring_radius']
            cut = plate & ring[None]
            plate &= ~cut
            mass &= ~cut
            solid &= ~cut
            v[cut] = 0
            c[cut] = 'air'
        self._mass, self._thin, self._glass, self._link, self._plate = mass, thin, glass, link, plate
        top = np.full((Z, X), -1)
        anys = solid.any(axis=0)
        top[anys] = Y - 1 - np.argmax(solid[::-1], axis=0)[anys]
        # ---- 实体：按材质合并；建筑部分的顶面分屋面（露天）和室内地面
        groups = {}
        for idx in np.unique(v[mass]):
            base, _ = self.parsed[idx]
            groups.setdefault((block_mat(base, False), block_mat(base, True)), []).append(idx)
        for (mk, gk), ids in groups.items():
            occ = np.isin(v, ids) & mass
            for is_ground, is_plate in ((True, False), (False, False), (False, True)):
                o = occ & (plate if is_plate else ~plate)
                if is_ground:
                    o[2:] = False
                else:
                    o[:2] = False
                if not o.any():
                    continue
                m = mat(gk if is_ground else mk)
                fm = None
                if not is_ground and mk not in ('wood', 'wood_dark', 'metal'):
                    def fm(axis, sign, s, sl, _top=top):
                        if axis != 0 or sign < 0:
                            return None
                        sky = _top == s
                        return (sl & sky, mat('roof'), sl & ~sky, mat('floor'))
                greedy_faces(acc, o, mass, m, self.origin, face_mat=fm, raise_bottom=PLATE_GAP if is_plate else 0.0)
            # 柱子 / 实墙顶上是薄楼板的，补到板底
            fill = occ & ~plate & shift(plate, 0, 1, False)
            fill[:1] = False
            for ly, lz, lx in np.argwhere(fill).tolist():
                x, y, z = self._xyz(lx, ly, lz)
                acc.box(x, y + 1, z, x + 1, y + 1 + PLATE_GAP, z + 1, mat(mk), skip=('-y', '+y'))
        greedy_faces(col, mass, mass, cm, self.origin)
        self._thin_walls(acc, col)
        self._windows(acc, col)
        self._rails(acc, col)
        water = c == 'water'
        if water.any():
            greedy_faces(acc, water, solid | water, mat('water'), self.origin)
            greedy_faces(col, water, solid | water, cm, self.origin)
        for y, z, x in np.argwhere(np.isin(c, ['slab', 'stairs', 'door', 'trapdoor', 'carpet', 'small'])).tolist():
            if c[y, z, x] == 'slab' and self.parsed[v[y, z, x]][1].get('type') == 'double':
                continue
            self._part(acc, col, x, y, z)
        self.build_roofs(acc, col)
        for lx, ly, lz in self._ceiling_lights:
            x, y, z = self._xyz(lx, ly, lz)
            acc.box(x + 0.08, y + PLATE_GAP - 0.03, z + 0.3, x + 0.92, y + PLATE_GAP, z + 0.7, mat('light'))
        return acc.build(self.spec['id'] + '_building', coll), col

    def _sig(self, lx, ly, lz):
        link = self._link
        Y, Z, X = link.shape

        def L(xx, zz):
            return 0 <= xx < X and 0 <= zz < Z and link[ly, zz, xx]
        orth = tuple(L(lx + dx, lz + dz) for dx, dz in DIRS4)
        diag = tuple(L(lx + dx, lz + dz) and not L(lx + dx, lz) and not L(lx, lz + dz) for dx, dz in DIAG)
        return (int(self.v[ly, lz, lx]), orth, diag)

    def _thin_walls(self, acc, col):
        thin = self._thin
        Y = thin.shape[0]
        cm = mat('collision')
        done = np.zeros_like(thin)
        for ly, lz, lx in np.argwhere(thin).tolist():
            if done[ly, lz, lx]:
                continue
            sig = self._sig(lx, ly, lz)
            ly1 = ly
            while ly1 + 1 < Y and thin[ly1 + 1, lz, lx] and not done[ly1 + 1, lz, lx] and self._sig(lx, ly1 + 1, lz) == sig:
                ly1 += 1
            done[ly:ly1 + 1, lz, lx] = True
            x, y0, z = self._xyz(lx, ly, lz)
            y1 = y0 + (ly1 - ly + 1) + (PLATE_GAP if ly1 + 1 < Y and self._plate[ly1 + 1, lz, lx] else 0)
            m = mat(block_mat(self.parsed[sig[0]][0]))
            _wall_piece(acc, x, z, y0, y1, sig[1], sig[2], m, T)
            _wall_piece(col, x, z, y0, y1, sig[1], sig[2], cm, T)

    def _windows(self, acc, col):
        """同一列连续的同种玻璃合成一扇窗：玻璃 + 窗框 / 中梃 + 窗台。"""
        glass, link = self._glass, self._link
        v = self.v
        Y, Z, X = v.shape
        frame = mat('frame')
        cm = mat('collision')
        done = np.zeros_like(glass)
        for ly, lz, lx in np.argwhere(glass).tolist():
            if done[ly, lz, lx]:
                continue
            gid = v[ly, lz, lx]
            ly1 = ly
            while ly1 + 1 < Y and glass[ly1 + 1, lz, lx] and v[ly1 + 1, lz, lx] == gid and not done[ly1 + 1, lz, lx]:
                ly1 += 1
            done[ly:ly1 + 1, lz, lx] = True
            x, y0, z = self._xyz(lx, ly, lz)
            y1 = y0 + (ly1 - ly + 1) + (PLATE_GAP if ly1 + 1 < Y and self._plate[ly1 + 1, lz, lx] else 0)
            base, props = self.parsed[gid]
            gm = mat(glass_mat(base))

            def L(xx, zz):
                return 0 <= xx < X and 0 <= zz < Z and link[ly, zz, xx]
            ex, wx, sz, nz = L(lx + 1, lz), L(lx - 1, lz), L(lx, lz + 1), L(lx, lz - 1)
            along_x, along_z = ex or wx, sz or nz
            if not along_x and not along_z:
                along_x = props.get('north') != 'true' and props.get('south') != 'true'
                along_z = not along_x
            cx, cz = x + 0.5, z + 0.5
            g = 0.02
            if along_x and not along_z:
                acc.box(x, y0, cz - g, x + 1, y1, cz + g, gm)
                col.box(x, y0, cz - 0.05, x + 1, y1, cz + 0.05, cm)
                self._frame(acc, frame, 'x', x, z, y0, y1, lx, ly, ly1, lz)
            elif along_z and not along_x:
                acc.box(cx - g, y0, z, cx + g, y1, z + 1, gm)
                col.box(cx - 0.05, y0, z, cx + 0.05, y1, z + 1, cm)
                self._frame(acc, frame, 'z', x, z, y0, y1, lx, ly, ly1, lz)
            else:
                acc.box(cx - 0.08, y0, cz - 0.08, cx + 0.08, y1, cz + 0.08, frame)
                if ex:
                    acc.box(cx, y0, cz - g, x + 1, y1, cz + g, gm)
                if wx:
                    acc.box(x, y0, cz - g, cx, y1, cz + g, gm)
                if sz:
                    acc.box(cx - g, y0, cz, cx + g, y1, z + 1, gm)
                if nz:
                    acc.box(cx - g, y0, z, cx + g, y1, cz, gm)
                col.box(x, y0, z, x + 1, y1, z + 1, cm)

    def _frame(self, acc, frame, axis, x, z, y0, y1, lx, ly, ly1, lz):
        glass = self._glass
        Y, Z, X = glass.shape
        fw, fd = 0.07, 0.12

        def G(xx, zz, yy):
            return 0 <= xx < X and 0 <= zz < Z and 0 <= yy < Y and glass[yy, zz, xx]
        above, below = G(lx, lz, ly1 + 1), G(lx, lz, ly - 1)
        if axis == 'x':
            c = z + 0.5
            for side, nb in ((x + 1, G(lx + 1, lz, ly)), (x, G(lx - 1, lz, ly))):
                w = 0.035 if nb else fw
                acc.box(side - w, y0, c - fd / 2, side + w, y1, c + fd / 2, frame)
            if not above:
                acc.box(x, y1 - fw, c - fd / 2, x + 1, y1, c + fd / 2, frame)
            if not below:
                acc.box(x, y0, c - fd / 2, x + 1, y0 + fw, c + fd / 2, frame)
                acc.box(x - 0.02, y0 - 0.06, c - 0.26, x + 1.02, y0, c + 0.26, mat('concrete'))
            if y1 - y0 >= 2:
                acc.box(x, y0 + 2.0 - 0.03, c - 0.04, x + 1, y0 + 2.0 + 0.03, c + 0.04, frame)
        else:
            c = x + 0.5
            for side, nb in ((z + 1, G(lx, lz + 1, ly)), (z, G(lx, lz - 1, ly))):
                w = 0.035 if nb else fw
                acc.box(c - fd / 2, y0, side - w, c + fd / 2, y1, side + w, frame)
            if not above:
                acc.box(c - fd / 2, y1 - fw, z, c + fd / 2, y1, z + 1, frame)
            if not below:
                acc.box(c - fd / 2, y0, z, c + fd / 2, y0 + fw, z + 1, frame)
                acc.box(c - 0.26, y0 - 0.06, z - 0.02, c + 0.26, y0, z + 1.02, mat('concrete'))
            if y1 - y0 >= 2:
                acc.box(c - 0.04, y0 + 2.0 - 0.03, z, c + 0.04, y0 + 2.0 + 0.03, z + 1, frame)

    def _rails(self, acc, col):
        """铁栏 / 栅栏 → 栏杆（扶手 + 立杆），石墙 → 带压顶的矮墙；竖向连续的合成一道高栏。"""
        c, v = self.c, self.v
        Y, Z, X = v.shape
        cm = mat('collision')
        rail = np.isin(c, ['bars', 'fence', 'wall'])
        conn = rail | self._link
        done = np.zeros_like(rail)
        for ly, lz, lx in np.argwhere(rail).tolist():
            if done[ly, lz, lx]:
                continue
            kind = c[ly, lz, lx]
            ly1 = ly
            while ly1 + 1 < Y and c[ly1 + 1, lz, lx] == kind and not done[ly1 + 1, lz, lx]:
                ly1 += 1
            done[ly:ly1 + 1, lz, lx] = True
            x, y0, z = self._xyz(lx, ly, lz)
            y1 = y0 + (ly1 - ly + 1) * (0.9 if kind == 'wall' else 1.0)
            base = self.parsed[v[ly, lz, lx]][0]

            def L(xx, zz):
                return 0 <= xx < X and 0 <= zz < Z and conn[ly, zz, xx]
            arms = [(dx, dz) for dx, dz in DIRS4 if L(lx + dx, lz + dz)]
            cx, cz = x + 0.5, z + 0.5
            if kind == 'wall':
                sm = mat(block_mat(base))
                acc.box(cx - 0.22, y0, cz - 0.22, cx + 0.22, y1 - 0.08, cz + 0.22, sm)
                for dx, dz in arms:
                    acc.box(min(cx, cx + dx * 0.5) - (0.18 if dx == 0 else 0), y0, min(cz, cz + dz * 0.5) - (0.18 if dz == 0 else 0),
                            max(cx, cx + dx * 0.5) + (0.18 if dx == 0 else 0), y1 - 0.08, max(cz, cz + dz * 0.5) + (0.18 if dz == 0 else 0), sm)
                    acc.box(min(cx, cx + dx * 0.5) - (0.25 if dx == 0 else 0), y1 - 0.08, min(cz, cz + dz * 0.5) - (0.25 if dz == 0 else 0),
                            max(cx, cx + dx * 0.5) + (0.25 if dx == 0 else 0), y1, max(cz, cz + dz * 0.5) + (0.25 if dz == 0 else 0), mat('concrete'))
                acc.box(cx - 0.25, y1 - 0.08, cz - 0.25, cx + 0.25, y1, cz + 0.25, mat('concrete'))
                col.box(x, y0, z, x + 1, y1, z + 1, cm)
                continue
            rm = mat('wood' if kind == 'fence' and ('oak' in base or 'spruce' in base or 'birch' in base) else 'metal_dark')
            acc.box(cx - 0.04, y0, cz - 0.04, cx + 0.04, y1, cz + 0.04, rm)
            for dx, dz in arms:
                ex, ez = cx + dx * 0.5, cz + dz * 0.5
                for yy, th in ((y1 - 0.04, 0.04), (y0 + 0.1, 0.02)):
                    acc.box(min(cx, ex) - (0.03 if dx == 0 else 0), yy - th, min(cz, ez) - (0.03 if dz == 0 else 0),
                            max(cx, ex) + (0.03 if dx == 0 else 0), yy + th, max(cz, ez) + (0.03 if dz == 0 else 0), rm)
                for k in (1, 2, 3):
                    px, pz = cx + dx * 0.125 * k, cz + dz * 0.125 * k
                    acc.box(px - 0.01, y0 + 0.1, pz - 0.01, px + 0.01, y1 - 0.04, pz + 0.01, rm)
                col.box(min(cx, ex) - (0.06 if dx == 0 else 0), y0, min(cz, ez) - (0.06 if dz == 0 else 0),
                        max(cx, ex) + (0.06 if dx == 0 else 0), max(y1, y0 + 1.1), max(cz, ez) + (0.06 if dz == 0 else 0), cm)

    def _part(self, acc, col, lx, ly, lz):
        x, y, z = self._xyz(lx, ly, lz)
        base, props = self.parsed[self.v[ly, lz, lx]]
        cat = self.c[ly, lz, lx]
        cm = mat('collision')
        m = mat(block_mat(base, ly < 2))
        if cat == 'slab':
            if props.get('type') == 'top':
                acc.box(x, y + 0.5, z, x + 1, y + 1, z + 1, m)
                col.box(x, y + 0.5, z, x + 1, y + 1, z + 1, cm)
            else:
                acc.box(x, y, z, x + 1, y + 0.5, z + 1, m)
                col.box(x, y, z, x + 1, y + 0.5, z + 1, cm)
        elif cat == 'stairs':
            dx, dz = FACING.get(props.get('facing', 'north'), (0, -1))
            below = self.c[ly - 1, lz, lx] if ly > 0 else 'solid'
            if props.get('half') != 'top' and below not in ('solid', 'slab', 'stairs') and ly >= 3:
                # 下面悬空的楼梯块 = 坡屋顶的一段：做成斜面（青瓦），不是台阶
                _ramp(acc, x, y, z, dx, dz, mat('roof_tile'))
                _ramp(col, x, y, z, dx, dz, cm)
                return
            if props.get('half') == 'top':
                acc.box(x, y + 0.5, z, x + 1, y + 1, z + 1, m)
                col.box(x, y, z, x + 1, y + 1, z + 1, cm)
                return
            # 每格四级小踏步（0.25 高 × 0.25 深），高的一边在 facing 一侧
            for k in range(4):
                f0 = k / 4
                yy = y + (k + 1) * 0.25
                if dx > 0:
                    acc.box(x + f0, y, z, x + 1, yy, z + 1, m)
                elif dx < 0:
                    acc.box(x, y, z, x + 1 - f0, yy, z + 1, m)
                elif dz > 0:
                    acc.box(x, y, z + f0, x + 1, yy, z + 1, m)
                else:
                    acc.box(x, y, z, x + 1, yy, z + 1 - f0, m)
            _ramp(col, x, y, z, dx, dz, cm)
        elif cat == 'door':
            if props.get('half') != 'upper':
                self._door(acc, x, y, z, base, props)
        elif cat == 'trapdoor':
            if props.get('half') == 'top':
                acc.box(x, y + 0.85, z, x + 1, y + 1, z + 1, mat('wood'))
            elif props.get('open') != 'true':
                acc.box(x, y, z, x + 1, y + 0.15, z + 1, mat('wood'))
        elif cat == 'carpet':
            acc.box(x + 0.02, y, z + 0.02, x + 0.98, y + 0.03, z + 0.98, mat('plaster' if base == 'snow' else block_mat(base)), skip=('-y',))
        elif cat == 'small':
            if ly + 1 < self.v.shape[0] and self._plate[ly + 1, lz, lx]:
                y += PLATE_GAP
            if base == 'end_rod':
                acc.box(x + 0.1, y + 0.94, z + 0.35, x + 0.9, y + 1.0, z + 0.65, mat('light'))
            elif base == 'lantern':
                acc.box(x + 0.32, y + 0.1, z + 0.32, x + 0.68, y + 0.55, z + 0.68, mat('light_warm'))
                acc.box(x + 0.28, y + 0.55, z + 0.28, x + 0.72, y + 0.62, z + 0.72, mat('metal_dark'))
            elif base == 'wall_torch':
                acc.box(x + 0.4, y + 0.3, z + 0.4, x + 0.6, y + 0.75, z + 0.6, mat('light_warm'))
            elif base.endswith('_button') or base == 'lever':
                acc.box(x + 0.4, y + 0.38, z + 0.4, x + 0.6, y + 0.6, z + 0.6, mat('plaster'))
            elif base.endswith('_sign') or base.endswith('_banner'):
                acc.box(x + 0.05, y + 0.3, z + 0.45, x + 0.95, y + 0.85, z + 0.55, mat('wood'))
            elif base in ('tripwire', 'stone_pressure_plate', 'tripwire_hook'):
                return
            elif base.startswith('potted_'):
                acc.box(x + 0.32, y, z + 0.32, x + 0.68, y + 0.38, z + 0.68, mat('plaster_brown'))
                fl = base.replace('potted_', '')
                acc.box(x + 0.4, y + 0.38, z + 0.4, x + 0.6, y + 0.7, z + 0.6, mat('flower_' + fl if fl in FLOWER_COLOR else 'flower_stem'))
            else:
                acc.box(x + 0.1, y, z + 0.1, x + 0.9, y + 0.8, z + 0.9, mat('wood_dark' if base in ('chest', 'lectern', 'cartography_table') else 'metal'))

    def _door(self, acc, x, y, z, base, props):
        dx, dz = FACING.get(props.get('facing', 'north'), (0, -1))
        leaf = mat('metal' if base == 'iron_door' else 'wood')
        frame = mat('frame' if base == 'iron_door' else 'wood_dark')
        cx, cz = x + 0.5, z + 0.5
        h = 2.0
        if dz != 0:
            acc.box(x + 0.04, y, cz - 0.03, x + 0.96, y + h - 0.06, cz + 0.03, leaf)
            for sx in (x, x + 0.96):
                acc.box(sx, y, cz - T / 2, sx + 0.04, y + h, cz + T / 2, frame)
            acc.box(x, y + h - 0.06, cz - T / 2, x + 1, y + h, cz + T / 2, frame)
            hx = x + (0.85 if props.get('hinge') == 'left' else 0.15)
            acc.box(hx - 0.06, y + 1.0, cz - 0.07, hx + 0.06, y + 1.04, cz + 0.07, mat('metal'))
        else:
            acc.box(cx - 0.03, y, z + 0.04, cx + 0.03, y + h - 0.06, z + 0.96, leaf)
            for sz in (z, z + 0.96):
                acc.box(cx - T / 2, y, sz, cx + T / 2, y + h, sz + 0.04, frame)
            acc.box(cx - T / 2, y + h - 0.06, z, cx + T / 2, y + h, z + 1, frame)
            hz = z + (0.85 if props.get('hinge') == 'left' else 0.15)
            acc.box(cx - 0.07, y + 1.0, hz - 0.06, cx + 0.07, y + 1.04, hz + 0.06, mat('metal'))
        self.doors.append({'pos': [cx, y - GROUND_Y, cz], 'facing': props.get('facing'), 'type': base})

    # ------------------------------------------------------------ 植物

    def build_vegetation(self, coll, col):
        c, v = self.c, self.v
        Y, Z, X = v.shape
        rng = np.random.default_rng(sum(map(ord, self.spec['id'])))
        support = np.isin(c, ['solid', 'slab', 'stairs', 'glass', 'water'])
        leaves = c == 'leaves'
        out = []
        # ---- 树：原木连通块 = 一棵树
        log_set = {tuple(p) for p in np.argwhere(c == 'log').tolist()}
        trees, seen = [], set()
        for p in sorted(log_set):
            if p in seen:
                continue
            comp, stack = [], [p]
            seen.add(p)
            while stack:
                q = stack.pop()
                comp.append(q)
                for d in N6:
                    r = (q[0] + d[0], q[1] + d[1], q[2] + d[2])
                    if r in log_set and r not in seen:
                        seen.add(r)
                        stack.append(r)
            trees.append(comp)
        # 树叶归属：所有树同时向外扩（最远 5 格），先到先得
        owner = -np.ones(v.shape, np.int32)
        frontier = []
        for ti, comp in enumerate(trees):
            for q in comp:
                owner[q] = ti
                frontier.append(q)
        for _ in range(5):
            nxt = []
            for q in frontier:
                for d in N6:
                    r = (q[0] + d[0], q[1] + d[1], q[2] + d[2])
                    if 0 <= r[0] < Y and 0 <= r[1] < Z and 0 <= r[2] < X and leaves[r] and owner[r] < 0:
                        owner[r] = owner[q]
                        nxt.append(r)
            frontier = nxt
        trunk_acc, crown_acc = MeshAcc(), MeshAcc()
        for ti, comp in enumerate(trees):
            self._tree(trunk_acc, crown_acc, col, comp, np.argwhere((owner == ti) & leaves), rng)
        for a, name, sm in ((trunk_acc, '_trunks', True), (crown_acc, '_crowns', True)):
            ob = a.build(self.spec['id'] + name, coll, smooth=sm)
            if ob:
                out.append(ob)
        # ---- 剩下的树叶：绿篱 / 灌木
        hedge_acc, shrub_acc = MeshAcc(), MeshAcc()
        self._hedges(hedge_acc, shrub_acc, col, leaves & (owner < 0), support, rng)
        ob = hedge_acc.build(self.spec['id'] + '_hedges', coll)
        if ob:
            _round_edges(ob, 0.2)
            out.append(ob)
        ob = shrub_acc.build(self.spec['id'] + '_shrubs', coll, smooth=True)
        if ob:
            out.append(ob)
        # ---- 竹子
        bam = MeshAcc()
        for ly, lz, lx in np.argwhere(c == 'bamboo').tolist():
            x, y, z = self._xyz(lx, ly, lz)
            _cyl_between(bam, (x + 0.5, y, z + 0.5), (x + 0.5, y + 1, z + 0.5), 0.06, 0.06, mat('flower_stem'), 6)
            if ly + 1 >= Y or c[ly + 1, lz, lx] != 'bamboo':
                _blob(bam, x + 0.5, y + 0.7, z + 0.5, 0.7, 0.5, mat('leaves_jungle_1'), rng, sub=1)
        ob = bam.build(self.spec['id'] + '_bamboo', coll)
        if ob:
            out.append(ob)
        # ---- 高草、花（矮草靠草皮贴图，只稀疏种一些）
        pl = MeshAcc()
        for ly, lz, lx in np.argwhere(c == 'plant').tolist():
            base, props = self.parsed[v[ly, lz, lx]]
            if props.get('half') == 'upper' or base in ('seagrass', 'tall_seagrass', 'sea_pickle', 'lily_pad', 'vine'):
                continue
            if ly == 0 or not support[ly - 1, lz, lx]:
                continue
            x, y, z = self._xyz(lx, ly, lz)
            if base == 'grass' and rng.random() > 0.2:
                continue
            if base in FLOWER_COLOR:
                for _ in range(3):
                    fx, fz = x + 0.2 + rng.random() * 0.6, z + 0.2 + rng.random() * 0.6
                    hh = 0.3 + rng.random() * 0.25
                    _blade(pl, fx, y, fz, rng.random() * math.pi, 0.05, hh, mat('flower_stem'))
                    pl.box(fx - 0.06, y + hh, fz - 0.06, fx + 0.06, y + hh + 0.07, fz + 0.06, mat('flower_' + base))
            else:
                tall = base in ('tall_grass', 'large_fern', 'sugar_cane')
                for _ in range(5 if tall else 3):
                    fx, fz = x + 0.15 + rng.random() * 0.7, z + 0.15 + rng.random() * 0.7
                    _blade(pl, fx, y, fz, rng.random() * math.pi, 0.16, (0.8 if tall else 0.3) * (0.7 + rng.random() * 0.6), mat('grass_tuft'))
        ob = pl.build(self.spec['id'] + '_plants', coll)
        if ob:
            out.append(ob)
        return out

    def _tree(self, tacc, cacc, col, comp, leaf_pts, rng):
        X0, Y0, Z0 = self.origin
        names = [self.parsed[self.v[q]][0] for q in comp]
        kind = max(set(names), key=names.count).replace('stripped_', '').replace('_log', '').replace('_wood', '')
        kind = kind if kind in TREE else 'oak'
        vert = [q for q in comp if self.parsed[self.v[q]][1].get('axis', 'y') == 'y'] or comp
        base = min(vert)
        bx, by, bz = base[2] + X0 + 0.5, base[0] + Y0, base[1] + Z0 + 0.5
        top_y = max(q[0] for q in vert) + Y0 + 1
        height = max(1.0, top_y - by)
        r0 = min(0.36, 0.12 + 0.03 * height)
        bark = mat('bark_' + kind)
        lean = (rng.normal(0, 0.05), rng.normal(0, 0.05))
        segs = max(2, int(height * 1.5))
        prev = (bx, by - 0.1, bz)
        for k in range(1, segs + 1):
            t = k / segs
            p = (bx + lean[0] * t * height, by + t * height, bz + lean[1] * t * height)
            _cyl_between(tacc, prev, p, r0 * (1 - 0.5 * (k - 1) / segs), r0 * (1 - 0.5 * t), bark)
            prev = p
        col.box(bx - r0, by, bz - r0, bx + r0, top_y, bz + r0, mat('collision'))
        for q in comp:
            if self.parsed[self.v[q]][1].get('axis', 'y') == 'y':
                continue
            qx, qy, qz = q[2] + X0 + 0.5, q[0] + Y0 + 0.5, q[1] + Z0 + 0.5
            a = (bx + lean[0] * (qy - by), qy - 0.4, bz + lean[1] * (qy - by))
            _cyl_between(tacc, a, (qx, qy + 0.3, qz), r0 * 0.45, r0 * 0.25, bark)
        if len(leaf_pts) == 0:
            _blob(cacc, bx, top_y + 0.8, bz, 1.4, 1.2, mat('leaves_%s_1' % kind), rng)
            return
        P = leaf_pts[:, [2, 0, 1]].astype(float) + np.array([X0 + 0.5, Y0 + 0.5, Z0 + 0.5])
        k = int(np.clip(len(P) / 12, 1, 7))
        cents = P[rng.choice(len(P), k, replace=False)]
        for _ in range(8):
            lab = np.argmin(((P[:, None, :] - cents[None]) ** 2).sum(-1), axis=1)
            cents = np.array([P[lab == i].mean(0) if (lab == i).any() else cents[i] for i in range(k)])
        lm = mat('leaves_%s_%d' % (kind, int(rng.integers(0, 3))))
        for i in range(k):
            pts = P[lab == i]
            if len(pts) == 0:
                continue
            spread = math.sqrt(((pts - cents[i]) ** 2).sum(1).mean()) if len(pts) > 1 else 0.6
            r = float(np.clip(spread * 1.2 + 0.6, 0.8, 3.4))
            cx, cy, cz = cents[i]
            cy = max(cy, by + 1.8 + r * 0.5)
            d = math.hypot(cx - bx, cz - bz)
            if d > r + 0.8:  # 离树干太远的团往里收，保证跟树连着
                f = (d - r - 0.5) / d
                cx, cz = cx + (bx - cx) * f, cz + (bz - cz) * f
            r = self._room_for(cx, cy, cz, r)
            if r >= 0.5:
                _blob(cacc, cx, cy, cz, r, r * 0.78, lm, rng)

    def _room_for(self, cx, cy, cz, r):
        """树冠半径收到不碰建筑（离最近的墙 / 楼板 / 玻璃留 0.4 m）。"""
        X0, Y0, Z0 = self.origin
        occ = self._mass | self._thin | self._glass
        occ = occ.copy()
        occ[:2] = False
        Y, Z, X = occ.shape
        lx0, lx1 = max(0, int(cx - r - X0) - 1), min(X, int(cx + r - X0) + 2)
        ly0, ly1 = max(0, int(cy - r - Y0) - 1), min(Y, int(cy + r - Y0) + 2)
        lz0, lz1 = max(0, int(cz - r - Z0) - 1), min(Z, int(cz + r - Z0) + 2)
        pts = np.argwhere(occ[ly0:ly1, lz0:lz1, lx0:lx1])
        if len(pts) == 0:
            return r
        py = pts[:, 0] + ly0 + Y0 + 0.5
        pz = pts[:, 1] + lz0 + Z0 + 0.5
        px = pts[:, 2] + lx0 + X0 + 0.5
        d = np.sqrt((px - cx) ** 2 + ((py - cy) / 0.78) ** 2 + (pz - cz) ** 2).min() - 0.9
        return min(r, d)

    def _hedges(self, hacc, sacc, col, free, support, rng):
        """不属于任何树的树叶连通块：落在地面 / 台面上的做绿篱（长条）或灌木团；悬空的丢掉。"""
        X0, Y0, Z0 = self.origin
        Y, Z, X = free.shape
        hm = mat('hedge')
        cm = mat('collision')
        lab = np.zeros(free.shape, np.int32)
        n = 0
        for p in map(tuple, np.argwhere(free).tolist()):
            if lab[p]:
                continue
            n += 1
            lab[p] = n
            stack, comp = [p], []
            while stack:
                q = stack.pop()
                comp.append(q)
                for d in N6:
                    r = (q[0] + d[0], q[1] + d[1], q[2] + d[2])
                    if 0 <= r[0] < Y and 0 <= r[1] < Z and 0 <= r[2] < X and free[r] and not lab[r]:
                        lab[r] = n
                        stack.append(r)
            cols = {}
            for y, z, x in comp:
                lo, hi = cols.get((z, x), (y, y))
                cols[(z, x)] = (min(lo, y), max(hi, y))
            grounded = {}
            for (z, x), (lo, hi) in cols.items():
                yy = lo - 1
                while yy >= 0 and not support[yy, z, x] and lo - yy <= 2:
                    yy -= 1
                if yy >= 0 and support[yy, z, x]:
                    grounded[(z, x)] = (yy + 1, hi + 1)
            if not grounded:
                continue
            zs = [k[0] for k in grounded]
            xs = [k[1] for k in grounded]
            sx, sz = max(xs) - min(xs) + 1, max(zs) - min(zs) + 1
            hts = [b - a for a, b in grounded.values()]
            if (min(sx, sz) <= 2 or len(grounded) < 0.5 * sx * sz) and max(hts) <= 3:
                bylvl = {}
                for (z, x), ab in grounded.items():
                    bylvl.setdefault(ab, []).append((z, x))
                for (a, b), cells in bylvl.items():
                    m2 = np.zeros((Z, X), bool)
                    for z, x in cells:
                        m2[z, x] = True
                    for r0, c0, r1, c1 in greedy2d(m2):
                        box = (c0 + X0 + 0.05, a + Y0, r0 + Z0 + 0.05, c1 + X0 - 0.05, b + Y0 - 0.15, r1 + Z0 - 0.05)
                        hacc.box(*box, hm, skip=('-y',))
                        col.box(*box, cm)
            else:
                pts = np.array([(x + X0 + 0.5, a + Y0, z + Z0 + 0.5, b - a) for (z, x), (a, b) in grounded.items()], float)
                k = int(np.clip(len(pts) / 5, 1, 14))
                cents = pts[rng.choice(len(pts), k, replace=False)]
                for _ in range(6):
                    lb = np.argmin(((pts[:, None, [0, 2]] - cents[None, :, [0, 2]]) ** 2).sum(-1), axis=1)
                    cents = np.array([pts[lb == i].mean(0) if (lb == i).any() else cents[i] for i in range(k)])
                for i in range(k):
                    sel = pts[lb == i]
                    if len(sel) == 0:
                        continue
                    rad = float(np.clip(math.sqrt(len(sel)) * 0.6 + 0.3, 0.6, 2.2))
                    hh = float(np.clip(sel[:, 3].mean(), 0.7, 2.6))
                    gy = float(sel[:, 1].min())
                    _blob(sacc, cents[i][0], gy + hh * 0.42, cents[i][2], rad, hh * 0.6, hm, rng, flat_bottom=gy)


# ================================================================ 房间辅助

def _components(mask):
    """二维连通块（4 邻接），返回每块的 (z, x) 坐标数组。"""
    Z, X = mask.shape
    lab = np.zeros(mask.shape, np.int32)
    out = []
    for z0, x0 in np.argwhere(mask).tolist():
        if lab[z0, x0]:
            continue
        lab[z0, x0] = len(out) + 1
        stack, cells = [(z0, x0)], []
        while stack:
            z, x = stack.pop()
            cells.append((z, x))
            for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                z2, x2 = z + dz, x + dx
                if 0 <= z2 < Z and 0 <= x2 < X and mask[z2, x2] and not lab[z2, x2]:
                    lab[z2, x2] = lab[z0, x0]
                    stack.append((z2, x2))
        out.append(np.array(cells))
    return out


def shift2(a, dz, dx):
    """二维：每个格子看 (dz, dx) 方向邻居的值，越界算 False。"""
    out = np.zeros_like(a)
    Z, X = a.shape
    zs, ze = max(0, -dz), Z - max(0, dz)
    xs, xe = max(0, -dx), X - max(0, dx)
    out[zs:ze, xs:xe] = a[zs + dz:ze + dz, xs + dx:xe + dx]
    return out


def _max_rect(mask):
    """二值图里面积最大的全 True 矩形 (r0, c0, r1, c1)，直方图法。"""
    Z, X = mask.shape
    h = np.zeros(X, int)
    best = (0, 0, 0, 0, 0)
    for r in range(Z):
        h = np.where(mask[r], h + 1, 0)
        stack = []
        for c_ in range(X + 1):
            cur = h[c_] if c_ < X else 0
            start = c_
            while stack and stack[-1][1] >= cur:
                s0, hh = stack.pop()
                a_ = hh * (c_ - s0)
                if a_ > best[0]:
                    best = (a_, r - hh + 1, s0, r + 1, c_)
                start = s0
            stack.append((start, cur))
    return best[1:]


def _in_box(room, b):
    x0, z0, x1, z1 = room['box']
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    return b[0] <= cx < b[2] and b[1] <= cz < b[3]


def _room_type(room, rules):
    """按 campus_plots.json 的 room_rules 定房间类型；返回 '' 表示不动。"""
    for sk in rules.get('skip', []):
        if (not sk.get('plot') or sk['plot'] == room['plot']) and ('box' not in sk or _in_box(room, sk['box'])) and room['floor'] >= sk.get('min_floor', -99):
            return ''
    w = room['box'][2] - room['box'][0]
    d = room['box'][3] - room['box'][1]
    for t in rules.get('types', []):
        if t.get('plot') and t['plot'] != room['plot']:
            continue
        if 'floor' in t and t['floor'] != room['floor']:
            continue
        if 'box' in t and not _in_box(room, t['box']):
            continue
        if not (t.get('min_area', 0) <= room['area'] <= t.get('max_area', 1e9)):
            continue
        if min(w, d) < t.get('min_side', 0) or room['fill'] < t.get('min_fill', 0.75):
            continue
        return t['type']
    return ''


# ================================================================ 几何小件

def _wall_piece(acc, x, z, y0, y1, orth, diag, m, t):
    cx, cz = x + 0.5, z + 0.5
    h = t / 2
    acc.box(cx - h, y0, cz - h, cx + h, y1, cz + h, m)
    e, w, s, n = orth
    if e:
        acc.box(cx + h, y0, cz - h, x + 1, y1, cz + h, m, skip=('-x',))
    if w:
        acc.box(x, y0, cz - h, cx - h, y1, cz + h, m, skip=('+x',))
    if s:
        acc.box(cx - h, y0, cz + h, cx + h, y1, z + 1, m, skip=('-z',))
    if n:
        acc.box(cx - h, y0, z, cx + h, y1, cz - h, m, skip=('+z',))
    for (dx, dz), on in zip(DIAG, diag):
        if on:
            acc.obox(cx + dx * 0.25, cz + dz * 0.25, math.sqrt(0.5) + t * 0.5, t, y0, y1, math.atan2(dz, dx), m)


def _ramp(acc, x, y, z, dx, dz, m):
    P = to_bl
    corners = [(x, z), (x + 1, z), (x + 1, z + 1), (x, z + 1)]

    def h(px, pz):
        t = (px - x) if dx > 0 else (x + 1 - px) if dx < 0 else (pz - z) if dz > 0 else (z + 1 - pz)
        return y + t
    top = [P(px, h(px, pz), pz) for px, pz in corners]
    acc.poly([top[0], top[3], top[2], top[1]], m)
    acc.poly([P(px, y, pz) for px, pz in corners], m)
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        acc.poly([P(a[0], y, a[1]), P(a[0], h(*a), a[1]), P(b[0], h(*b), b[1]), P(b[0], y, b[1])], m)


def _cyl_between(acc, a, b, r0, r1, m, seg=8):
    """两点之间的圆台（MC 坐标），侧面 UV 按周长 × 长度。"""
    a, b = np.array(a, float), np.array(b, float)
    d = b - a
    L = float(np.linalg.norm(d))
    if L < 1e-4:
        return
    d /= L
    up = np.array([0, 1, 0]) if abs(d[1]) < 0.9 else np.array([1, 0, 0])
    u = np.cross(d, up)
    u /= np.linalg.norm(u)
    w = np.cross(d, u)
    tile = TILE.get(m.name, 1.0)
    ring = [math.cos(2 * math.pi * i / seg) * u + math.sin(2 * math.pi * i / seg) * w for i in range(seg + 1)]
    circ = 2 * math.pi * max(r0, 0.05)
    for i in range(seg):
        pa0, pa1 = a + ring[i] * r0, a + ring[i + 1] * r0
        pb0, pb1 = b + ring[i] * r1, b + ring[i + 1] * r1
        u0, u1 = circ * i / seg / tile, circ * (i + 1) / seg / tile
        acc.poly([to_bl(*pa0), to_bl(*pb0), to_bl(*pb1), to_bl(*pa1)], m, uvs=[(u0, 0), (u0, L / tile), (u1, L / tile), (u1, 0)])


def _blob(acc, cx, cy, cz, r, ry, m, rng, flat_bottom=None, sub=2):
    """有起伏的椭球团（树冠 / 灌木）。flat_bottom：底面压平在这个高度。"""
    verts, faces = _ICO[sub]
    jit = 1 + rng.normal(0, 0.08, len(verts))
    out = []
    for (vx, vy, vz), j in zip(verts, jit):
        py = cy + vy * ry * j
        if flat_bottom is not None:
            py = max(py, flat_bottom + 0.02)
        out.append((cx + vx * r * j, py, cz + vz * r * j))
    tile = TILE.get(m.name, 1.0)
    for f in faces:
        acc.poly([to_bl(*out[i]) for i in f], m, uvs=[((out[i][0] + out[i][2]) / tile, out[i][1] / tile) for i in f])


def _make_ico(sub):
    t = (1 + 5 ** 0.5) / 2
    vs = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
          (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    vs = [tuple(np.array(p) / np.linalg.norm(p)) for p in vs]
    fs = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
          (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(sub):
        cache = {}

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                p = (np.array(vs[a]) + np.array(vs[b])) / 2
                vs.append(tuple(p / np.linalg.norm(p)))
                cache[k] = len(vs) - 1
            return cache[k]
        nf = []
        for a, b, c in fs:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        fs = nf
    # MC (x, y, z) → Blender 时 z 取反、手性翻转，所以面的顶点反序，法线才朝外
    return vs, [(c, b, a) for a, b, c in fs]


_ICO = {s: _make_ico(s) for s in (1, 2)}


def _blade(acc, x, y, z, ang, w, h, m):
    dx, dz = math.cos(ang) * w / 2, math.sin(ang) * w / 2
    acc.poly([to_bl(x - dx, y, z - dz), to_bl(x + dx, y, z + dz), to_bl(x + dx * 0.15, y + h, z + dz * 0.15), to_bl(x - dx * 0.15, y + h, z - dz * 0.15)],
             m, uvs=[(0, 0), (0.2, 0), (0.2, h), (0, h)])


def _round_edges(ob, width):
    b = ob.modifiers.new('bevel', 'BEVEL')
    b.width = width
    b.segments = 3
    b.limit_method = 'ANGLE'
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=b.name)
    ob.data.shade_smooth()


# ================================================================ 圆塔 / 圆顶

def build_tower(plot, r, coll, col):
    cx, cz, rad = r['center'][0], r['center'][1], r['radius']
    ya, yb = r['y']
    seg = r.get('segments', 72)
    acc = MeshAcc()
    frame = mat('frame')
    P = to_bl
    rc = rad - 0.3
    for y in range(ya, yb + 1):
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            am = (a0 + a1) / 2
            key, glassy = None, False
            for rr in (rad - 0.5, rad - 1.0, rad, rad - 1.5):
                base, _ = plot.sample(int(math.floor(cx + math.cos(am) * rr)), y, int(math.floor(cz + math.sin(am) * rr)))
                cat = category(base)
                if cat in ('solid', 'glass', 'pane'):
                    key, glassy = base, cat in ('glass', 'pane')
                    break
            if key is None:
                continue
            m = mat(glass_mat(key)) if glassy else mat(block_mat(key))
            t = 0.04 if glassy else T
            ro, ri = rc + t / 2, rc - t / 2
            p = [(cx + math.cos(a) * rr, cz + math.sin(a) * rr) for a, rr in ((a0, ro), (a1, ro), (a1, ri), (a0, ri))]
            tile = TILE.get(m.name, 1.0)
            arc = rad * (a1 - a0)
            uv = [(arc * i / tile, y / tile), (arc * (i + 1) / tile, y / tile), (arc * (i + 1) / tile, (y + 1) / tile), (arc * i / tile, (y + 1) / tile)]
            acc.poly([P(p[0][0], y, p[0][1]), P(p[1][0], y, p[1][1]), P(p[1][0], y + 1, p[1][1]), P(p[0][0], y + 1, p[0][1])], m, uv)
            acc.poly([P(p[3][0], y, p[3][1]), P(p[3][0], y + 1, p[3][1]), P(p[2][0], y + 1, p[2][1]), P(p[2][0], y, p[2][1])], m, uv)
            if glassy and i % 3 == 0:
                acc.obox(cx + math.cos(a0) * rc, cz + math.sin(a0) * rc, 0.08, 0.16, y, y + 1, a0 + math.pi / 2, frame)
    ring_r = r.get('ring_radius', rad + 0.75)
    for y in range(ya, yb + 1):
        base, _ = plot.sample(int(cx), y, int(cz))
        if category(base) == 'solid':
            _disc(acc, cx, cz, ring_r, y + PLATE_GAP, y + 1, mat('facade'), mat('floor'))
            if ring_r > rad + 1:  # 阳台外沿的玻璃栏板
                n = 72
                for i in range(n):
                    a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
                    p0 = (cx + math.cos(a0) * (ring_r - 0.08), cz + math.sin(a0) * (ring_r - 0.08))
                    p1 = (cx + math.cos(a1) * (ring_r - 0.08), cz + math.sin(a1) * (ring_r - 0.08))
                    acc.poly([to_bl(p0[0], y + 1, p0[1]), to_bl(p1[0], y + 1, p1[1]), to_bl(p1[0], y + 2.05, p1[1]), to_bl(p0[0], y + 2.05, p0[1])], mat('glass'))
                    acc.poly([to_bl(p0[0], y + 1, p0[1]), to_bl(p0[0], y + 2.05, p0[1]), to_bl(p1[0], y + 2.05, p1[1]), to_bl(p1[0], y + 1, p1[1])], mat('glass'))
                    if i % 6 == 0:
                        acc.obox(p0[0], p0[1], 0.06, 0.06, y + 1, y + 2.1, a0, mat('frame'))
                    acc.obox((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 0.01, 0.08, y + 2.05, y + 2.1, (a0 + a1) / 2 + math.pi / 2, mat('frame'))
    cm0 = mat('collision')
    for y in range(ya, yb + 1):
        base, _ = plot.sample(int(cx), y, int(cz))
        if category(base) == 'solid':
            n = 36
            for i in range(n):
                a0 = 2 * math.pi * (i + 0.5) / n
                rr = (rad + ring_r) / 2
                col.obox(cx + math.cos(a0) * rr, cz + math.sin(a0) * rr, 2 * math.pi * ring_r / n + 0.2, ring_r - rad + 0.6, y + PLATE_GAP, y + 1, a0 + math.pi / 2, cm0)
    cm = mat('collision')
    for i in range(48):
        a0 = 2 * math.pi * (i + 0.5) / 48
        col.obox(cx + math.cos(a0) * rc, cz + math.sin(a0) * rc, 2 * math.pi * rad / 48 + 0.1, 0.3, ya, yb + 1, a0 + math.pi / 2, cm)
    if 'dome' in r:
        dm = r['dome']
        dacc = MeshAcc()
        _dome(dacc, cx, cz, dm.get('radius', rad), dm['base_y'], dm.get('height', rad), mat('metal'))
        dacc.build(r['id'] + '_dome', coll, smooth=True)
    return acc.build(r['id'], coll)


def build_dome(r, coll):
    acc = MeshAcc()
    _dome(acc, r['center'][0], r['center'][1], r['radius'], r['base_y'], r.get('height', r['radius']), mat('metal'))
    return acc.build(r['id'], coll, smooth=True)


def _disc(acc, cx, cz, rad, y0, y1, side_m, top_m, seg=72):
    ring = [(cx + math.cos(2 * math.pi * i / seg) * rad, cz + math.sin(2 * math.pi * i / seg) * rad) for i in range(seg)]
    acc.poly([to_bl(x, y1, z) for x, z in reversed(ring)], top_m)
    acc.poly([to_bl(x, y0, z) for x, z in ring], side_m)
    for i in range(seg):
        j = (i + 1) % seg
        acc.poly([to_bl(ring[i][0], y0, ring[i][1]), to_bl(ring[j][0], y0, ring[j][1]), to_bl(ring[j][0], y1, ring[j][1]), to_bl(ring[i][0], y1, ring[i][1])], side_m)


def _dome(acc, cx, cz, rad, base_y, height, m, seg=64, rings=16):
    pts = []
    for k in range(rings + 1):
        phi = (math.pi / 2) * k / rings
        rr = rad * math.cos(phi)
        yy = base_y + height * math.sin(phi)
        pts.append([(cx + math.cos(2 * math.pi * i / seg) * rr, yy, cz + math.sin(2 * math.pi * i / seg) * rr) for i in range(seg)])
    for k in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            acc.poly([to_bl(*p) for p in (pts[k][i], pts[k][j], pts[k + 1][j], pts[k + 1][i])], m)
    _disc(acc, cx, cz, rad + 0.25, base_y - 0.3, base_y, mat('facade'), mat('roof'))


# ================================================================ 场景与导出

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()
    _IMGS.clear()
    TILE.clear()


def export_gltf(path):
    """导出 .gltf + .bin，贴图引用 textures/ 下的原文件（各地块共用，不重复打包）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLTF_SEPARATE', export_keep_originals=True, export_apply=True,
                              export_yup=True, export_materials='EXPORT', use_selection=False)


def tri_count():
    n = 0
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and not ob.name.endswith('-colonly'):
            n += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return n
