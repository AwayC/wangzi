"""从 assets/env/campus/*.gltf 的真实三维网格与 campus_rooms.json / campus_doors.json 提取每栋楼每层的精确水平横截面图（v4.1）。"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MOD_DIR = os.path.join(ROOT, 'assets', 'env', 'campus')
OUT_DIR = os.path.join(ROOT, 'docs', 'production', 'img', 'sections')
os.makedirs(OUT_DIR, exist_ok=True)

FONT_PATH = '/System/Library/Fonts/Hiragino Sans GB.ttc'
F_TITLE = ImageFont.truetype(FONT_PATH, 26)
F_SUB = ImageFont.truetype(FONT_PATH, 16)
F_ROOM = ImageFont.truetype(FONT_PATH, 15)
F_SMALL = ImageFont.truetype(FONT_PATH, 13)
F_TINY = ImageFont.truetype(FONT_PATH, 11)


def load_gltf_primitives(mod_id):
    """读取指定 gltf 主建筑节点（mesh 0）的全部三角面，按材质名分组返回 (tris_xyz, normals_xyz)。"""
    gltf_path = os.path.join(MOD_DIR, mod_id + '.gltf')
    bin_path = os.path.join(MOD_DIR, mod_id + '.bin')
    g = json.load(open(gltf_path, encoding='utf-8'))
    raw = open(bin_path, 'rb').read()
    mats = [m.get('name', '') for m in g.get('materials', [])]
    bvs = g['bufferViews']
    accs = g['accessors']

    def get_acc(idx):
        a = accs[idx]
        bv = bvs[a['bufferView']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        cnt = a['count']
        ctype = a['componentType']
        atype = a['type']
        ncomp = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[atype]
        dt = {5126: '<f4', 5123: '<u2', 5125: '<u4', 5121: '<u1'}[ctype]
        stride = bv.get('byteStride', 0)
        item_sz = np.dtype(dt).itemsize * ncomp
        if stride and stride != item_sz:
            arr = np.ndarray((cnt, ncomp), dtype=dt, buffer=raw, offset=off, strides=(stride, np.dtype(dt).itemsize))
            return arr.copy()
        return np.frombuffer(raw, dtype=dt, count=cnt * ncomp, offset=off).reshape(cnt, ncomp)

    by_mat = {}
    mesh0 = g['meshes'][0]
    for prim in mesh0['primitives']:
        mname = mats[prim['material']] if 'material' in prim else ''
        pos = get_acc(prim['attributes']['POSITION']).astype(np.float64)
        idx = get_acc(prim['indices']).ravel()
        tris = pos[idx].reshape(-1, 3, 3)
        v10 = tris[:, 1] - tris[:, 0]
        v20 = tris[:, 2] - tris[:, 0]
        nrm = np.cross(v10, v20)
        ln = np.linalg.norm(nrm, axis=1, keepdims=True)
        nrm = np.divide(nrm, np.maximum(ln, 1e-9))
        if mname in by_mat:
            by_mat[mname] = (np.concatenate([by_mat[mname][0], tris]), np.concatenate([by_mat[mname][1], nrm]))
        else:
            by_mat[mname] = (tris, nrm)
    return by_mat


def slice_plane_segments(tris, y_cut):
    """计算三角网格与水平面 y = y_cut 的交线段集合 [(x0, z0, x1, z1), ...]。"""
    ys = tris[:, :, 1]
    above = ys >= y_cut
    cnt = above.sum(axis=1)
    mask = (cnt == 1) | (cnt == 2)
    sub = tris[mask]
    segs = []
    for tri in sub:
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            ya, yb = a[1] - y_cut, b[1] - y_cut
            if (ya >= 0) != (yb >= 0):
                t = ya / (ya - yb)
                p = a + t * (b - a)
                pts.append((float(p[0]), float(p[2])))
            elif abs(ya) < 1e-6 and abs(yb) < 1e-6:
                pts.append((float(a[0]), float(a[2])))
                pts.append((float(b[0]), float(b[2])))
        if len(pts) >= 2:
            if math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]) > 1e-4:
                segs.append((pts[0][0], pts[0][1], pts[1][0], pts[1][1]))
    return segs


def _in_box(seg, x0, z0, x1, z1):
    mx = (seg[0] + seg[2]) * 0.5
    mz = (seg[1] + seg[3]) * 0.5
    return x0 <= mx <= x1 and z0 <= mz <= z1


def scanline_fill_closed_slice(draw, segs, to_px, img_h, fill_rgb, max_w=95.0):
    """利用水平剖面交线段的奇偶绕数扫描线填充闭合墙体/立柱内部实心截面（Poché）。"""
    if not segs:
        return
    px_segs = []
    min_py, max_py = img_h, 0
    for x0, z0, x1, z1 in segs:
        px0, py0 = to_px(x0, z0)
        px1, py1 = to_px(x1, z1)
        if abs(py1 - py0) < 0.25:
            continue
        if py0 > py1:
            px0, py0, px1, py1 = px1, py1, px0, py0
        px_segs.append((px0, py0, px1, py1))
        min_py = min(min_py, int(math.floor(py0)))
        max_py = max(max_py, int(math.ceil(py1)))
    min_py = max(0, min_py)
    max_py = min(img_h - 1, max_py)
    for py in range(min_py, max_py + 1):
        yy = py + 0.5
        xs = []
        for px0, py0, px1, py1 in px_segs:
            if py0 <= yy < py1:
                x_int = px0 + (yy - py0) * (px1 - px0) / (py1 - py0)
                xs.append(x_int)
        if len(xs) >= 2:
            xs.sort()
            dedup = []
            for x in xs:
                if dedup and abs(x - dedup[-1]) < 0.35:
                    continue
                dedup.append(x)
            for k in range(0, len(dedup) - 1, 2):
                xa, xb = dedup[k], dedup[k + 1]
                if 0.8 <= (xb - xa) <= max_w:
                    draw.line([(xa, py), (xb, py)], fill=fill_rgb, width=1)


def _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, lx, lz, w, d, fill, outline):
    ang = math.radians(rot_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dz in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        px_l, pz_l = lx + dx, lz + dz
        wx = cx + px_l * ca + pz_l * sa
        wz = cz - px_l * sa + pz_l * ca
        pts.append(to_px(wx, wz))
    draw.polygon(pts, fill=fill, outline=outline)


def draw_furniture_for_room(draw, to_px, r):
    b = r['box']
    x0, z0, x1, z1 = b
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    along_x = (x1 - x0) > (z1 - z0)
    rot_deg = float(r.get('rot', 90.0 if along_x else 0.0))
    span_x, span_z = x1 - x0, z1 - z0
    is_90 = abs((abs(rot_deg) % 180.0) - 90.0) < 1.0
    L = (span_x if is_90 else span_z) - 0.2
    W = (span_z if is_90 else span_x) - 0.2
    rtype = r['type']

    c_desk = (228, 206, 172)
    c_desk_o = (165, 138, 102)
    c_pc = (192, 214, 232)
    c_pc_o = (110, 145, 175)
    c_bed = (196, 216, 240)
    c_bed_o = (95, 130, 175)
    c_cab = (205, 210, 216)
    c_cab_o = (120, 128, 138)
    c_sofa = (182, 206, 198)
    c_sofa_o = (82, 122, 112)
    c_bb = (58, 112, 82)

    if rtype in ('classroom', 'lab'):
        front, back = -L / 2, L / 2
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 0, front + 0.85, 2.6, 1.4, (226, 222, 214), (170, 164, 154))
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 0, front + 1.0, 1.1, 0.65, (198, 158, 112), (135, 98, 60))
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 0, front + 0.10, 3.8, 0.16, c_bb, (35, 75, 52))
        if rtype == 'lab':
            per = max(1, int((W - 1.0) / 1.45))
            z = front + 2.65
            while z < back - 1.0:
                for i in range(per):
                    xx = (i - (per - 1) / 2.0) * 1.45
                    _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, xx, z, 1.32, 0.62, c_pc, c_pc_o)
                z += 1.55
        else:
            groups = max(1, min(3, int((W - 1.2) / 2.3)))
            z = front + 2.55
            while z < back - 1.15:
                for i in range(groups):
                    gx = (i - (groups - 1) / 2.0) * 2.25
                    for dx in (-0.31, 0.31):
                        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, gx + dx, z, 0.58, 0.44, c_desk, c_desk_o)
                z += 1.15
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -W / 2 + 0.9, back - 0.25, 1.1, 0.38, c_cab, c_cab_o)
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, W / 2 - 0.9, back - 0.33, 0.95, 0.45, c_cab, c_cab_o)

    elif rtype == 'reading_lounge':
        # 东墙书架 + 西墙海报公告栏 + 背靠西墙朝东书架的阅读沙发
        for z in (-2.0, 0.0, 2.0):
            _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, W / 2 - 0.25, z, 0.42, 1.45, c_desk, c_desk_o)
        for z in (-1.8, 0.3, 2.1):
            _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -W / 2 + 0.08, z, 0.12, 1.2, (238, 198, 115), (175, 128, 45))
        for z in (-1.3, 1.1):
            _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -W / 2 + 0.55, z, 0.78, 1.56, c_sofa, c_sofa_o)

    elif rtype == 'study_room':
        # 宿舍 3F 自习室：书架 + 四张对坐自习桌
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, W / 2 - 0.25, 0.0, 0.42, 1.45, c_desk, c_desk_o)
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -W / 2 + 0.85, L / 2 - 0.28, 1.1, 0.38, c_cab, c_cab_o)
        for dx in (-0.45, 0.25):
            for dz in (-0.55, 0.55):
                _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, dx, dz, 0.58, 0.44, c_desk, c_desk_o)

    elif rtype == 'office':
        pairs = max(1, min(3, int((L - 1.5) / 1.7)))
        if W >= 2.8:
            for i in range(pairs):
                z = (i - (pairs - 1) / 2.0) * 1.7
                _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -0.38, z, 0.68, 1.25, c_desk, c_desk_o)
                _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 0.38, z, 0.68, 1.25, c_desk, c_desk_o)
        if L > 3.5:
            _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -W / 2 + 0.5, -L / 2 + 0.4, 0.85, 0.45, c_cab, c_cab_o)
            _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, W / 2 - 0.7, -L / 2 + 0.3, 1.0, 0.38, c_cab, c_cab_o)

    elif rtype == 'dorm':
        # 寝室只放床，两侧贴墙留紧凑过人过道！
        n = max(1, min(2, int((L - 0.3) / 2.05)))
        for side in (-1, 1):
            if W < 2.6 and side > 0:
                continue
            for k in range(n):
                z_pos = (k - (n - 1) / 2.0) * 2.05
                _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, side * (W / 2 - 0.52), z_pos, 0.95, 1.95, c_bed, c_bed_o)

    elif rtype == 'small_lab':
        for x in (-1.5, 0.0, 1.5):
            _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, x, -0.82, 1.32, 0.62, c_pc, c_pc_o)
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 2.55, 0.95, 0.92, 0.45, c_cab, c_cab_o)

    elif rtype == 'astronomy':
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 0.2, 0.2, 1.6, 1.1, c_desk, c_desk_o)
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -0.8, -1.6, 1.3, 0.62, c_pc, c_pc_o)
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 0.9, -1.6, 1.3, 0.62, c_pc, c_pc_o)
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, -1.2, 1.4, 0.65, 1.0, (198, 158, 112), (135, 98, 60))
        _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, 1.5, 1.6, 1.0, 0.38, c_cab, c_cab_o)

    elif rtype == 'canteen':
        x = -W / 2 + 2.2
        while x < W / 2 - 1.8:
            z = -L / 2 + 2.4
            while z < L / 2 - 2.0:
                _draw_oriented_rect(draw, to_px, cx, cz, rot_deg, x, z, 1.55, 1.35, c_desk, c_desk_o)
                z += 2.6
            x += 2.7


def render_section(spec, rooms_db, doors_db):
    mod_id = spec['mod_id']
    by_mat = load_gltf_primitives(mod_id)
    bx0, bz0, bx1, bz1 = spec['bbox']
    y_floor = spec['y_floor']
    floor_h = spec.get('floor_h', 3.4)
    y_cut = spec.get('y_cut', y_floor + 1.45)
    y_low = spec.get('y_low', y_floor + 0.62)
    sub_cut = spec.get('sub_cut')  # 可选局部错半层剖切区: (sx0, sz0, sx1, sz1, sy_floor, sy_cut, sy_low)

    pad_l, pad_r, pad_t, pad_b = 68, 44, 96, 72
    span_x = bx1 - bx0
    span_z = bz1 - bz0
    scale = min(1680.0 / span_x, 860.0 / span_z)
    scale = max(18.0, min(scale, 42.0))
    W = int(round(span_x * scale)) + pad_l + pad_r
    H = int(round(span_z * scale)) + pad_t + pad_b
    W = max(W, 1520)

    img = Image.new('RGB', (W, H), (247, 249, 252))
    draw = ImageDraw.Draw(img)

    ox = pad_l + (W - pad_l - pad_r - span_x * scale) / 2.0
    oz = pad_t

    def to_px(x, z):
        return (ox + (x - bx0) * scale, oz + (z - bz0) * scale)

    # 1) 1 m 细网格与 5 m 坐标主网格
    gx_start = int(math.ceil(bx0))
    gx_end = int(math.floor(bx1))
    gz_start = int(math.ceil(bz0))
    gz_end = int(math.floor(bz1))
    p_tl = to_px(bx0, bz0)
    p_br = to_px(bx1, bz1)
    draw.rectangle([p_tl, p_br], fill=(242, 245, 249), outline=(195, 203, 214), width=1)

    for gx in range(gx_start, gx_end + 1):
        px, _ = to_px(gx, bz0)
        is_5 = (gx % 5 == 0)
        draw.line([(px, p_tl[1]), (px, p_br[1])], fill=(214, 221, 230) if is_5 else (233, 237, 243), width=1)
        if is_5:
            draw.text((px - 10, p_tl[1] - 18), f'{gx}', font=F_TINY, fill=(105, 115, 130))
    for gz in range(gz_start, gz_end + 1):
        _, py = to_px(bx0, gz)
        is_5 = (gz % 5 == 0)
        draw.line([(p_tl[0], py), (p_br[0], py)], fill=(214, 221, 230) if is_5 else (233, 237, 243), width=1)
        if is_5:
            draw.text((p_tl[0] - 32, py - 7), f'{gz}', font=F_TINY, fill=(105, 115, 130))

    # 2) 楼板、露台与楼梯踏步水平投影层
    floor_mats = [
        ('M_roof', (218, 223, 230), (185, 192, 202)),
        ('M_plaza', (232, 234, 238), None),
        ('M_paving_light', (235, 237, 240), None),
        ('M_concrete', (228, 231, 236), (195, 200, 208)),
        ('M_floor', (252, 251, 247), (222, 220, 214)),
    ]
    y_min_proj = spec.get('y_min_proj', y_floor - 0.12)
    for mname, base_c, _ in floor_mats:
        if mname not in by_mat:
            continue
        tris, nrm = by_mat[mname]
        ym = tris[:, :, 1].mean(axis=1)
        if mname == 'M_roof':
            sel = (nrm[:, 1] > 0.6) & (ym >= y_floor - 0.5) & (ym <= y_cut - 0.2)
        elif mname in ('M_plaza', 'M_paving_light'):
            sel = (nrm[:, 1] > 0.6) & (abs(ym - y_floor) < 0.5)
        else:
            sel = (nrm[:, 1] > 0.6) & (ym >= y_min_proj) & (ym <= y_floor + floor_h - 0.12)
        idx_order = np.argsort(ym[sel])
        sub_tris = tris[sel][idx_order]
        for tri in sub_tris:
            cx_t, cz_t = tri[:, 0].mean(), tri[:, 2].mean()
            if not (bx0 - 2 <= cx_t <= bx1 + 2 and bz0 - 2 <= cz_t <= bz1 + 2):
                continue
            if sub_cut and (sub_cut[0] <= cx_t <= sub_cut[2] and sub_cut[1] <= cz_t <= sub_cut[3]):
                if abs(float(tri[:, 1].mean()) - sub_cut[4]) > 0.9:
                    continue
            dy = float(tri[:, 1].mean()) - y_floor
            pts2 = [to_px(tri[k, 0], tri[k, 2]) for k in range(3)]
            if abs(dy) > 0.12 and mname in ('M_floor', 'M_concrete'):
                shade = max(0.75, min(0.97, 0.95 - 0.055 * abs(dy)))
                fc = tuple(int(v * shade) for v in (226, 234, 244))
                draw.polygon(pts2, fill=fc, outline=(150, 162, 178))
            else:
                draw.polygon(pts2, fill=base_c, outline=None)

    # 2.4) 挑空区标注（如宿舍 2F 门厅南半“空”挑空）
    for vx0, vz0, vx1, vz1 in spec.get('voids', []):
        p0, p1 = to_px(vx0, vz0), to_px(vx1, vz1)
        draw.rectangle([p0, p1], fill=(235, 240, 246), outline=(145, 158, 176), width=1)
        draw.line([p0, p1], fill=(165, 178, 194), width=2)
        draw.line([(p0[0], p1[1]), (p1[0], p0[1])], fill=(165, 178, 194), width=2)

    # 2.5) 周边绿篱与乔木树干截面
    if 'M_hedge' in by_mat and y_floor < 1.0:
        h_segs = slice_plane_segments(by_mat['M_hedge'][0], 0.45)
        h_clip = [s for s in h_segs if not (max(s[0], s[2]) < bx0 or min(s[0], s[2]) > bx1 or max(s[1], s[3]) < bz0 or min(s[1], s[3]) > bz1)]
        scanline_fill_closed_slice(draw, h_clip, to_px, H, (158, 208, 152), max_w=450.0)
        for x0, z0, x1, z1 in h_clip:
            draw.line([to_px(x0, z0), to_px(x1, z1)], fill=(86, 148, 82), width=2)
    for bmat in ('M_bark_oak', 'M_bark_birch'):
        if bmat in by_mat and y_floor < 1.0:
            for x0, z0, x1, z1 in slice_plane_segments(by_mat[bmat][0], 1.1):
                if bx0 <= x0 <= bx1 and bz0 <= z0 <= bz1:
                    draw.line([to_px(x0, z0), to_px(x1, z1)], fill=(92, 146, 78), width=3)

    # 3) 房间类型浅底色高亮 + 套件家具平面图
    room_tint = {
        'classroom': (242, 250, 244),
        'lab': (236, 246, 255),
        'small_lab': (232, 242, 255),
        'astronomy': (242, 238, 252),
        'reading_lounge': (244, 250, 240),
        'study_room': (245, 248, 238),
        'office': (255, 249, 236),
        'dorm': (240, 247, 255),
        'canteen': (255, 248, 238),
    }
    fl_num = spec.get('floor_num', 1)
    for r in rooms_db.get(mod_id, []):
        if int(r['floor']) != fl_num:
            continue
        rx0, rz0, rx1, rz1 = r['box']
        if rx1 < bx0 or rx0 > bx1 or rz1 < bz0 or rz0 > bz1:
            continue
        fc = room_tint.get(r['type'])
        if fc:
            draw.rectangle([to_px(rx0, rz0), to_px(rx1, rz1)], fill=fc)
        draw_furniture_for_room(draw, to_px, r)

    def _sliced_segs(tris, y_main, y_sub):
        segs = slice_plane_segments(tris, y_main)
        if sub_cut:
            sx0, sz0, sx1, sz1 = sub_cut[:4]
            segs = [s for s in segs if not _in_box(s, sx0, sz0, sx1, sz1)]
            segs += [s for s in slice_plane_segments(tris, y_sub) if _in_box(s, sx0, sz0, sx1, sz1)]
        return [
            s for s in segs
            if not (max(s[0], s[2]) < bx0 - 0.5 or min(s[0], s[2]) > bx1 + 0.5 or max(s[1], s[3]) < bz0 - 0.5 or min(s[1], s[3]) > bz1 + 0.5)
        ]

    # 4) 低矮构件切面（栏杆、闸机机箱、打饭台、洗手台、柜台与货架）
    low_styles = [
        ('M_concrete', (168, 174, 184), 2),
        ('M_wood', (186, 146, 102), 3),
        ('M_wood_dark', (142, 108, 76), 3),
        ('M_metal', (115, 132, 148), 2),
        ('M_metal_dark', (86, 102, 118), 3),
        ('M_red_sign', (215, 68, 58), 3),
    ]
    sy_low = sub_cut[6] if sub_cut else y_low
    for mname, col_rgb, w_px in low_styles:
        if mname not in by_mat:
            continue
        for x0, z0, x1, z1 in _sliced_segs(by_mat[mname][0], y_low, sy_low):
            draw.line([to_px(x0, z0), to_px(x1, z1)], fill=col_rgb, width=w_px)

    # 5) 主墙体/立柱水平剖切层
    solid_wall_mats = ('M_facade', 'M_plaster', 'M_dado_blue', 'M_stone', 'M_sandstone', 'M_concrete')
    all_wall_segs = []
    sy_cut = sub_cut[5] if sub_cut else y_cut
    for mname in solid_wall_mats:
        if mname not in by_mat:
            continue
        clipped = _sliced_segs(by_mat[mname][0], y_cut, sy_cut)
        scanline_fill_closed_slice(draw, clipped, to_px, H, (58, 66, 78))
        all_wall_segs.extend(clipped)
    for x0, z0, x1, z1 in all_wall_segs:
        draw.line([to_px(x0, z0), to_px(x1, z1)], fill=(34, 40, 50), width=2)

    # 错半层虚线框提示
    if sub_cut:
        sx0, sz0, sx1, sz1 = sub_cut[:4]
        draw.rectangle([to_px(sx0, sz0), to_px(sx1, sz1)], outline=(140, 95, 175), width=2)

    # 6) 窗户、玻璃幕墙、门扇、卷帘门切面
    cut_styles = [
        ('M_shutter', (130, 138, 148), 4),
        ('M_frame', (95, 115, 135), 2),
        ('M_glass', (38, 162, 224), 4),
        ('M_glass_blue', (24, 136, 218), 4),
        ('M_glass_dark', (52, 98, 145), 4),
        ('M_wood', (178, 116, 56), 3),
        ('M_metal', (135, 62, 168), 3),
        ('M_metal_dark', (90, 102, 115), 2),
    ]
    for mname, col_rgb, w_px in cut_styles:
        if mname not in by_mat:
            continue
        for x0, z0, x1, z1 in _sliced_segs(by_mat[mname][0], y_cut, sy_cut):
            draw.line([to_px(x0, z0), to_px(x1, z1)], fill=col_rgb, width=w_px)

    # 7) 门位与门锁图标标注（含 1F 进楼口半升起镂空铁链卷帘门虚线符号！）
    for d in doors_db.get(mod_id, []):
        dx, dy, dz = d['pos']
        if abs(dy - y_floor) > 0.6:
            continue
        if not (bx0 <= dx <= bx1 and bz0 <= dz <= bz1):
            continue
        dtype = d.get('type', '')
        if dtype == 'chain_shutter':
            facing = d.get('facing', 'south')
            half_s = 1.05
            if facing in ('south', 'north'):
                for k in range(-4, 5):
                    xa = dx + k * (half_s / 4.8) - 0.06
                    xb = xa + 0.12
                    draw.line([to_px(xa, dz), to_px(xb, dz)], fill=(215, 72, 42), width=4)
            else:
                for k in range(-4, 5):
                    za = dz + k * (half_s / 4.8) - 0.06
                    zb = za + 0.12
                    draw.line([to_px(dx, za), to_px(dx, zb)], fill=(215, 72, 42), width=4)
        px, py = to_px(dx, dz)
        lock = d.get('lock', '')
        if dtype == 'chain_shutter':
            dc, tag = (225, 72, 42), '帘'
        elif lock.startswith('curfew'):
            dc, tag = (225, 72, 42), '禁'
        elif lock.startswith('key'):
            dc, tag = (148, 56, 205), '锁'
        else:
            dc, tag = (36, 162, 88), ''
        r_px = 6 if not tag else 9
        draw.ellipse([px - r_px, py - r_px, px + r_px, py + r_px], fill=dc, outline=(255, 255, 255), width=2)
        if tag:
            draw.text((px - 6, py - 7), tag, font=F_TINY, fill=(255, 255, 255))

    # 8) 楼梯上下行方向箭头标注
    for sx, sz, dir_str in spec.get('stairs', []):
        px, py = to_px(sx, sz)
        bb = draw.textbbox((px, py), dir_str, font=F_SMALL)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.rounded_rectangle([px - tw / 2 - 4, py - th / 2 - 2, px + tw / 2 + 4, py + th / 2 + 2],
                               radius=4, fill=(255, 255, 255), outline=(110, 125, 145), width=1)
        draw.text((px - tw / 2, py - th / 2 - 1), dir_str, font=F_SMALL, fill=(45, 62, 88))

    # 9) 空间编号与尺寸标签
    for code, title_s, dim_s, lx, lz in spec.get('labels', []):
        px, py = to_px(lx, lz)
        line1 = f'{code} {title_s}' if code else title_s
        b1 = draw.textbbox((0, 0), line1, font=F_ROOM)
        b2 = draw.textbbox((0, 0), dim_s, font=F_TINY) if dim_s else (0, 0, 0, 0)
        tw = max(b1[2] - b1[0], b2[2] - b2[0])
        th = (b1[3] - b1[1]) + ((b2[3] - b2[1] + 3) if dim_s else 0)
        x_a, y_a = px - tw / 2 - 6, py - th / 2 - 4
        x_b, y_b = px + tw / 2 + 6, py + th / 2 + 4
        draw.rounded_rectangle([x_a, y_a, x_b, y_b], radius=5, fill=(255, 255, 255), outline=(72, 96, 132), width=1)
        draw.text((px - (b1[2] - b1[0]) / 2, y_a + 3), line1, font=F_ROOM, fill=(22, 38, 68))
        if dim_s:
            draw.text((px - (b2[2] - b2[0]) / 2, y_a + 5 + (b1[3] - b1[1])), dim_s, font=F_TINY, fill=(95, 108, 126))

    # 10) 顶部双行标题栏 + 指北针 + 底部图例与比例尺
    draw.rectangle([(0, 0), (W, 64)], fill=(32, 44, 62))
    draw.text((22, 8), spec['title'], font=F_TITLE, fill=(255, 255, 255))
    sub = f"剖切标高 y = {y_cut:.2f} m（楼面 y = {y_floor:.2f} m） | 坐标单位：米（X 向东 →，Z 向南 ↓）"
    draw.text((24, 40), sub, font=F_TINY, fill=(195, 212, 232))

    nx, ny = W - 36, 78
    draw.polygon([(nx, ny - 12), (nx - 6, ny + 6), (nx, ny + 2), (nx + 6, ny + 6)], fill=(210, 55, 45))
    draw.text((nx - 6, ny + 8), '北', font=F_TINY, fill=(45, 55, 70))

    ly = H - 36
    legend = [
        ((45, 52, 64), '实墙 / 结构柱'),
        ((28, 148, 222), '玻璃窗 / 幕墙'),
        ((95, 110, 126), '护栏 / 闸机'),
        ((216, 224, 236), '楼梯踏步(全敞开无门)'),
        ((36, 162, 88), '普通门'),
        ((225, 72, 42), '1F镂空铁链卷帘门(帘)'),
        ((148, 56, 205), '钥匙门(锁)'),
    ]
    lx_cur = 22
    for c_box, txt in legend:
        draw.rectangle([lx_cur, ly + 3, lx_cur + 16, ly + 15], fill=c_box, outline=(60, 68, 80))
        draw.text((lx_cur + 21, ly + 1), txt, font=F_SMALL, fill=(55, 65, 80))
        lx_cur += 28 + draw.textbbox((0, 0), txt, font=F_SMALL)[2]

    bar_px = 5.0 * scale
    bx_r = W - 32
    bx_l = bx_r - bar_px
    draw.line([(bx_l, ly + 12), (bx_r, ly + 12)], fill=(30, 38, 50), width=3)
    draw.line([(bx_l, ly + 7), (bx_l, ly + 17)], fill=(30, 38, 50), width=2)
    draw.line([(bx_r, ly + 7), (bx_r, ly + 17)], fill=(30, 38, 50), width=2)
    draw.text(((bx_l + bx_r) / 2 - 12, ly - 5), '5 m', font=F_SMALL, fill=(30, 38, 50))

    out_path = os.path.join(OUT_DIR, spec['out'])
    img.save(out_path)
    print('OK', spec['out'], img.size)


def build_all():
    cfg = json.load(open(os.path.join(ROOT, 'data', 'map', 'campus_layout.json'), encoding='utf-8'))
    org = cfg['origins']
    rooms_db = json.load(open(os.path.join(ROOT, 'data', 'map', 'campus_rooms.json'), encoding='utf-8'))
    doors_db = json.load(open(os.path.join(ROOT, 'data', 'map', 'campus_doors.json'), encoding='utf-8'))

    # ==================== 1. 高三教学楼（1F / 2F / 3F） ====================
    gdx, gdz = org['gaosan_dx'], org['gaosan_dz']
    for fl in (1, 2, 3):
        yf = 0.25 + (fl - 1) * 3.4
        st_s = '上2F ↑' if fl == 1 else ('↑上3F / 下1F↓' if fl == 2 else '下2F ↓')
        st_e = '向东上 →' if fl == 1 else ('→上3F / ←下1F' if fl == 2 else '← 下2F')
        render_section({
            'mod_id': 'gaosan',
            'floor_num': fl,
            'y_floor': yf,
            'bbox': (132.5 + gdx, 110.5 + gdz, 190.8 + gdx, 132.2 + gdz),
            'out': f'sec_gaosan_{fl}f.png',
            'title': f'高三教学楼 — {fl}F 水平横截面图（1F三梯口铁链卷帘门 / 全玻璃东楼梯 / 黑板全在东）',
            'stairs': [
                (136.1 + gdx, 128.4 + gdz, st_s),
                (161.1 + gdx, 124.0 + gdz, st_s),
                (186.6 + gdx, 119.4 + gdz, st_e),
            ],
            'labels': [
                (f'G{fl}-1', '西阅览空间', '沙发+东书架+西海报', 136.1 + gdx, 119.6 + gdz),
                ('', '西楼梯(1F口装帘)' if fl == 1 else '西楼梯(敞开)', '4.2×5.2m', 136.1 + gdx, 126.9 + gdz),
                (f'G{fl}-2', '西段办公室', '6.0×7.2m', 141.2 + gdx, 119.6 + gdz),
                (f'G{fl}-3', '西段教室(黑板在东)', '10.0×7.2m', 149.2 + gdx, 119.6 + gdz),
                (f'G{fl}-4', '错位连廊拐角', '4.8×7.0m', 156.6 + gdx, 122.3 + gdz),
                (f'G{fl}-5', '北小储藏间', '4.2×7.2m', 161.1 + gdx, 115.2 + gdz),
                ('', '中楼梯(1F口装帘)' if fl == 1 else '中楼梯(敞开)', '4.2×5.2m', 161.1 + gdx, 122.6 + gdz),
                (f'G{fl}-6', '东段办公室', '6.0×7.2m', 166.2 + gdx, 115.2 + gdz),
                (f'G{fl}-7', '东段教室(黑板在东)', '10.0×7.2m', 174.2 + gdx, 115.2 + gdz),
                (f'G{fl}-8', '男女卫生间', '4.8×7.2m', 181.6 + gdx, 115.2 + gdz),
                (f'G{fl}-9', '全玻璃东楼梯', '对准走廊·1F口装帘' if fl == 1 else '三面全玻璃墙', 186.8 + gdx, 115.8 + gdz),
                ('', '南侧开放外廊 (2.6m宽)', '', 146.5 + gdx, 124.6 + gdz),
                ('', '南侧开放外廊 (2.6m宽)', '', 173.5 + gdx, 120.2 + gdz),
            ],
        }, rooms_db, doors_db)

    # ==================== 2. 萃华楼（1F / 2F / 3F） ====================
    cdx, cdz = org['cuihua_dx'], org['cuihua_dz']
    for fl in (1, 2, 3):
        yf = 0.25 + (fl - 1) * 3.4
        ty0 = -1.45 if fl == 1 else (1.95 if fl == 2 else 5.35)
        ty_tag = '-0.5F 厕所' if fl == 1 else (f'{fl - 0.5:.1f}F 厕所')
        st_w = '←下-0.5F / 上1.5F←' if fl == 1 else ('←上2.5F / 下1.5F→' if fl == 2 else '下2.5F →')
        st_e = '向东上 →' if fl == 1 else ('→上3F / ←下1F' if fl == 2 else '← 下2F')
        if fl == 1:
            raw_lbls = [
                ('', '圆塔北封闭区', '不可进', 14.8, 75.6),
                ('C1-1', '天文社(圆塔南整间)', '钥匙门(锁)', 14.8, 80.5),
                ('C-0.5厕', f'{ty_tag}(错半层)', '标高 y=-1.45m', 12.5, 68.6),
                ('C1-3', '西北副楼1F教室', '黑板在南', 18.8, 66.4),
                ('', '敞开台阶口(无门)', '北出口', 23.5, 62.9),
                ('C1-4', '西门厅', '西梯口装铁链卷帘门', 21.6, 80.5),
                ('C1-5', '1F 教室(黑板在东)', '10.0×7.6m', 29.4, 77.8),
                ('C1-6', '1F 办公室', '7.2×7.6m', 38.0, 77.8),
                ('C1-过道', '东过道', '南接东口K', 42.8, 79.4),
                ('C1-7', '全玻璃东楼梯', '1F梯口装铁链卷帘门', 46.8, 78.2),
                ('', '全段开放柱廊', '', 33.5, 83.0),
            ]
        elif fl == 2:
            raw_lbls = [
                ('', '圆塔2F北封闭区', '不可进', 14.8, 75.6),
                ('C2-1', '圆塔2F南圆厅', '南北分割同1F', 14.8, 80.5),
                ('C1.5厕', f'{ty_tag}(错半层)', '标高 y=+1.95m', 12.5, 68.6),
                ('C2-2', '西北副楼2F教室', '黑板在南', 18.8, 66.4),
                ('C2-3', '西门厅廊', '', 21.6, 80.5),
                ('C2-4', '2F 教室(黑板在东)', '10.0×7.6m', 29.4, 77.8),
                ('C2-5', '2F 办公室', '7.2×7.6m', 38.0, 77.8),
                ('C2-过道', '东过道', '', 42.8, 79.4),
                ('C2-6', '全玻璃东楼梯', '三面全玻璃幕墙', 46.8, 78.2),
                ('', '全段开放柱廊', '', 33.5, 83.0),
            ]
        else:
            raw_lbls = [
                ('', '北封闭弧', '', 15.6, 74.5),
                ('C3-1', '3F 小机房(中段)', '东防盗门(锁)+西窗', 14.8, 77.1),
                ('', '南封闭区(保留常闭门)', '不可进', 14.8, 80.8),
                ('C2.5厕', f'{ty_tag}(错半层·顶已严封)', '标高 y=+5.35m', 12.5, 68.6),
                ('C3-2', '副楼 2F 屋顶露台', '(3F退台)', 19.8, 66.2),
                ('C3-3', '西门厅廊', '', 21.6, 80.5),
                ('C3-4', '3F 电脑教室(黑板在东)', '10.0×7.6m', 29.4, 77.8),
                ('C3-5', '3F 钥匙办公室', '仅西隔墙开内门!', 38.0, 77.8),
                ('C3-过道', '东过道', '', 42.8, 79.4),
                ('C3-6', '全玻璃东楼梯', '三面全玻璃幕墙', 46.8, 78.2),
                ('', '全段开放柱廊', '', 33.5, 83.0),
            ]
        labels = [(c, t, d, lx + cdx, lz + cdz) for (c, t, d, lx, lz) in raw_lbls]
        render_section({
            'mod_id': 'cuihua',
            'floor_num': fl,
            'y_floor': yf,
            'y_min_proj': -1.55 if fl == 1 else yf - 1.80,
            'sub_cut': (10.9 + cdx, 69.5 + cdz, 14.18 + cdx, 74.05 + cdz, ty0, max(0.50, ty0 + 1.45), ty0 + 0.55),
            'bbox': (9.8 + cdx, 61.8 + cdz, 50.4 + cdx, 86.6 + cdz),
            'out': f'sec_cuihua_{fl}f.png',
            'title': f'萃华楼 — {fl}F 水平横截面图（过道+全玻璃东楼梯 / 1F两梯口铁链卷帘门 / 严封顶盖）',
            'stairs': [
                (16.6 + cdx, 71.8 + cdz, st_w),
                (46.6 + cdx, 81.8 + cdz, st_e),
            ],
            'labels': labels,
        }, rooms_db, doors_db)

    # ==================== 3. 宿舍北楼 ====================
    ddx = org['dorm_x'] - 132.0
    ddz = org['dorm_n_z'] - 7.2
    for fl in (1, 2, 3):
        yf = 0.25 + (fl - 1) * 3.4
        st_ns = '上2F ↑' if fl == 1 else ('↑上3F / 下1F↓' if fl == 2 else '下2F ↓')
        voids = [(144.32 + ddx, 19.72 + ddz, 147.85 + ddx, 21.85 + ddz)] if fl == 2 else []
        stairs = [(141.1 + ddx, 16.2 + ddz, st_ns), (158.8 + ddx, 13.0 + ddz, st_ns)]
        if fl == 1:
            stairs.append((145.6 + ddx, 19.1 + ddz, 'L梯上2F ←'))
            raw_lbls = [
                ('D1-1', '8分屏监控室', '11.0×4.5m', 137.5, 9.4),
                ('D1-2', '宿管值班室', '7.2×4.5m', 135.6, 16.2),
                ('', '南北主楼梯', '1F~3F贯通', 141.1, 14.5),
                ('D1-3', '围合门厅(全墙隔绝1F)', '东侧起L梯只到2F', 145.0, 20.8),
                ('D1-4', '宿管物资室', '8.4×4.5m', 152.2, 13.0),
                ('D1-5', '底楼东段活动室', '8.4×4.5m', 152.2, 19.8),
                ('D1-6', '东副楼梯', '4.8m宽', 158.8, 18.8),
            ]
        else:
            hall_lbl = ('D2-空', '2F挑空+西侧L梯到达口', '北沿接2F大厅', 145.8, 20.6) if fl == 2 else (
                'D3-自习', '3F 自习室(L梯不到3F)', '自习桌+书架', 145.5, 20.2)
            raw_lbls = [
                (f'D{fl}-0', '北盥洗', '3.2×4.5m', 133.6, 9.4),
                (f'D{fl}-0S', '南盥洗', '3.2×4.5m', 133.6, 16.2),
                (f'D{fl}-1', '西北寝室', '4.0×4.5m(仅放床)', 137.2, 9.4),
                (f'D{fl}-2', '西南寝室', '4.0×4.5m(仅放床)', 137.2, 16.2),
                (f'D{fl}-储', '北储物间', '3.8×4.5m', 141.1, 9.4),
                ('', '南北主楼梯', '', 141.1, 14.5),
                hall_lbl,
                (f'D{fl}-3', '东北寝室1', '4.2×4.5m(仅放床)', 150.1, 13.0),
                (f'D{fl}-4', '东南寝室1', '4.2×4.5m(仅放床)', 150.1, 19.8),
                (f'D{fl}-5', '东北寝室2', '4.2×4.5m(仅放床)', 154.3, 13.0),
                (f'D{fl}-6', '东南寝室2', '4.2×4.5m(仅放床)', 154.3, 19.8),
                ('', '2F/3F中央大厅', '', 145.5, 14.8),
            ]
        labels = [(c, t, d, lx + ddx, lz + ddz) for (c, t, d, lx, lz) in raw_lbls]
        render_section({
            'mod_id': 'north',
            'floor_num': fl,
            'y_floor': yf,
            'voids': voids,
            'bbox': (130.8 + ddx, 6.2 + ddz, 162.6 + ddx, 23.2 + ddz),
            'out': f'sec_dorm_{fl}f.png',
            'title': f'宿舍北楼 — {fl}F 水平横截面图（1F全墙围合门厅L梯只到2F + 南北向主楼梯 + 2F挑空·3F自习室）',
            'stairs': stairs,
            'labels': labels,
        }, rooms_db, doors_db)

    # ==================== 4. 食堂与小卖部 ====================
    cb = org['canteen_box']
    cx0, cz0, cx1, cz1 = cb
    render_section({
        'mod_id': 'north',
        'floor_num': 1,
        'y_floor': 0.25,
        'floor_h': 4.2,
        'bbox': (cx0 - 2.6, cz0 - 1.2, cx1 + 1.4, cz1 + 1.4),
        'out': 'sec_canteen_1f.png',
        'title': '食堂 — 1F 水平横截面图（紧凑衔接主干道与宿舍）',
        'labels': [
            ('E1-1', '1F 就餐大厅（成排连凳餐桌）', '含圆弧幕墙区', cx0 + 11.2, (cz0 + cz1) / 2),
            ('E1-2', '打饭窗口长台', '', cx1 - 6.8, (cz0 + cz1) / 2 - 1.5),
            ('E1-3', '东侧后厨隔间', '6.5×25.0m', cx1 - 3.2, (cz0 + cz1) / 2),
            ('', '西主入口雨棚 (E点)', '', cx0 - 0.8, cz1 - 14.1),
            ('', '西南圆弧玻璃幕墙 (R=11.5m)', '', cx0 + 6.0, cz1 - 4.2),
            ('', '南副入口', '', cx0 + 14.9, cz1 - 0.6),
        ],
    }, rooms_db, doors_db)

    render_section({
        'mod_id': 'north',
        'floor_num': 2,
        'y_floor': 4.45,
        'floor_h': 3.4,
        'bbox': (cx0 - 2.6, cz0 - 1.2, cx1 + 1.4, cz1 + 1.4),
        'out': 'sec_canteen_2f.png',
        'title': '食堂 — 2F 水平横截面图（封闭外观体块，保留圆弧双层玻璃幕墙）',
        'labels': [
            ('E2-1', '食堂 2F（封闭不可进，仅做外观立面与圆弧窗带）', '28.0×25.0m', (cx0 + cx1) / 2, (cz0 + cz1) / 2),
        ],
    }, rooms_db, doors_db)

    sb = cfg['shop']['box']
    sx0, sz0, sx1, sz1 = sb
    render_section({
        'mod_id': 'north',
        'floor_num': 1,
        'y_floor': 0.22,
        'y_cut': 1.45,
        'y_low': 0.75,
        'bbox': (sx0 - 2.2, sz0 - 0.8, sx1 + 3.0, sz1 + 6.5),
        'out': 'sec_shop_1f.png',
        'title': '小卖部 — 1F 水平横截面图（紧凑布局 / S1-1 与 S1-2 连通营业 / 门前绿篱夹道）',
        'labels': [
            ('S1-1', '小卖部西间(收银+正门)', '6.0×6.5m', sx0 + 3.0, sz0 + 2.1),
            ('S1-2', '连通小卖部东间(货架+冰柜)', '6.0×6.5m 中隔墙开门', sx0 + 9.0, sz0 + 4.7),
            ('S1-3', '东铺面(卷帘门封闭)', '6.0×6.5m', sx0 + 15.0, sz0 + 3.1),
            ('', '正门无遮挡入口通道(S点)', '4.2m宽', sx0 + 2.7, sz1 + 2.6),
            ('', '门前修剪绿篱带', '', sx0 + 8.7, sz1 + 2.6),
        ],
    }, rooms_db, doors_db)

    # ==================== 5. 南校门 & 图书馆截面 ====================
    g = cfg['gate']
    gcx, gz = sum(g['x']) / 2, g['z']
    render_section({
        'mod_id': 'library',
        'floor_num': 1,
        'y_floor': 0.45,
        'y_cut': 1.65,
        'y_low': 0.65,
        'bbox': (gcx - 20.5, gz - 6.5, gcx + 20.5, gz + 5.2),
        'out': 'sec_gate_1f.png',
        'title': '南校门与双保安室 — 1F 水平横截面图（中间大门常关 / 两侧各设双刷卡闸机通道）',
        'labels': [
            ('GT-1', '西塔保安室', '6.6×7.2m(核验窗+门)', gcx - 15.9, gz - 0.2),
            ('', '西双闸机', '3.2m', gcx - 11.0, gz - 2.8),
            ('', '中间 14m 铁艺大门（常关）', '北接紧凑进校大道', gcx, gz - 2.8),
            ('', '东双闸机', '3.2m', gcx + 11.0, gz - 2.8),
            ('GT-2', '东塔保安室', '6.6×7.2m(核验窗+门)', gcx + 15.9, gz - 0.2),
        ],
    }, rooms_db, doors_db)

    ldx, ldz = org['lib_dx'], org['lib_dz']
    render_section({
        'mod_id': 'library',
        'floor_num': 1,
        'y_floor': 1.50,
        'y_cut': 3.20,
        'y_low': 0.35,
        'bbox': (71.0 + ldx, 48.0 + ldz, 117.0 + ldx, 80.5 + ldz),
        'out': 'sec_library_podium.png',
        'title': '图书馆裙楼与正门台阶 — 1F~2F 水平横截面轮廓（实心不可进地标）',
        'labels': [
            ('LB-裙楼', '图书馆裙楼主体（实心不可进地标）', '40.4×21.0m 退台翼楼 + 六柱门廊', 94.0 + ldx, 61.0 + ldz),
            ('', '正门 8 级大台阶', '12.0×5.6m', 94.0 + ldx, 75.4 + ldz),
            ('', '西镜面真水水池', '', 62.5, 30.2),
            ('', '东镜面真水水池', '', 91.5, 30.2),
        ],
    }, rooms_db, doors_db)


if __name__ == '__main__':
    build_all()
