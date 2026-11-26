"""v4.3 紧凑化结构校园建模脚本（174×88m 紧凑间距总图 / 全玻璃零缝隙东楼梯 / 宿舍1F围合L梯+南北主梯 / 1F梯口铁链卷帘门）。

用法:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/build_campus_v4.py -- [模块 id ...]
"""
import json
import math
import os
import sys
import time

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campus_arch as A  # noqa: E402
import mc_lib as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CFG_PATH = os.path.join(ROOT, 'data', 'map', 'campus_layout.json')
OUT_DIR = os.path.join(ROOT, 'assets', 'env', 'campus')
ROOMS_PATH = os.path.join(ROOT, 'data', 'map', 'campus_rooms.json')
DOORS_PATH = os.path.join(ROOT, 'data', 'map', 'campus_doors.json')

FLOOR_H = 3.4


def _add_room(rooms, mod_id, rtype, floor, x0, z0, x1, z1, y_floor, ceil_h=FLOOR_H - 0.22, rot_override=None):
    r = {
        'type': rtype,
        'floor': floor,
        'box': [round(x0, 2), round(z0, 2), round(x1, 2), round(z1, 2)],
        'y': round(y_floor, 2),
        'ceil': round(y_floor + ceil_h, 2),
    }
    if rot_override is not None:
        r['rot'] = rot_override
    rooms.setdefault(mod_id, []).append(r)


def _add_door(doors, mod_id, x, y, z, dtype='door', facing='south', lock=''):
    doors.setdefault(mod_id, []).append({
        'pos': [round(x, 2), round(y, 2), round(z, 2)],
        'type': dtype,
        'facing': facing,
        'lock': lock,
    })


# ================================================================ 1. extras（紧凑 174×88m 地面、路网、围墙、行道绿植）

def build_extras(cfg, coll):
    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)
    grass = L.mat('grass')
    asphalt = L.mat('asphalt')
    paving = L.mat('paving')
    curb = L.mat('concrete')
    cm = L.mat('collision')

    org = cfg['origins']
    pit_x0, pit_x1 = 11.0 + org['cuihua_dx'], 18.8 + org['cuihua_dx']   # 8.0 .. 15.8
    pit_z0, pit_z1 = 69.8 + org['cuihua_dz'], 73.8 + org['cuihua_dz']   # 20.8 .. 24.8

    ground_rects = [
        (0, 10, 48, pit_z0),
        (0, pit_z1, 48, 88),
        (0, pit_z0, pit_x0, pit_z1),
        (pit_x1, pit_z0, 48, pit_z1),
        (48, 0, 174, 88),
    ]
    for x0, z0, x1, z1 in ground_rects:
        A.box(acc, x0, -0.5, z0, x1, 0.0, z1, grass, skip=('-y',))
        A.box(col, x0, -0.5, z0, x1, 0.0, z1, cm)

    # 校门外沥青市政路
    A.box(acc, 44, -0.5, 88, 110, -0.02, 104, asphalt, skip=('-y',))
    A.box(col, 44, -0.5, 88, 110, -0.02, 104, cm)

    roads = [
        (3.0, 41.0, 170.0, 46.0, asphalt),    # 紧凑东西主干道（5m宽）
        (48.0, 10.0, 53.0, 86.0, asphalt),    # 西侧南北干道（5m宽）
        (101.0, 2.0, 106.0, 86.0, asphalt),   # 东侧南北干道（5m宽）
        (106.0, 2.0, 108.6, 41.0, paving),    # 宿舍西侧门厅步道
        (170.0, 2.0, 173.6, 86.0, paving),    # 东环步道
        (108.5, 1.2, 148.2, 4.0, paving),     # 宿舍北后巷（连小卖部）
        (108.5, 18.8, 138.0, 24.4, paving),   # 宿舍南北楼紧凑中庭
        (137.7, 3.8, 143.2, 41.0, paving),    # 宿舍与食堂之间 5.3m 步道
        (143.0, 7.7, 171.0, 14.2, paving),    # 小卖部门前及食堂北侧铺装
        (108.5, 39.2, 171.0, 41.0, paving),   # 宿舍南楼与食堂南侧人行道
        (6.0, 35.4, 48.0, 41.0, paving),      # 萃华楼南侧紧凑前坪
        (1.2, 24.0, 7.2, 36.0, paving),       # 萃华楼西侧翻墙点步道
        (18.5, 11.0, 22.2, 14.6, paving),     # 萃华楼西北副楼北出口步道
        (106.0, 59.4, 165.0, 69.5, paving),   # 高三楼南侧紧凑前坪
        (106.0, 46.0, 110.5, 64.0, paving),   # 高三楼西口衔接铺装
    ]
    for x0, z0, x1, z1, m in roads:
        A.box(acc, x0, 0.0, z0, x1, 0.03, z1, m, skip=('-y',))
        if m == asphalt:
            A.box(acc, x0, 0.0, z0 - 0.12, x1, 0.052, z0, curb, skip=('-y',))
            A.box(acc, x0, 0.0, z1, x1, 0.052, z1 + 0.12, curb, skip=('-y',))

    _build_wall(acc, col, cfg)

    t_idx = 10
    # 1) 萃华楼北侧紧凑树列与绿篱
    for tx, tz, sc in [
        (4.5, 13.0, 0.85), (10.5, 12.2, 0.82), (25.5, 12.5, 0.88), (32.0, 13.5, 0.84),
        (38.5, 12.5, 0.88), (44.5, 14.0, 0.84), (28.0, 18.0, 0.82), (36.0, 18.0, 0.85),
        (43.5, 22.0, 0.82), (4.0, 38.0, 0.80),
    ]:
        A.add_tree(acc, col, tx, tz, 0.0, scale=sc, seed=t_idx, species='oak' if t_idx % 3 else 'birch')
        t_idx += 1
    A.add_hedge(acc, col, 23.0, 23.2, 40.5, 24.0, 0.0, 0.70)

    # 2) 操场西缘与南缘紧凑行道树
    for tz in (54, 65, 76):
        A.add_tree(acc, col, 1.5, tz, 0.0, scale=0.80, seed=t_idx)
        t_idx += 1
    for tx in (10, 22, 34, 44):
        A.add_tree(acc, col, tx, 86.5, 0.0, scale=0.80, seed=t_idx)
        t_idx += 1

    # 3) 高三楼南北紧凑花坛与绿林
    for hx0, hx1 in ((109.0, 125.0), (129.0, 145.0), (149.0, 165.0)):
        A.add_hedge(acc, col, hx0, 71.5, hx1, 72.3, 0.0, 0.72)
        A.add_hedge(acc, col, hx0, 84.6, hx1, 85.4, 0.0, 0.72)
        A.add_hedge(acc, col, hx0, 72.3, hx0 + 0.8, 84.6, 0.0, 0.72)
        A.add_hedge(acc, col, hx1 - 0.8, 72.3, hx1, 84.6, 0.0, 0.72)
    for tx, tz, sc in [
        (113, 75.5, 0.88), (121, 78.0, 0.85), (116, 82.2, 0.86),
        (133, 75.5, 0.88), (141, 78.0, 0.86), (136, 82.2, 0.84),
        (153, 75.5, 0.88), (161, 78.0, 0.85), (156, 82.2, 0.86),
        (167.5, 54.0, 0.86), (167.5, 65.0, 0.84),
        (113, 49.5, 0.80), (122, 49.5, 0.82), (130, 48.0, 0.80),
        (142, 47.6, 0.80), (154, 47.6, 0.80),
    ]:
        A.add_tree(acc, col, tx, tz, 0.0, scale=sc, seed=t_idx, species='oak' if t_idx % 4 else 'acacia')
        t_idx += 1

    # 4) 宿舍紧凑中庭绿植
    A.add_hedge(acc, col, 125.0, 20.6, 136.5, 22.6, 0.0, 0.66)
    for tx, tz, sc in [
        (128.0, 21.6, 0.74), (134.0, 21.6, 0.74),
        (124.0, 2.2, 0.76), (134.0, 2.2, 0.76),
    ]:
        A.add_tree(acc, col, tx, tz, 0.0, scale=sc, seed=t_idx)
        t_idx += 1

    acc.build('extras', coll)
    col.build('extras-colonly', coll)


def _build_wall(acc, col, cfg):
    pts = cfg['wall']
    g = cfg['gate']
    gx0, gx1, gz = g['x'][0] - 12.2, g['x'][1] + 12.2, g['z']
    segs = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if abs(a[1] - gz) < 0.01 and abs(b[1] - gz) < 0.01:
            lo, hi = min(a[0], b[0]), max(a[0], b[0])
            segs += [((lo, gz), (gx0, gz)), ((gx1, gz), (hi, gz))]
        else:
            segs.append((a, b))
    stone, plaster, cap, iron = L.mat('stone'), L.mat('plaster'), L.mat('concrete'), L.mat('metal_dark')
    cm = L.mat('collision')
    for a, b in segs:
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dz)
        if length < 0.1:
            continue
        ang = math.atan2(dz, dx)
        cx, cz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        A.obox(acc, cx, cz, length + 0.4, 0.46, -0.1, 0.55, ang, stone)
        A.obox(acc, cx, cz, length + 0.3, 0.28, 0.55, 2.3, ang, plaster)
        A.obox(acc, cx, cz, length + 0.4, 0.40, 2.3, 2.42, ang, cap)
        A.obox(col, cx, cz, length + 0.4, 0.46, -0.1, 3.0, ang, cm)
        n = max(1, int(length / 4.5))
        for k in range(n + 1):
            t = k / n
            A.obox(acc, a[0] + dx * t, a[1] + dz * t, 0.48, 0.48, 0.55, 2.52, ang, plaster)
            A.obox(acc, a[0] + dx * t, a[1] + dz * t, 0.58, 0.58, 2.52, 2.64, ang, cap)
        A.obox(acc, cx, cz, length, 0.05, 2.95, 3.0, ang, iron)
        bars = max(2, int(length / 0.25))
        for k in range(bars):
            t = (k + 0.5) / bars
            A.obox(acc, a[0] + dx * t, a[1] + dz * t, 0.025, 0.025, 2.42, 3.0, ang, iron)


# ================================================================ 2. library（紧凑中轴：图书馆 + 水景 + 圆形广场 + 短大道 + 校门）

def build_library(cfg, coll, doors):
    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)
    water_acc = L.MeshAcc()
    cm = L.mat('collision')
    plaza_m = L.mat('plaza')
    paving_m = L.mat('paving_light')
    curb_m = L.mat('concrete')

    org = cfg['origins']
    dx, dz = org['lib_dx'], org['lib_dz']   # -17.0, -45.5 -> 中轴 X = 77.0
    plz = cfg['plaza']
    pcx, pcz, pr = plz['center'][0], plz['center'][1], plz['radius']   # 77, 54, 12.5
    gz = cfg['gate']['z']                                              # 88

    _build_gate(acc, col, cfg['gate'], coll, doors)

    # 紧凑进校大道（z: 54 → 88）与校门衔接坪
    ax0, ax1 = plz['avenue_x'][0] - 0.4, plz['avenue_x'][1] + 0.4      # 69.6 .. 84.4
    A.box(acc, ax0, 0.0, pcz, ax1, 0.05, gz + 5.5, plaza_m, skip=('-y',))
    A.box(acc, pcx - 15.5, 0.0, gz - 4.8, pcx + 15.5, 0.048, gz + 5.0, plaza_m, skip=('-y',))
    A.box(acc, ax0 - 0.35, 0.0, pcz + pr - 0.5, ax0, 0.11, gz - 4.8, curb_m, skip=('-y',))
    A.box(acc, ax1, 0.0, pcz + pr - 0.5, ax1 + 0.35, 0.11, gz - 4.8, curb_m, skip=('-y',))

    # 紧凑圆形中心广场（R = 12.5m）与东西衔接铺装
    A.cyl(acc, pcx, pcz, pr, 0.0, 0.055, plaza_m, seg=48, cap_bot=False)
    A.arc_wall(acc, None, pcx, pcz, pr, pr + 0.32, 0.0, 0.095, 0, 2 * math.pi, curb_m, seg=48, add_col=False, cap_ends=False)
    A.box(acc, 53.0, 0.0, 41.0, 101.0, 0.042, 46.5, paving_m, skip=('-y',))
    A.box(acc, 53.0, 0.0, 50.5, 101.0, 0.042, 57.5, paving_m, skip=('-y',))

    # 大道两侧紧凑对称绿篱与行道树
    for side, (hx0, hx1) in enumerate(((54.5, 68.2), (85.8, 99.5))):
        A.add_hedge(acc, col, hx0, 67.2, hx1, 68.0, 0.0, 0.72)
        if side == 0:
            A.add_hedge(acc, col, 54.5, gz - 5.8, 63.8, gz - 5.0, 0.0, 0.72)
        else:
            A.add_hedge(acc, col, 90.2, gz - 5.8, 99.5, gz - 5.0, 0.0, 0.72)
        ave_tx = 66.8 if side == 0 else 87.2
        for k, tz in enumerate((71.0, 77.5)):
            A.add_tree(acc, col, ave_tx, tz, 0.0, scale=0.88, seed=210 + side * 20 + k)
        out_tx = 57.2 if side == 0 else 96.8
        for k, tz in enumerate((60.5, 70.5, 79.0)):
            A.add_tree(acc, col, out_tx, tz, 0.0, scale=0.84, seed=220 + side * 20 + k, species='birch' if k % 2 else 'oak')
        A.add_bench(acc, 62.8 if side == 0 else 91.2, pcz, 0.05, math.pi / 2 if side == 0 else -math.pi / 2)

    # 图书馆建筑本体（整体按 dx, dz 刚性平移，比例细节 100% 保持！）
    facade, sand, concrete, glass_b, frame, roof_m = (
        L.mat('facade'), L.mat('sandstone'), L.mat('concrete'), L.mat('glass_blue'), L.mat('frame'), L.mat('roof')
    )
    A.box(acc, 74.0 + dx, 0.0, 49.0 + dz, 114.0 + dx, 1.5, 72.5 + dz, concrete)
    A.box(col, 74.0 + dx, 0.0, 49.0 + dz, 114.0 + dx, 1.5, 72.5 + dz, cm)
    for i in range(8):
        t0, t1 = i / 8, (i + 1) / 8
        A.box(acc, 88.0 + dx, 0.0, 72.5 + dz + 5.6 * t0, 100.0 + dx, 1.5 * (1.0 - t0), 72.5 + dz + 5.6 * t1, plaza_m)
    A.box(acc, 87.3 + dx, 0.0, 72.5 + dz, 88.0 + dx, 1.72, 78.3 + dz, concrete)
    A.box(acc, 100.0 + dx, 0.0, 72.5 + dz, 100.7 + dx, 1.72, 78.3 + dz, concrete)
    A.poly(col, [(88 + dx, 1.5, 72.5 + dz), (100 + dx, 1.5, 72.5 + dz),
                 (100 + dx, 0.0, 78.1 + dz), (88 + dx, 0.0, 78.1 + dz)], cm)

    A.box(acc, 77.0 + dx, 1.5, 50.5 + dz, 111.0 + dx, 9.3, 71.5 + dz, facade)
    A.box(acc, 73.8 + dx, 1.5, 53.5 + dz, 77.2 + dx, 8.3, 68.5 + dz, facade)
    A.box(acc, 110.8 + dx, 1.5, 53.5 + dz, 114.2 + dx, 8.3, 68.5 + dz, facade)
    A.box(col, 73.8 + dx, 1.5, 50.5 + dz, 114.2 + dx, 9.6, 71.5 + dz, cm)
    A.box(acc, 76.6 + dx, 5.3, 50.1 + dz, 111.4 + dx, 5.65, 71.9 + dz, concrete)
    A.box(acc, 76.5 + dx, 9.1, 50.0 + dz, 111.5 + dx, 9.55, 72.0 + dz, concrete)
    A.box(acc, 77.0 + dx, 9.55, 50.5 + dz, 111.0 + dx, 9.85, 71.5 + dz, roof_m)
    A.box(acc, 73.5 + dx, 8.2, 53.2 + dz, 77.2 + dx, 8.55, 68.8 + dz, concrete)
    A.box(acc, 110.8 + dx, 8.2, 53.2 + dz, 114.5 + dx, 8.55, 68.8 + dz, concrete)

    A.box(acc, 86.4 + dx, 6.2, 71.5 + dz, 101.6 + dx, 7.0, 75.2 + dz, facade)
    A.box(acc, 86.1 + dx, 7.0, 71.3 + dz, 101.9 + dx, 7.35, 75.4 + dz, concrete)
    A.box(acc, 86.9 + dx, 7.35, 71.7 + dz, 101.1 + dx, 8.25, 74.8 + dz, glass_b)
    A.box(acc, 86.5 + dx, 8.25, 71.4 + dz, 101.5 + dx, 8.65, 75.1 + dz, sand)
    for px in (87.3, 90.0, 92.7, 95.3, 98.0, 100.7):
        A.round_col(acc, col, px + dx, 74.4 + dz, 0.32, 1.5, 6.2, 'facade')
    A.box(acc, 88.2 + dx, 1.5, 71.48 + dz, 99.8 + dx, 6.0, 71.58 + dz, glass_b)
    for mx in (90.5, 92.8, 95.2, 97.5):
        A.box(acc, mx + dx - 0.05, 1.5, 71.52 + dz, mx + dx + 0.05, 6.0, 71.64 + dz, frame)
    for wy0, wy1 in ((2.0, 5.1), (5.8, 8.85)):
        for wx in range(78, 110, 3):
            if 86 <= wx <= 100:
                continue
            A.box(acc, wx + dx, wy0, 71.46 + dz, wx + dx + 2.2, wy1, 71.56 + dz, glass_b)
            A.box(acc, wx + dx, wy0, 50.44 + dz, wx + dx + 2.2, wy1, 50.54 + dz, glass_b)
        for wz in range(55, 68, 3):
            A.box(acc, 73.74 + dx, wy0, wz + dz, 73.84 + dx, wy1, wz + dz + 2.1, glass_b)
            A.box(acc, 114.16 + dx, wy0, wz + dz, 114.26 + dx, wy1, wz + dz + 2.1, glass_b)

    A.box(acc, 84.0 + dx, 9.6, 54.5 + dz, 104.0 + dx, 28.5, 66.5 + dz, facade)
    A.box(acc, 87.0 + dx, 9.6, 53.5 + dz, 101.0 + dx, 28.5, 67.5 + dz, facade)
    A.box(col, 84.0 + dx, 9.6, 53.5 + dz, 104.0 + dx, 29.0, 67.5 + dz, cm)
    for fl in range(6):
        wy0 = 10.4 + fl * 2.95
        wy1 = wy0 + 1.95
        A.box(acc, 83.8 + dx, wy0 - 0.25, 54.3 + dz, 104.2 + dx, wy0 - 0.04, 66.7 + dz, concrete)
        A.box(acc, 86.8 + dx, wy0 - 0.25, 53.3 + dz, 101.2 + dx, wy0 - 0.04, 67.7 + dz, concrete)
        for wx in (85.0, 101.6):
            A.box(acc, wx + dx, wy0, 66.46 + dz, wx + dx + 1.5, wy1, 66.56 + dz, glass_b)
            A.box(acc, wx + dx, wy0, 54.44 + dz, wx + dx + 1.5, wy1, 54.54 + dz, glass_b)
        for wx in range(88, 100, 2):
            A.box(acc, wx + dx + 0.18, wy0, 67.46 + dz, wx + dx + 1.55, wy1, 67.56 + dz, glass_b)
            A.box(acc, wx + dx + 0.18, wy0, 53.44 + dz, wx + dx + 1.55, wy1, 53.54 + dz, glass_b)
            A.box(acc, wx + dx - 0.06, wy0 - 0.1, 67.48 + dz, wx + dx + 0.12, wy1 + 0.85, 67.68 + dz, facade)
        for wz in range(56, 66, 2):
            A.box(acc, 83.94 + dx, wy0, wz + dz + 0.18, 84.04 + dx, wy1, wz + dz + 1.55, glass_b)
            A.box(acc, 103.96 + dx, wy0, wz + dz + 0.18, 104.06 + dx, wy1, wz + dz + 1.55, glass_b)

    A.box(acc, 83.7 + dx, 28.5, 53.3 + dz, 104.3 + dx, 29.0, 67.7 + dz, concrete)
    A.box(acc, 84.5 + dx, 29.0, 54.2 + dz, 103.5 + dx, 29.2, 66.8 + dz, roof_m)
    for px in range(85, 104, 2):
        for pz in (54.4, 66.6):
            A.box(acc, px + dx - 0.16, 29.0, pz + dz - 0.16, px + dx + 0.16, 31.1, pz + dz + 0.16, facade)
    for pz in range(56, 66, 2):
        for px in (84.6, 103.4):
            A.box(acc, px + dx - 0.16, 29.0, pz + dz - 0.16, px + dx + 0.16, 31.1, pz + dz + 0.16, facade)
    for bx0, bz0, bx1, bz1 in ((84.4, 54.2, 103.6, 54.7), (84.4, 66.3, 103.6, 66.8),
                               (84.4, 54.2, 84.9, 66.8), (103.1, 54.2, 103.6, 66.8)):
        A.box(acc, bx0 + dx, 30.8, bz0 + dz, bx1 + dx, 31.25, bz1 + dz, facade)
    dr = 4.6
    lcx, lcz = 94.0 + dx, 60.5 + dz
    dpts = [(lcx, 29.2, lcz - dr), (lcx + dr, 29.2, lcz), (lcx, 29.2, lcz + dr), (lcx - dr, 29.2, lcz)]
    for i in range(4):
        A.poly(acc, [dpts[i], dpts[(i + 1) % 4], (lcx, 31.2, lcz)], glass_b)

    for k, tx in enumerate((57, 65, 73, 81, 89, 97)):
        A.add_tree(acc, col, tx, 1.8, 0.0, scale=0.80, seed=280 + k)
    for side_x in (55.0, 99.0):
        for k, tz in enumerate((9.0, 17.5, 25.5)):
            A.add_tree(acc, col, side_x, tz, 0.0, scale=0.80, seed=290 + int(side_x) + k)

    # 馆前紧凑水池与花坛（z: 27 → 41）
    A.box(acc, 53.0, 0.0, 26.8, 101.0, 0.045, 41.0, paving_m, skip=('-y',))
    for side, (sx0, sx1) in enumerate(((56.2, 68.8), (85.2, 97.8))):
        px0, px1 = sx0 + 2.0, sx1 - 2.0
        pz0, pz1 = 28.5, 32.0
        A.box(acc, px0 - 0.3, 0.045, pz0 - 0.3, px1 + 0.3, 0.42, pz0, curb_m)
        A.box(acc, px0 - 0.3, 0.045, pz1, px1 + 0.3, 0.42, pz1 + 0.3, curb_m)
        A.box(acc, px0 - 0.3, 0.045, pz0, px0, 0.42, pz1, curb_m)
        A.box(acc, px1, 0.045, pz0, px1 + 0.3, 0.42, pz1, curb_m)
        A.box(acc, px0, 0.045, pz0, px1, 0.10, pz1, L.mat('gravel'))
        A.box(col, px0, 0.0, pz0, px1, 0.10, pz1, cm)
        A.poly(water_acc, [(px0, 0.34, pz0), (px0, 0.34, pz1), (px1, 0.34, pz1), (px1, 0.34, pz0)], L.mat('water'))

        lz0, lz1 = 33.8, 39.2
        A.box(acc, sx0, 0.045, lz0, sx1, 0.24, lz1, L.mat('grass'))
        A.box(acc, sx0 - 0.2, 0.045, lz0 - 0.2, sx1 + 0.2, 0.28, lz0, curb_m)
        A.box(acc, sx0 - 0.2, 0.045, lz1, sx1 + 0.2, 0.28, lz1 + 0.2, curb_m)
        A.box(acc, sx0 - 0.2, 0.045, lz0, sx0, 0.28, lz1, curb_m)
        A.box(acc, sx1, 0.045, lz0, sx1 + 0.2, 0.28, lz1, curb_m)
        A.box(col, sx0 - 0.2, 0.0, lz0 - 0.2, sx1 + 0.2, 0.28, lz1 + 0.2, cm)
        A.add_hedge(acc, col, sx0 + 0.6, lz0 + 0.5, sx1 - 0.6, lz0 + 1.2, 0.24, 0.56)
        for k, tx in enumerate((sx0 + 2.4, (sx0 + sx1) / 2, sx1 - 2.4)):
            A.add_tree(acc, col, tx, lz1 - 1.8, 0.24, scale=0.80, seed=310 + side * 10 + k)
        A.add_bench(acc, (sx0 + sx1) / 2, 40.2, 0.045, 0.0)

    acc.build('library', coll)
    water_acc.build('library_water', coll)
    col.build('library-colonly', coll)


def _build_gate(acc, col, g, coll, doors):
    x0, x1, z = g['x'][0], g['x'][1], g['z']
    cm = L.mat('collision')
    facade, sand, cap, stone = L.mat('facade'), L.mat('sandstone'), L.mat('concrete'), L.mat('stone')
    metal, dark = L.mat('metal'), L.mat('metal_dark')

    for side in (-1, 1):
        px0, px1 = (x0 - 2.4, x0) if side < 0 else (x1, x1 + 2.4)
        A.box(acc, px0 - 0.1, 0, z - 1.8, px1 + 0.1, 0.5, z + 1.8, stone)
        A.box(acc, px0, 0.5, z - 1.7, px1, 5.2, z + 1.7, facade)
        A.box(acc, px0 - 0.12, 5.2, z - 1.82, px1 + 0.12, 6.0, z + 1.82, sand)
        A.box(acc, px0 - 0.16, 6.0, z - 1.86, px1 + 0.16, 6.12, z + 1.86, cap)
        A.box(acc, (px0 + px1) / 2 - 0.22, 6.12, z - 0.22, (px0 + px1) / 2 + 0.22, 6.55, z + 0.22, L.mat('light_warm'))
        A.box(col, px0, 0, z - 1.8, px1, 6.6, z + 1.8, cm)

        lane_x0, lane_x1 = (x0 - 5.6, x0 - 2.4) if side < 0 else (x1 + 2.4, x1 + 5.6)
        A.add_turnstiles(acc, col, lane_x0, lane_x1, z, y0=0.05)

        inner = x0 - 5.6 if side < 0 else x1 + 5.6
        outer = inner + side * 6.6
        tx0, tx1 = min(inner, outer), max(inner, outer)
        tz0, tz1 = z - 3.6, z + 3.6
        A.box(acc, tx0 - 0.1, 0, tz0 - 0.1, tx1 + 0.1, 0.45, tz1 + 0.1, stone)
        A.wall_x(acc, col, tx0, tx1, tz0 + 0.14, 0.45, 3.6, 0.28, 'facade', dado=True)
        A.wall_x(acc, col, tx0, tx1, tz1 - 0.14, 0.45, 3.6, 0.28, 'facade', dado=True)
        outer_wall_x = tx0 + 0.14 if side < 0 else tx1 - 0.14
        inner_wall_x = tx1 - 0.14 if side < 0 else tx0 + 0.14
        A.wall_z(acc, col, tz0, tz1, outer_wall_x, 0.45, 3.6, 0.28, 'facade', dado=True)
        A.wall_z(acc, col, tz0, tz1, inner_wall_x, 0.45, 3.6, 0.28, 'facade', [
            (tz0 + 1.1, tz0 + 3.2, 1.35, 2.55, 'window'),
            (tz1 - 2.4, tz1 - 1.3, 0.45, 2.55, 'door'),
        ], dado=True)
        cnt_x0, cnt_x1 = (tx1, tx1 + 0.42) if side < 0 else (tx0 - 0.42, tx0)
        A.box(acc, cnt_x0, 1.30, tz0 + 1.1, cnt_x1, 1.38, tz0 + 3.2, cap)
        A.box(acc, tx0 + 0.28, 0.44, tz0 + 0.28, tx1 - 0.28, 0.48, tz1 - 0.28, L.mat('floor'))
        desk_x0, desk_x1 = (tx1 - 1.3, tx1 - 0.45) if side < 0 else (tx0 + 0.45, tx0 + 1.3)
        A.box(acc, desk_x0, 0.48, tz0 + 1.2, desk_x1, 1.22, tz0 + 3.1, L.mat('wood_dark'))
        A.box(col, tx0, 0, tz0, tx1, 0.48, tz1, cm)
        _add_door(doors, 'library', inner_wall_x, 0.45, tz1 - 1.85, 'guard_room', 'east' if side < 0 else 'west')

        A.slab_with_ceiling(acc, col, tx0 - 0.22, tz0 - 0.22, tx1 + 0.22, tz1 + 0.22, 3.56, 3.80, 'concrete', 'concrete', add_col=True)
        hx0, hx1 = (inner - 4.4, inner) if side < 0 else (inner, inner + 4.4)
        sx0, sx1 = (outer, outer + 2.2) if side < 0 else (outer - 2.2, outer)
        A.box(acc, hx0, 3.8, tz0 + 0.6, hx1, 8.2, tz1 - 0.6, facade)
        A.box(acc, hx0 - 0.12, 8.2, tz0 + 0.48, hx1 + 0.12, 9.2, tz1 - 0.48, sand)
        A.box(acc, hx0, 9.2, tz0 + 0.6, hx1, 10.4, tz1 - 0.6, facade)
        A.box(acc, hx0 - 0.16, 10.4, tz0 + 0.44, hx1 + 0.16, 11.2, tz1 - 0.44, sand)
        A.box(acc, hx0 - 0.2, 11.2, tz0 + 0.4, hx1 + 0.2, 11.34, tz1 - 0.4, cap)
        A.box(acc, sx0, 3.8, tz0 + 0.6, sx1, 6.2, tz1 - 0.6, facade)
        A.box(acc, sx0 - 0.12, 6.2, tz0 + 0.48, sx1 + 0.12, 7.0, tz1 - 0.48, sand)
        A.box(acc, sx0 - 0.16, 7.0, tz0 + 0.44, sx1 + 0.16, 7.12, tz1 - 0.44, cap)
        for zz in (tz0 + 0.6, tz1 - 0.6):
            for k in range(3):
                if side > 0 and zz > z and k == 1:
                    continue
                wx = hx0 + 0.9 + k * 1.3
                A.box(acc, wx - 0.2, 4.5, zz - 0.04, wx + 0.2, 7.6, zz + 0.04, L.mat('glass_dark'))
        A.box(col, tx0, 3.8, tz0, tx1, 11.3, tz1, cm)

    _grille(acc, (x0, z), (x1, z), 1.85, metal, dark)
    A.box(col, x0, 0, z - 0.12, x1, 1.9, z + 0.12, cm)

    # 校名牌挂在右侧（东侧）保安室上方的高门楼塔柱南面：灰白底 + 黑绿字
    hx = x1 + 5.6 + 2.2
    A.box(acc, hx - 0.79, 4.16, z + 3.00, hx + 0.79, 8.04, z + 3.05, dark)
    A.box(acc, hx - 0.75, 4.20, z + 3.00, hx + 0.75, 8.00, z + 3.08, L.mat('sign_graywhite'))
    for k, ch in enumerate(g.get('name', '荒烟中学')):
        A.text_mesh(coll, ch, (hx, 7.4 - k * 0.88, z + 3.09), 0.72, 'sign_darkgreen', facing='south')


def _grille(acc, a, b, h, m, frame):
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dz)
    if length < 0.1:
        return
    ang = math.atan2(dz, dx)
    cx, cz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    A.obox(acc, cx, cz, length, 0.06, 0.1, 0.18, ang, frame)
    A.obox(acc, cx, cz, length, 0.06, h - 0.08, h, ang, frame)
    A.obox(acc, cx, cz, length, 0.04, h * 0.55, h * 0.55 + 0.05, ang, frame)
    n = max(2, int(length / 0.18))
    for k in range(n + 1):
        t = k / n
        A.obox(acc, a[0] + dx * t, a[1] + dz * t, 0.025, 0.025, 0.1, h, ang, m)


# ================================================================ 3. gaosan（紧凑平移 dx, dz，内部结构 100% 完整）

def build_gaosan(cfg, coll, rooms, doors):
    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)
    cm = L.mat('collision')
    facade, flr, concrete = L.mat('facade'), L.mat('floor'), L.mat('concrete')

    org = cfg['origins']
    dx, dz = org['gaosan_dx'], org['gaosan_dz']  # -25.5, -62.0

    west_segs = [
        (134.0 + dx, 138.2 + dx, 'lounge_west'),
        (138.2 + dx, 144.2 + dx, 'office'),
        (144.2 + dx, 154.2 + dx, 'classroom'),
    ]
    east_segs = [
        (159.0 + dx, 163.2 + dx, 'stair_mid'),
        (163.2 + dx, 169.2 + dx, 'office'),
        (169.2 + dx, 179.2 + dx, 'classroom'),
        (179.2 + dx, 184.0 + dx, 'toilet'),
    ]

    A.box(acc, 133.7 + dx, 0.0, 115.7 + dz, 159.1 + dx, 0.25, 126.0 + dz, concrete)
    A.box(col, 133.7 + dx, 0.0, 115.7 + dz, 159.1 + dx, 0.25, 126.0 + dz, cm)
    A.box(acc, 154.1 + dx, 0.0, 111.3 + dz, 184.3 + dx, 0.25, 121.6 + dz, concrete)
    A.box(col, 154.1 + dx, 0.0, 111.3 + dz, 184.3 + dx, 0.25, 121.6 + dz, cm)

    A.gaosan_south_stair_tower(acc, col, 134.0 + dx, 138.2 + dx, 125.8 + dz, 131.0 + dz, 0.25, 3, FLOOR_H, open_west_1f=True)
    A.gaosan_south_stair_tower(acc, col, 159.0 + dx, 163.2 + dx, 121.4 + dz, 126.6 + dz, 0.25, 3, FLOOR_H, open_west_1f=False)
    A.glass_stair_box_east(acc, col, 184.0 + dx, 189.2 + dx, 117.4 + dz, 121.4 + dz, 0.25, 3, FLOOR_H)
    A.build_stair_flights_x(acc, col, 117.6 + dz, 121.2 + dz, 184.0 + dx, 188.9 + dx, 0.25, 3, FLOOR_H, first_side='south')

    A.add_chain_shutter_x(acc, col, 134.26 + dx, 137.94 + dx, 125.8 + dz, 0.25, 3.35)
    _add_door(doors, 'gaosan', 136.1 + dx, 0.25, 125.8 + dz, 'chain_shutter', 'north', 'curfew_23')
    A.add_chain_shutter_x(acc, col, 159.26 + dx, 162.94 + dx, 121.4 + dz, 0.25, 3.35)
    _add_door(doors, 'gaosan', 161.1 + dx, 0.25, 121.4 + dz, 'chain_shutter', 'north', 'curfew_23')
    A.add_chain_shutter_z(acc, col, 118.88 + dz, 121.24 + dz, 184.0 + dx, 0.25, 3.35)
    _add_door(doors, 'gaosan', 184.0 + dx, 0.25, 120.06 + dz, 'chain_shutter', 'west', 'curfew_23')

    for fl in range(3):
        y0 = 0.25 + fl * FLOOR_H
        y1 = y0 + FLOOR_H
        y_ceil = y1 - 0.22

        if fl == 0:
            A.box(acc, 134.0 + dx, 0.24, 116.0 + dz, 159.0 + dx, 0.26, 125.8 + dz, flr, skip=('-y',))
            A.box(acc, 154.2 + dx, 0.24, 111.6 + dz, 184.0 + dx, 0.26, 121.4 + dz, flr, skip=('-y',))
        else:
            A.slab_with_ceiling(acc, col, 134.0 + dx, 116.0 + dz, 154.2 + dx, 125.92 + dz, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, 154.2 + dx, 118.8 + dz, 159.0 + dx, 125.92 + dz, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, 159.0 + dx, 111.6 + dz, 184.08 + dx, 121.52 + dz, y0 - 0.22, y0)

        _build_gaosan_wing(acc, col, west_segs, 116.0 + dz, 123.2 + dz, 125.8 + dz, y0, y1, y_ceil, fl, rooms, doors)

        A.wall_z(acc, col, 116.0 + dz, 123.2 + dz, 154.2 + dx, y0, y1, 0.24, 'facade', dado=True)
        A.wall_z(acc, col, 111.6 + dz, 118.8 + dz, 159.0 + dx, y0, y1, 0.24, 'facade',
                 [(113.6 + dz, 116.8 + dz, y0 + 0.9, y0 + 2.5, 'window')])
        for cx in (154.35 + dx, 156.6 + dx, 158.85 + dx):
            A.square_col(acc, col, cx, 118.95 + dz, 0.18, y0, y1, 'facade')
            A.square_col(acc, col, cx, 125.62 + dz, 0.18, y0, y1, 'facade', with_lamp=True, lamp_dir_z=-1)
        A.box(acc, 154.2 + dx, y_ceil - 0.24, 118.8 + dz, 159.0 + dx, y1, 119.15 + dz, facade)
        A.box(acc, 154.2 + dx, y_ceil - 0.24, 125.44 + dz, 159.0 + dx, y1, 125.85 + dz, facade)
        A.box(acc, 158.65 + dx, y_ceil - 0.24, 121.4 + dz, 159.0 + dx, y1, 125.85 + dz, facade)
        A.railing_x(acc, col, 154.4 + dx, 158.8 + dx, 118.95 + dz, y0)
        A.railing_z(acc, col, 121.4 + dz, 125.65 + dz, 158.85 + dx, y0)
        if fl == 0:
            A.railing_x(acc, col, 154.4 + dx, 156.42 + dx, 125.65 + dz, y0)
            A.box(acc, 156.5 + dx, 0.0, 125.8 + dz, 158.9 + dx, 0.25, 126.55 + dz, concrete)
        else:
            A.railing_x(acc, col, 154.4 + dx, 158.8 + dx, 125.65 + dz, y0)

        _build_gaosan_wing(acc, col, east_segs, 111.6 + dz, 118.8 + dz, 121.4 + dz, y0, y1, y_ceil, fl, rooms, doors)
        A.wall_z(acc, col, 111.6 + dz, 118.8 + dz, 184.0 + dx, y0, y1, 0.24, 'facade', dado=True)

    yr = 0.25 + 3 * FLOOR_H
    A.slab_with_ceiling(acc, col, 133.88 + dx, 115.88 + dz, 154.32 + dx, 125.92 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    A.slab_with_ceiling(acc, col, 154.20 + dx, 118.80 + dz, 159.00 + dx, 125.92 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    A.slab_with_ceiling(acc, col, 158.88 + dx, 111.48 + dz, 184.12 + dx, 121.52 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    for bx0, bz0, bx1, bz1 in (
        (133.85, 115.85, 154.35, 116.15), (138.2, 125.65, 159.0, 125.95),
        (158.85, 111.45, 184.15, 111.75), (163.2, 121.25, 184.15, 121.55),
        (133.85, 115.85, 134.15, 125.85), (183.85, 111.45, 184.15, 117.55),
    ):
        A.box(acc, bx0 + dx, yr, bz0 + dz, bx1 + dx, yr + 0.72, bz1 + dz, facade)

    acc.build('gaosan', coll)
    col.build('gaosan-colonly', coll)


def _build_gaosan_wing(acc, col, segs, zn, zc, zs, y0, y1, y_ceil, fl, rooms, doors):
    facade, concrete = L.mat('facade'), L.mat('concrete')
    for idx, (x0, x1, kind) in enumerate(segs):
        n_bay = max(1, int(round((x1 - x0) / 3.3)))
        for b in range(n_bay):
            bx0 = x0 + (x1 - x0) * b / n_bay
            bx1 = x0 + (x1 - x0) * (b + 1) / n_bay
            A.square_col(acc, col, bx0 + 0.16, zs - 0.18, 0.18, y0, y1, 'facade', with_lamp=(b % 2 == 0), lamp_dir_z=-1)
            if idx == len(segs) - 1 and b == n_bay - 1:
                A.square_col(acc, col, bx1 - 0.16, zs - 0.18, 0.18, y0, y1, 'facade')
            if kind not in ('lounge_west', 'stair_mid'):
                A.railing_x(acc, col, bx0 + 0.34, bx1 - 0.18, zs - 0.16, y0)
        A.box(acc, x0, y_ceil - 0.24, zs - 0.36, x1, y1, zs + 0.04, facade)
        A.box(acc, x0, y0 + 0.82, zn - 0.26, x1, y0 + 0.92, zn, concrete)
        A.box(acc, x0, y_ceil - 0.18, zn - 0.26, x1, y1, zn, concrete)

        if kind == 'lounge_west':
            A.wall_x(acc, col, x0, x1, zn, y0, y1, 0.24, 'facade', [(x0 + 0.8, x1 - 0.8, y0 + 0.9, y0 + 2.55, 'window')], dado=True)
            A.wall_z(acc, col, zn, zc, x0, y0, y1, 0.24, 'facade', [(zn + 1.0, zc - 1.0, y0 + 2.25, y0 + 2.75, 'window')], dado=True)
            if fl == 0:
                A.box(acc, x0 - 0.12, y_ceil - 0.24, zc, x0 + 0.12, y1, zs, facade)
                _add_door(doors, 'gaosan', x0, y0, (zc + zs) / 2, 'building_entrance', 'west')
            else:
                A.wall_z(acc, col, zc, zs, x0, y0, y1, 0.24, 'facade', [(zc + 0.4, zs - 0.4, y0 + 0.9, y0 + 2.55, 'window')], dado=True)
            A.wall_x(acc, col, x0, x1, zc, y0, y_ceil, 0.20, 'plaster', [(x0 + 0.9, x1 - 0.9, y0, y0 + 2.5, 'door')], dado=True)
            _add_room(rooms, 'gaosan', 'reading_lounge', fl + 1, x0 + 0.24, zn + 0.24, x1 - 0.22, zc - 0.22, y0)

        elif kind == 'stair_mid':
            A.wall_z(acc, col, zn, zc, x0, y0, y_ceil, 0.22, 'plaster', dado=True)
            A.wall_x(acc, col, x0, x1, zn, y0, y1, 0.24, 'facade', [(x0 + 0.8, x1 - 0.8, y0 + 0.9, y0 + 2.55, 'window')], dado=True)
            A.wall_x(acc, col, x0, x1, zc, y0, y_ceil, 0.22, 'plaster', [
                (x0 + 0.7, x0 + 1.7, y0, y0 + 2.2, 'door_leaf_open'),
                (x0 + 2.1, x1 - 0.7, y0 + 1.05, y0 + 2.45, 'window'),
            ], dado=True)

        elif kind == 'office':
            A.wall_z(acc, col, zn, zc, x0, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.wall_x(acc, col, x0, x1, zn, y0, y1, 0.24, 'facade', [
                (x0 + 0.85, x1 - 0.85, y0 + 0.9, y0 + 2.55, 'window'),
            ], dado=True)
            A.wall_x(acc, col, x0, x1, zc, y0, y_ceil, 0.22, 'plaster', [
                (x0 + 0.75, x0 + 1.75, y0, y0 + 2.2, 'door_leaf_open'),
                (x0 + 2.25, x1 - 0.85, y0 + 1.05, y0 + 2.45, 'window'),
            ], dado=True)
            _add_door(doors, 'gaosan', x0 + 1.25, y0, zc, 'office', 'south')
            _add_room(rooms, 'gaosan', 'office', fl + 1, x0 + 0.22, zn + 0.22, x1 - 0.22, zc - 0.22, y0)

        elif kind == 'classroom':
            A.wall_z(acc, col, zn, zc, x0, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.wall_x(acc, col, x0, x1, zn, y0, y1, 0.24, 'facade', [
                (x0 + 0.9, x0 + 4.5, y0 + 0.9, y0 + 2.55, 'window'),
                (x1 - 4.5, x1 - 0.9, y0 + 0.9, y0 + 2.55, 'window'),
            ], dado=True)
            A.wall_x(acc, col, x0, x1, zc, y0, y_ceil, 0.22, 'plaster', [
                (x0 + 0.75, x0 + 1.75, y0, y0 + 2.2, 'door_leaf_open'),
                (x0 + 2.35, x1 - 2.35, y0 + 1.05, y0 + 2.45, 'window'),
                (x1 - 1.75, x1 - 0.75, y0, y0 + 2.2, 'door_leaf_open'),
            ], dado=True)
            _add_door(doors, 'gaosan', x0 + 1.25, y0, zc, 'classroom', 'south')
            _add_door(doors, 'gaosan', x1 - 1.25, y0, zc, 'classroom', 'south')
            _add_room(rooms, 'gaosan', 'classroom', fl + 1, x0 + 0.22, zn + 0.22, x1 - 0.22, zc - 0.22, y0, rot_override=-90.0)

        elif kind == 'toilet':
            A.wall_z(acc, col, zn, zc, x0, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.wall_x(acc, col, x0, x1, zn, y0, y1, 0.24, 'facade', [
                (x0 + 0.8, x1 - 0.8, y0 + 1.65, y0 + 2.55, 'window'),
            ], dado=True)
            mx = (x0 + x1) / 2
            A.wall_x(acc, col, x0, x1, zc, y0, y_ceil, 0.22, 'plaster', [
                (mx - 1.4, mx - 0.5, y0, y0 + 2.2, 'door'),
                (mx + 0.5, mx + 1.4, y0, y0 + 2.2, 'door'),
            ], dado=True)
            A.wall_z(acc, col, zn + 0.2, zc - 0.2, mx, y0, y_ceil, 0.16, 'plaster', dado=True)
            for kx in (x0 + 1.2, x1 - 1.2):
                A.box(acc, kx - 0.45, y0, zn + 0.25, kx + 0.45, y0 + 0.82, zn + 0.85, L.mat('concrete'))
            _add_door(doors, 'gaosan', mx - 0.95, y0, zc, 'toilet', 'south')


# ================================================================ 4. cuihua（紧凑平移 dx, dz，内部结构 100% 完整）

def build_cuihua(cfg, coll, rooms, doors):
    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)
    cm = L.mat('collision')
    facade, flr, concrete = L.mat('facade'), L.mat('floor'), L.mat('concrete')
    glass_b, frame = L.mat('glass_blue'), L.mat('frame')

    org = cfg['origins']
    dx, dz = org['cuihua_dx'], org['cuihua_dz']   # -3.0, -49.0

    tcx, tcz, tr = 15.0 + dx, 79.2 + dz, 5.4
    x_junc = 18.8 + dx
    dz_int = math.sqrt(tr * tr - (x_junc - tcx) ** 2)
    z_int_n, z_int_s = tcz - dz_int, tcz + dz_int
    a_start = math.acos((x_junc - tcx) / tr)
    a_end = 2 * math.pi - a_start
    yr = 0.25 + 3 * FLOOR_H

    A.box(acc, 18.6 + dx, 0.0, 69.6 + dz, 41.8 + dx, 0.25, 84.7 + dz, concrete)
    A.box(col, 18.6 + dx, 0.0, 69.6 + dz, 41.8 + dx, 0.25, 84.7 + dz, cm)
    A.box(acc, 41.6 + dx, 0.0, 77.4 + dz, 44.2 + dx, 0.25, 84.7 + dz, concrete)
    A.box(col, 41.6 + dx, 0.0, 77.4 + dz, 44.2 + dx, 0.25, 84.7 + dz, cm)
    A.cyl(acc, tcx, tcz, tr + 0.18, 0.0, 0.25, concrete, seg=40)
    A.cyl(col, tcx, tcz, tr + 0.18, 0.0, 0.25, cm, seg=24)
    A.box(acc, 14.9 + dx, 0.0, 63.1 + dz, 24.6 + dx, 0.25, 69.9 + dz, concrete)
    A.box(col, 14.9 + dx, 0.0, 63.1 + dz, 24.6 + dx, 0.25, 69.9 + dz, cm)

    for st in range(2):
        A.box(acc, 22.3 + dx, 0.0, 62.3 + dz + st * 0.45, 24.6 + dx, (st + 1) * 0.125, 63.4 + dz, concrete)
    A.poly(col, [(22.3 + dx, 0.0, 62.3 + dz), (24.6 + dx, 0.0, 62.3 + dz),
                 (24.6 + dx, 0.25, 63.4 + dz), (22.3 + dx, 0.25, 63.4 + dz)], cm)
    A.box(acc, 18.8 + dx, 0.0, 84.4 + dz, 24.4 + dx, 0.14, 85.3 + dz, concrete)
    A.box(acc, 41.2 + dx, 0.0, 84.4 + dz, 44.4 + dx, 0.14, 86.0 + dz, concrete)
    A.box(acc, 41.0 + dx, 3.35, 84.4 + dz, 44.5 + dx, 3.65, 86.2 + dz, concrete)
    A.square_col(acc, col, 41.4 + dx, 85.8 + dz, 0.18, 0.14, 3.35, 'facade')
    A.square_col(acc, col, 44.1 + dx, 85.8 + dz, 0.18, 0.14, 3.35, 'facade')

    A.build_stair_flights_x(acc, col, 70.0 + dz, 73.6 + dz, 18.8 + dx, 14.05 + dx, 0.25, 3, FLOOR_H, first_side='south', sub_half=True)
    A.box(acc, 17.60 + dx, -1.75, 69.8 + dz, 18.85 + dx, 0.05, 73.8 + dz, concrete)
    A.box(col, 17.60 + dx, -1.75, 69.8 + dz, 18.85 + dx, 0.05, 73.8 + dz, cm)
    A.wall_x(acc, col, 14.0 + dx, 18.8 + dx, 69.8 + dz, -1.70, yr, 0.24, 'facade', [
        (15.4 + dx, 18.0 + dx, 7.85, 9.55, 'window'),
    ], dado=True)
    A.wall_x(acc, col, 14.0 + dx, 18.8 + dx, 73.8 + dz, -1.70, yr, 0.24, 'facade', dado=True)

    y_tl_top = 5.35 + FLOOR_H
    A.box(acc, 11.0 + dx, -1.75, 69.6 + dz, 14.1 + dx, -1.45, 74.0 + dz, concrete)
    A.box(col, 11.0 + dx, -1.75, 69.6 + dz, 14.1 + dx, -1.45, 74.0 + dz, cm)
    for t_idx, ty0 in enumerate((-1.45, 1.95, 5.35)):
        ty1 = ty0 + FLOOR_H
        ty_c = ty1 - 0.22
        if t_idx > 0:
            A.slab_with_ceiling(acc, col, 11.2 + dx, 69.8 + dz, 14.0 + dx, 73.8 + dz, ty0 - 0.22, ty0)
        else:
            A.box(acc, 11.2 + dx, ty0 - 0.02, 69.8 + dz, 14.0 + dx, ty0, 73.8 + dz, flr, skip=('-y',))
        win_y0 = max(0.28, ty0 + 1.65)
        win_y1 = max(0.95, ty0 + 2.55)
        A.wall_x(acc, col, 11.2 + dx, 14.0 + dx, 69.8 + dz, ty0, ty1, 0.24, 'facade', dado=True)
        A.wall_x(acc, col, 11.2 + dx, 14.0 + dx, 73.8 + dz, ty0, ty1, 0.24, 'facade', dado=True)
        A.wall_z(acc, col, 69.8 + dz, 73.8 + dz, 11.2 + dx, ty0, ty1, 0.24, 'facade', [
            (70.6 + dz, 73.0 + dz, win_y0, win_y1, 'window'),
        ], dado=True)
        door_z0 = (70.4 if t_idx == 0 else 71.3) + dz
        A.wall_z(acc, col, 69.8 + dz, 73.8 + dz, 14.0 + dx, ty0, ty_c, 0.20, 'plaster', [
            (door_z0, door_z0 + 1.0, ty0, ty0 + 2.15, 'door'),
        ], dado=True)
        A.box(acc, 11.4 + dx, ty0, 70.0 + dz, 12.0 + dx, ty0 + 0.82, 71.2 + dz, concrete)
        A.box(acc, 11.4 + dx, ty0, 72.3 + dz, 12.8 + dx, ty0 + 1.95, 72.42 + dz, L.mat('plaster'))

    A.slab_with_ceiling(acc, col, 11.08 + dx, 69.68 + dz, 14.12 + dx, 73.92 + dz, y_tl_top - 0.22, y_tl_top, 'roof', 'concrete', add_col=True)
    for bx0, bz0, bx1, bz1 in ((11.05, 69.65, 14.05, 69.95), (11.05, 73.65, 14.05, 73.95), (11.05, 69.65, 11.35, 73.95)):
        A.box(acc, bx0 + dx, y_tl_top, bz0 + dz, bx1 + dx, y_tl_top + 0.50, bz1 + dz, facade)
    A.wall_z(acc, col, 69.8 + dz, 73.8 + dz, 14.0 + dx, y_tl_top - 0.22, yr, 0.24, 'facade', [
        (70.6 + dz, 73.0 + dz, 9.0, 9.95, 'window'),
    ])
    A.slab_with_ceiling(acc, col, 13.88 + dx, 69.68 + dz, 19.0 + dx, 73.92 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)

    A.glass_stair_box_east(acc, col, 44.0 + dx, 49.2 + dx, 79.4 + dz, 84.2 + dz, 0.25, 3, FLOOR_H)
    A.build_stair_flights_x(acc, col, 79.6 + dz, 84.0 + dz, 44.0 + dx, 48.9 + dx, 0.25, 3, FLOOR_H, first_side='south')

    A.add_chain_shutter_z(acc, col, 70.06 + dz, 73.62 + dz, x_junc, 0.25, 3.35)
    _add_door(doors, 'cuihua', x_junc, 0.25, 71.84 + dz, 'chain_shutter', 'east', 'curfew_23')
    A.add_chain_shutter_z(acc, col, 79.58 + dz, 84.02 + dz, 44.0 + dx, 0.25, 3.35)
    _add_door(doors, 'cuihua', 44.0 + dx, 0.25, 81.80 + dz, 'chain_shutter', 'west', 'curfew_23')

    for fl in range(2):
        ny0 = 0.25 + fl * FLOOR_H
        ny1 = ny0 + FLOOR_H
        ny_c = ny1 - 0.22
        if fl == 0:
            A.box(acc, 15.2 + dx, 0.24, 63.4 + dz, 24.4 + dx, 0.26, 69.8 + dz, flr, skip=('-y',))
        else:
            A.slab_with_ceiling(acc, col, 15.2 + dx, 63.4 + dz, 24.4 + dx, 69.8 + dz, ny0 - 0.22, ny0)
            A.slab_with_ceiling(acc, col, 18.8 + dx, 69.8 + dz, 24.4 + dx, 74.0 + dz, ny0 - 0.22, ny0)

        if fl == 0:
            A.wall_x(acc, col, 15.2 + dx, 24.4 + dx, 63.4 + dz, ny0, ny1, 0.24, 'facade', [
                (16.2 + dx, 21.4 + dx, ny0 + 0.9, ny0 + 2.5, 'window'),
                (22.65 + dx, 24.15 + dx, ny0, ny0 + 2.55, 'open'),
            ], dado=True)
        else:
            A.wall_x(acc, col, 15.2 + dx, 24.4 + dx, 63.4 + dz, ny0, ny1, 0.24, 'facade', [
                (16.2 + dx, 21.4 + dx, ny0 + 0.9, ny0 + 2.5, 'window'),
                (22.8 + dx, 24.1 + dx, ny0 + 0.9, ny0 + 2.5, 'window'),
            ], dado=True)
        A.wall_z(acc, col, 63.4 + dz, 69.8 + dz, 15.2 + dx, ny0, ny1, 0.24, 'facade', [
            (64.6 + dz, 68.6 + dz, ny0 + 0.9, ny0 + 2.5, 'window'),
        ], dado=True)
        A.wall_z(acc, col, 63.4 + dz, 69.8 + dz, 22.5 + dx, ny0, ny_c, 0.20, 'plaster', [
            (64.8 + dz, 68.2 + dz, ny0 + 1.05, ny0 + 2.45, 'window'),
        ], dado=True)
        A.wall_z(acc, col, 63.4 + dz, 74.0 + dz, 24.4 + dx, ny0, ny1, 0.24, 'facade', [
            (64.8 + dz, 69.0 + dz, ny0 + 0.9, ny0 + 2.5, 'window'),
            (70.2 + dz, 73.0 + dz, ny0 + 0.9, ny0 + 2.5, 'window'),
        ], dado=True)
        A.wall_x(acc, col, 15.2 + dx, 22.5 + dx, 69.8 + dz, ny0, ny_c, 0.22, 'plaster', [
            (21.1 + dx, 22.1 + dx, ny0, ny0 + 2.2, 'door_leaf_open'),
        ], dado=True)
        _add_door(doors, 'cuihua', 21.6 + dx, ny0, 69.8 + dz, 'classroom', 'south')
        _add_room(rooms, 'cuihua', 'classroom', fl + 1, 15.45 + dx, 63.65 + dz, 20.95 + dx, 69.55 + dz, ny0, rot_override=180.0)

    ny_r = 0.25 + 2 * FLOOR_H
    A.slab_with_ceiling(acc, col, 15.08 + dx, 63.28 + dz, 24.52 + dx, 69.92 + dz, ny_r - 0.22, ny_r, 'roof', 'concrete', add_col=True)
    for bx0, bz0, bx1, bz1 in ((15.0, 63.2, 24.6, 63.55), (15.0, 63.2, 15.35, 69.8), (24.25, 63.2, 24.6, 69.8)):
        A.box(acc, bx0 + dx, ny_r, bz0 + dz, bx1 + dx, ny_r + 0.62, bz1 + dz, facade)

    segs = [
        (24.4 + dx, 34.4 + dx, 'classroom'),
        (34.4 + dx, 41.6 + dx, 'office'),
    ]
    for fl in range(3):
        y0 = 0.25 + fl * FLOOR_H
        y1 = y0 + FLOOR_H
        y_ceil = y1 - 0.22

        if fl == 0:
            A.clipped_cyl_slab(acc, None, tcx, tcz, tr - 0.04, x_junc, 0.23, 0.26, 'floor', seg=48)
            A.box(acc, x_junc, 0.24, 69.8 + dz, 24.4 + dx, 0.26, 84.4 + dz, flr, skip=('-y',))
            A.box(acc, 24.4 + dx, 0.24, 74.0 + dz, 41.6 + dx, 0.26, 84.4 + dz, flr, skip=('-y',))
            A.box(acc, 41.6 + dx, 0.24, 77.6 + dz, 44.0 + dx, 0.26, 84.4 + dz, flr, skip=('-y',))
        else:
            A.clipped_cyl_slab(acc, col, tcx, tcz, tr - 0.04, x_junc, y0 - 0.22, y0, 'floor', seg=48)
            if fl == 2:
                A.slab_with_ceiling(acc, col, x_junc, 69.8 + dz, 24.4 + dx, 74.0 + dz, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, x_junc, 74.0 + dz, 24.4 + dx, 84.48 + dz, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, 24.4 + dx, 74.0 + dz, 41.6 + dx, 84.48 + dz, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, 41.6 + dx, 77.6 + dz, 44.08 + dx, 84.48 + dz, y0 - 0.22, y0)

        A.arc_wall(acc, None, tcx, tcz, tr - 0.16, tr + 0.05, y0 - (0.22 if fl > 0 else 0.0), y0 + 0.22,
                   a_start, a_end, facade, seg=36, add_col=False, cap_ends=False)
        A.arc_wall(acc, col, tcx, tcz, tr - 0.06, tr, y0 + 0.22, y1,
                   a_start, a_end, glass_b, seg=36, add_col=True, cap_ends=False)
        n_mul = 16
        for k in range(1, n_mul):
            ang = a_start + (a_end - a_start) * k / n_mul
            A.obox(acc, tcx + tr * math.cos(ang), tcz + tr * math.sin(ang), 0.075, 0.075, y0 + 0.22, y1, ang, frame)

        A.square_col(acc, col, x_junc, 69.92 + dz, 0.16, y0, y1, 'facade')
        A.square_col(acc, col, x_junc, 73.76 + dz, 0.16, y0, y1, 'facade')
        A.square_col(acc, col, x_junc, z_int_n, 0.20, y0, y1, 'facade')
        A.square_col(acc, col, x_junc, z_int_s, 0.20, y0, y1, 'facade')
        A.wall_z(acc, col, 73.8 + dz, z_int_n, x_junc, y0, y1, 0.24, 'facade', dado=True)
        A.wall_z(acc, col, z_int_s, 84.4 + dz, x_junc, y0, y1, 0.24, 'facade', dado=True)

        if fl < 2:
            dx_w = math.sqrt(tr * tr - ((77.0 + dz) - tcz) ** 2) - 0.08
            A.wall_x(acc, col, tcx - dx_w, x_junc, 77.0 + dz, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.wall_z(acc, col, z_int_n + 0.18, z_int_s - 0.18, x_junc, y0, y_ceil, 0.22, 'plaster', [
                (79.6 + dz, 80.7 + dz, y0, y0 + 2.25, 'door'),
            ], dado=True)
            if fl == 0:
                _add_door(doors, 'cuihua', x_junc, y0, 80.15 + dz, 'astronomy', 'east', 'key_astronomy')
                _add_room(rooms, 'cuihua', 'astronomy', 1, 11.2 + dx, 77.4 + dz, 18.4 + dx, 83.2 + dz, y0)
            else:
                _add_door(doors, 'cuihua', x_junc, y0, 80.15 + dz, 'round_hall', 'east')
        else:
            for zp in (75.3 + dz, 78.9 + dz):
                dx_w = math.sqrt(tr * tr - (zp - tcz) ** 2) - 0.08
                A.wall_x(acc, col, tcx - dx_w, x_junc, zp, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.arc_wall(acc, None, tcx, tcz, tr - 0.14, tr + 0.04, y0 + 0.90, y0 + 0.98,
                       math.radians(156), math.radians(204), frame, seg=10, add_col=False, cap_ends=False)
            A.wall_z(acc, col, z_int_n + 0.18, z_int_s - 0.18, x_junc, y0, y_ceil, 0.22, 'plaster', [
                (76.55 + dz, 77.65 + dz, y0, y0 + 2.35, 'small_lab_door'),
                (80.0 + dz, 81.05 + dz, y0, y0 + 2.2, 'closed_door'),
            ], dado=True)
            _add_door(doors, 'cuihua', x_junc, y0, 77.1 + dz, 'small_lab', 'east', 'key_small_lab')
            _add_room(rooms, 'cuihua', 'small_lab', 3, 11.4 + dx, 75.55 + dz, 18.45 + dx, 78.65 + dz, y0, rot_override=0.0)

        if fl == 2:
            A.wall_x(acc, col, x_junc, 24.4 + dx, 69.8 + dz, y0, y1, 0.24, 'facade', [
                (19.6 + dx, 23.6 + dx, y0 + 0.9, y0 + 2.5, 'window'),
            ], dado=True)
            A.wall_z(acc, col, 69.8 + dz, 74.0 + dz, 24.4 + dx, y0, y1, 0.24, 'facade', [
                (70.6 + dz, 73.2 + dz, y0 + 0.9, y0 + 2.5, 'window'),
            ], dado=True)

        A.square_col(acc, col, 21.6 + dx, 84.22 + dz, 0.18, y0, y1, 'facade', with_lamp=True, lamp_dir_z=-1)
        A.box(acc, x_junc, y_ceil - 0.24, 84.06 + dz, 24.4 + dx, y1, 84.44 + dz, facade)
        if fl > 0:
            A.railing_x(acc, col, x_junc + 0.2, 21.4 + dx, 84.22 + dz, y0)
            A.railing_x(acc, col, 21.8 + dx, 24.2 + dx, 84.22 + dz, y0)

        for x0, x1, kind in segs:
            if fl == 2 and kind == 'office':
                A.wall_z(acc, col, 74.0 + dz, 81.6 + dz, x0, y0, y_ceil, 0.20, 'plaster', [
                    (80.15 + dz, 81.15 + dz, y0, y0 + 2.2, 'door_leaf_open'),
                ], dado=True)
                _add_door(doors, 'cuihua', x0, y0, 80.65 + dz, 'key_office_inner', 'west')
            else:
                A.wall_z(acc, col, 74.0 + dz, 81.6 + dz, x0, y0, y_ceil, 0.20, 'plaster', dado=True)

            A.box(acc, x0, y0 + 0.82, 73.75 + dz, x1, y0 + 0.90, 74.0 + dz, concrete)
            A.box(acc, x0, y_ceil - 0.24, 84.06 + dz, x1, y1, 84.44 + dz, facade)

            if kind == 'classroom':
                for b in range(3):
                    bx0 = x0 + (x1 - x0) * b / 3
                    bx1 = x0 + (x1 - x0) * (b + 1) / 3
                    A.square_col(acc, col, bx0 + 0.16, 84.22 + dz, 0.18, y0, y1, 'facade', with_lamp=(b == 1), lamp_dir_z=-1)
                    A.railing_x(acc, col, bx0 + 0.34, bx1 - 0.16, 84.22 + dz, y0)
                A.wall_x(acc, col, x0, x1, 74.0 + dz, y0, y1, 0.24, 'facade', [
                    (x0 + 0.9, x0 + 4.5, y0 + 0.9, y0 + 2.55, 'window'),
                    (x1 - 4.5, x1 - 0.9, y0 + 0.9, y0 + 2.55, 'window'),
                ], dado=True)
                A.wall_x(acc, col, x0, x1, 81.6 + dz, y0, y_ceil, 0.22, 'plaster', [
                    (x0 + 0.75, x0 + 1.75, y0, y0 + 2.2, 'door_leaf_open'),
                    (x0 + 2.35, x1 - 2.35, y0 + 1.05, y0 + 2.45, 'window'),
                    (x1 - 1.75, x1 - 0.75, y0, y0 + 2.2, 'door_leaf_open'),
                ], dado=True)
                rtype = 'lab' if fl == 2 else 'classroom'
                _add_door(doors, 'cuihua', x0 + 1.25, y0, 81.6 + dz, rtype, 'south')
                _add_door(doors, 'cuihua', x1 - 1.25, y0, 81.6 + dz, rtype, 'south')
                _add_room(rooms, 'cuihua', rtype, fl + 1, x0 + 0.22, 74.22 + dz, x1 - 0.22, 81.38 + dz, y0, rot_override=-90.0)

            elif kind == 'office':
                for b in range(2):
                    bx0 = x0 + (x1 - x0) * b / 2
                    bx1 = x0 + (x1 - x0) * (b + 1) / 2
                    A.square_col(acc, col, bx0 + 0.16, 84.22 + dz, 0.18, y0, y1, 'facade', with_lamp=(b == 0), lamp_dir_z=-1)
                    A.railing_x(acc, col, bx0 + 0.34, bx1 - 0.16, 84.22 + dz, y0)
                A.wall_x(acc, col, x0, x1, 74.0 + dz, y0, y1, 0.24, 'facade', [
                    (x0 + 0.9, x1 - 0.9, y0 + 0.9, y0 + 2.55, 'window'),
                ], dado=True)
                if fl == 2:
                    A.wall_x(acc, col, x0, x1, 81.6 + dz, y0, y_ceil, 0.22, 'plaster', [
                        (x0 + 1.2, x1 - 1.2, y0 + 1.05, y0 + 2.45, 'window'),
                    ], dado=True)
                else:
                    A.wall_x(acc, col, x0, x1, 81.6 + dz, y0, y_ceil, 0.22, 'plaster', [
                        (x0 + 0.8, x0 + 1.8, y0, y0 + 2.2, 'door_leaf_open'),
                        (x0 + 2.3, x1 - 0.9, y0 + 1.05, y0 + 2.45, 'window'),
                    ], dado=True)
                    _add_door(doors, 'cuihua', x0 + 1.3, y0, 81.6 + dz, 'office', 'south')
                _add_room(rooms, 'cuihua', 'office', fl + 1, x0 + 0.22, 74.22 + dz, x1 - 0.22, 81.38 + dz, y0)

        A.wall_z(acc, col, 74.0 + dz, 77.6 + dz, 41.6 + dx, y0, y1, 0.24, 'facade', dado=True)
        A.wall_z(acc, col, 77.6 + dz, 81.6 + dz, 41.6 + dx, y0, y_ceil, 0.22, 'plaster', dado=True)
        A.wall_x(acc, col, 41.6 + dx, 44.0 + dx, 77.6 + dz, y0, y1, 0.24, 'facade', [
            (42.1 + dx, 43.5 + dx, y0 + 0.9, y0 + 2.5, 'window'),
        ], dado=True)
        A.wall_z(acc, col, 77.6 + dz, 79.5 + dz, 44.0 + dx, y0, y1, 0.24, 'facade', dado=True)
        A.square_col(acc, col, 41.76 + dx, 84.22 + dz, 0.18, y0, y1, 'facade')
        A.square_col(acc, col, 43.86 + dx, 84.22 + dz, 0.18, y0, y1, 'facade')
        A.box(acc, 41.6 + dx, y_ceil - 0.24, 84.06 + dz, 44.08 + dx, y1, 84.44 + dz, facade)
        if fl == 0:
            _add_door(doors, 'cuihua', 42.8 + dx, y0, 84.22 + dz, 'building_entrance', 'south')
        else:
            A.railing_x(acc, col, 41.94 + dx, 43.68 + dx, 84.22 + dz, y0)

    A.clipped_cyl_slab(acc, col, tcx, tcz, tr - 0.04, x_junc, yr - 0.22, yr, 'roof', seg=48)
    A.slab_with_ceiling(acc, col, x_junc - 0.12, 69.68 + dz, 24.52 + dx, 74.0 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    A.slab_with_ceiling(acc, col, x_junc - 0.12, 73.88 + dz, 41.72 + dx, 84.52 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    A.slab_with_ceiling(acc, col, 41.60 + dx, 77.48 + dz, 44.12 + dx, 84.52 + dz, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    for bx0, bz0, bx1, bz1 in (
        (20.4, 73.85, 41.75, 74.15), (41.45, 73.85, 41.75, 77.75), (41.45, 77.45, 44.15, 77.75),
        (20.4, 84.25, 44.15, 84.55),
    ):
        A.box(acc, bx0 + dx, yr, bz0 + dz, bx1 + dx, yr + 0.68, bz1 + dz, facade)
    A.cyl(acc, tcx, tcz, tr, yr - 0.22, yr + 0.18, facade, seg=40)
    A.arc_wall(acc, None, tcx, tcz, tr - 0.08, tr - 0.02, yr + 0.18, yr + 1.45, 0, 2 * math.pi, glass_b, seg=36, add_col=False, cap_ends=False)
    for k in range(16):
        ang = 2 * math.pi * k / 16
        A.obox(acc, tcx + tr * math.cos(ang), tcz + tr * math.sin(ang), 0.07, 0.07, yr + 0.18, yr + 1.45, ang, frame)
    A.cyl(acc, tcx, tcz, tr + 0.12, yr + 1.45, yr + 1.82, facade, seg=40)
    A.dome(acc, tcx, tcz, tr - 0.02, yr + 1.82, 3.8, facade, seg=40, rings=14)
    dcx, dcz, dr = 38.0 + dx, 78.0 + dz, 2.6
    A.cyl(acc, dcx, dcz, dr + 0.2, yr, yr + 0.35, concrete, seg=28)
    for k in range(8):
        ang = 2 * math.pi * k / 8
        A.cyl(acc, dcx + (dr - 0.25) * math.cos(ang), dcz + (dr - 0.25) * math.sin(ang), 0.14, yr + 0.35, yr + 1.35, facade, seg=10)
    A.cyl(acc, dcx, dcz, dr + 0.15, yr + 1.35, yr + 1.62, facade, seg=28)
    A.dome(acc, dcx, dcz, dr, yr + 1.62, 1.9, concrete, seg=28, rings=10)

    acc.build('cuihua', coll)
    col.build('cuihua-colonly', coll)


# ================================================================ 5. north（紧凑生活区：宿舍南北楼间距5.6m / 宿舍食堂间距5.3m / 小卖部紧凑贴靠）

def build_north(cfg, coll, rooms, doors):
    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)

    org = cfg['origins']
    dx_dorm = org['dorm_x']
    cb = org['canteen_box']
    _build_dorm(acc, col, dx_dorm, org['dorm_n_z'], rooms, doors, enterable=True)
    _build_dorm(acc, col, dx_dorm, org['dorm_s_z'], rooms, doors, enterable=False)
    _build_canteen(acc, col, cb[0], cb[2], cb[1], cb[3], rooms, doors)
    _build_shop(acc, col, cfg['shop'], coll, doors)

    acc.build('north', coll)
    col.build('north-colonly', coll)


def _build_dorm_foyer_l_stair(acc, col, xm0, xm1, zs_w, zs_e, y1f, y2f):
    m_step = L.mat('floor')
    m_side = L.mat('concrete')
    m_ceil = L.mat('ceiling_white')
    m_rail = L.mat('metal_dark')
    cm = L.mat('collision')

    y_mid = y1f + 1.15
    fx0, fx1 = xm1 - 1.34, xm1 - 0.14
    z_run1_s, z_run1_n = zs_e - 0.42, zs_w + 1.32
    sz0, sz1 = zs_w + 0.12, zs_w + 1.32
    x_run2_e, x_run2_w = fx0, xm0 + 1.28

    n1 = 6
    for i in range(n1):
        t0, t1 = i / n1, (i + 1) / n1
        za, zb = z_run1_s + (z_run1_n - z_run1_s) * t0, z_run1_s + (z_run1_n - z_run1_s) * t1
        yt = y1f + (y_mid - y1f) * t1
        A.box(acc, fx0, y1f, min(za, zb), fx1, yt, max(za, zb), m_step)
    A.poly(col, [(fx0, y1f, z_run1_s), (fx1, y1f, z_run1_s), (fx1, y_mid, z_run1_n), (fx0, y_mid, z_run1_n)], cm)
    A.poly(col, [(fx0, y_mid, z_run1_n), (fx1, y_mid, z_run1_n), (fx1, y1f, z_run1_s), (fx0, y1f, z_run1_s)], cm)
    rx1 = fx0 + 0.03
    A.poly(acc, [(rx1, y1f + 0.90, z_run1_s), (rx1, y_mid + 0.90, z_run1_n),
                 (rx1, y_mid + 0.96, z_run1_n), (rx1, y1f + 0.96, z_run1_s)], m_rail)
    A.poly(acc, [(rx1, y1f + 0.96, z_run1_s), (rx1, y_mid + 0.96, z_run1_n),
                 (rx1, y_mid + 0.90, z_run1_n), (rx1, y1f + 0.90, z_run1_s)], m_rail)
    for tk in (0.1, 0.5, 0.9):
        zk = z_run1_s + (z_run1_n - z_run1_s) * tk
        yk = y1f + (y_mid - y1f) * tk
        A.box(acc, rx1 - 0.02, yk, zk - 0.02, rx1 + 0.02, yk + 0.92, zk + 0.02, m_rail)

    A.box(acc, fx0, y1f, sz0, fx1, y_mid, sz1, m_step)
    A.box(col, fx0, y1f, sz0, fx1, y_mid, sz1, cm)

    n2 = 11
    for i in range(n2):
        t0, t1 = i / n2, (i + 1) / n2
        xa, xb = x_run2_e + (x_run2_w - x_run2_e) * t0, x_run2_e + (x_run2_w - x_run2_e) * t1
        yb0, yb1 = y_mid + (y2f - y_mid) * t0, y_mid + (y2f - y_mid) * t1
        A.box(acc, min(xa, xb), yb0, sz0, max(xa, xb), yb1, sz1, m_step)
    d_sof = 0.18
    p0, p1 = (x_run2_e, y_mid - d_sof, sz0), (x_run2_e, y_mid - d_sof, sz1)
    p2, p3 = (x_run2_w, y2f - d_sof, sz1), (x_run2_w, y2f - d_sof, sz0)
    A.poly(acc, [p0, p1, p2, p3], m_ceil)
    A.poly(acc, [p3, p2, p1, p0], m_ceil)
    for zz in (sz0, sz1):
        A.poly(acc, [(x_run2_e, y_mid, zz), (x_run2_w, y2f, zz), (x_run2_w, y2f - d_sof, zz), (x_run2_e, y_mid - d_sof, zz)], m_side)
        A.poly(acc, [(x_run2_e, y_mid - d_sof, zz), (x_run2_w, y2f - d_sof, zz), (x_run2_w, y2f, zz), (x_run2_e, y_mid, zz)], m_side)
    A.poly(col, [(x_run2_e, y_mid, sz0), (x_run2_e, y_mid, sz1), (x_run2_w, y2f, sz1), (x_run2_w, y2f, sz0)], cm)
    A.poly(col, [(x_run2_w, y2f, sz0), (x_run2_w, y2f, sz1), (x_run2_e, y_mid, sz1), (x_run2_e, y_mid, sz0)], cm)
    rz2 = sz1 - 0.03
    A.poly(acc, [(x_run2_e, y_mid + 0.90, rz2), (x_run2_w, y2f + 0.90, rz2),
                 (x_run2_w, y2f + 0.96, rz2), (x_run2_e, y_mid + 0.96, rz2)], m_rail)
    A.poly(acc, [(x_run2_e, y_mid + 0.96, rz2), (x_run2_w, y2f + 0.96, rz2),
                 (x_run2_w, y2f + 0.90, rz2), (x_run2_e, y_mid + 0.90, rz2)], m_rail)
    for tk in (0.15, 0.5, 0.85):
        xk = x_run2_e + (x_run2_w - x_run2_e) * tk
        yk = y_mid + (y2f - y_mid) * tk
        A.box(acc, xk - 0.02, yk, rz2 - 0.02, xk + 0.02, yk + 0.92, rz2 + 0.02, m_rail)

    A.slab_with_ceiling(acc, col, xm0 + 0.12, zs_w - 0.06, x_run2_w, sz1, y2f - 0.22, y2f, 'floor', 'concrete', add_col=True)
    A.railing_x(acc, col, xm0 + 0.16, x_run2_w, sz1 - 0.04, y2f, h=1.02, glass_panel=True)


def _build_dorm(acc, col, x_west, z_north, rooms, doors, enterable=True):
    """注意所有 X 坐标全部以 x_west 为基准（无任何硬编码旧坐标）！"""
    cm = L.mat('collision')
    facade, flr, concrete, roof_m = L.mat('facade'), L.mat('floor'), L.mat('concrete'), L.mat('roof')

    zn_w, zs_w = z_north, z_north + 11.2
    zn_e, zs_e = z_north + 3.6, z_north + 14.8
    x0, xm0, xm1, x1 = x_west, x_west + 11.0, x_west + 16.0, x_west + 29.2
    x_st_w = xm0 - 3.8  # 主楼梯西界 (x_west + 7.2)

    A.box(acc, x0 - 0.25, 0.0, zn_w - 0.25, xm0 + 0.25, 0.25, zs_w + 0.25, concrete)
    A.box(acc, xm0 - 0.1, 0.0, zn_e - 0.25, x1 + 0.25, 0.25, zs_e + 0.25, concrete)
    A.box(col, x0 - 0.25, 0.0, zn_w - 0.25, xm0 + 0.25, 0.25, zs_w + 0.25, cm)
    A.box(col, xm0 - 0.1, 0.0, zn_e - 0.25, x1 + 0.25, 0.25, zs_e + 0.25, cm)

    if not enterable:
        yr = 0.25 + 3 * FLOOR_H
        A.box(acc, x0, 0.25, zn_w, xm0 + 0.2, yr - 0.35, zs_w, facade)
        A.box(acc, xm0, 0.25, zn_e, xm1, yr + 0.2, zs_e, facade)
        A.box(acc, xm1 - 0.2, 0.25, zn_e, x1, yr, zs_e, facade)
        A.box(col, x0, 0.25, zn_w, xm0, yr + 0.6, zs_w, cm)
        A.box(col, xm0, 0.25, zn_e, x1, yr + 0.6, zs_e, cm)
        for fl in range(3):
            yf = 0.25 + fl * FLOOR_H
            for wx0, wx1 in ((x0 + 0.8, x0 + 4.4), (x0 + 5.4, xm0 - 0.8)):
                for zz in (zn_w, zs_w):
                    A._window_x(acc, None, wx0, wx1, yf + 0.9, yf + 2.55, zz, 0.24, 'glass_blue')
            for k in range(2):
                wx0 = xm1 + 0.6 + k * 4.2
                for zz in (zn_e, zs_e):
                    A._window_x(acc, None, wx0, wx0 + 3.0, yf + 0.9, yf + 2.55, zz, 0.24, 'glass_blue')
            A._window_z(acc, None, zs_w + 0.3, zs_e - 0.3, yf + 0.2, yf + 3.1, xm0, 0.24, 'glass_blue')
            A._window_x(acc, None, xm0 + 0.3, xm1 - 0.3, yf + 0.2, yf + 3.1, zs_e, 0.24, 'glass_blue')
        A.box(acc, x0 - 0.2, yr - 0.35, zn_w - 0.2, xm0 + 0.1, yr - 0.1, zs_w + 0.2, concrete)
        A.box(acc, xm0 - 0.2, yr, zn_e - 0.2, xm1 + 0.2, yr + 0.45, zs_e + 0.2, concrete)
        A.box(acc, xm1 - 0.1, yr, zn_e - 0.2, x1 + 0.2, yr + 0.25, zs_e + 0.2, concrete)
        A.box(acc, xm1, yr + 0.25, zn_e, x1, yr + 0.32, zs_e, roof_m)
        A.solar_panels(acc, xm1 + 0.6, x1 - 0.8, zn_e + 0.6, zs_e - 0.6, yr + 0.32)
        return

    zc_w0, zc_w1 = zn_w + 4.5, zs_w - 4.5
    zc_e0, zc_e1 = zn_e + 4.5, zs_e - 4.5

    A.build_stair_flights(acc, col, x_st_w + 0.18, xm0 - 0.18, zc_w1, zs_w - 0.24, 0.25, 3, FLOOR_H)
    _build_dorm_foyer_l_stair(acc, col, xm0, xm1, zs_w, zs_e, 0.25, 0.25 + FLOOR_H)
    A.build_stair_flights(acc, col, x1 - 4.8, x1 - 0.25, zc_e0, zn_e + 0.25, 0.25, 3, FLOOR_H)

    for fl in range(3):
        y0 = 0.25 + fl * FLOOR_H
        y1 = y0 + FLOOR_H
        y_ceil = y1 - 0.22

        if fl == 0:
            A.box(acc, x0, 0.24, zn_w, xm0, 0.26, zs_w, flr, skip=('-y',))
            A.box(acc, xm0, 0.24, zn_e, x1, 0.26, zs_e, flr, skip=('-y',))
        else:
            A.slab_with_ceiling(acc, col, x0, zn_w, xm0, zc_w1, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, x0, zc_w1, x_st_w, zs_w, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, xm0, zn_e, xm1, zs_w, y0 - 0.22, y0)
            if fl == 2:
                A.slab_with_ceiling(acc, col, xm0, zs_w, xm1, zs_e, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, xm1, zn_e, x1 - 4.8, zs_e, y0 - 0.22, y0)
            A.slab_with_ceiling(acc, col, x1 - 4.8, zc_e0, x1, zs_e, y0 - 0.22, y0)

        A.wall_z(acc, col, zn_w, zs_w, x0, y0, y1, 0.24, 'facade', [
            (zn_w + 4.6, zn_w + 6.6, y0 + 0.9, y0 + 2.5, 'window'),
        ], dado=True)
        A.wall_z(acc, col, zn_w, zn_e, xm0, y0, y1, 0.24, 'facade')
        A.wall_x(acc, col, xm0, xm1, zn_e, y0, y1, 0.24, 'facade', [
            (xm0 + 0.8, xm1 - 0.8, y0 + 0.9, y0 + 2.5, 'window'),
        ], dado=True)
        A.wall_z(acc, col, zn_e, zs_e, x1, y0, y1, 0.24, 'facade', [
            (zn_e + 1.2, zs_e - 1.2, y0 + 0.85, y0 + 2.55, 'glass_wall'),
        ], dado=True)

        A.wall_z(acc, col, zc_w1, zs_w, x_st_w, y0, y_ceil, 0.20, 'plaster', dado=True)
        A.wall_z(acc, col, zc_w1, zs_w, xm0, y0, y_ceil, 0.20, 'plaster', dado=True)
        A.wall_x(acc, col, x_st_w, xm0, zs_w, y0, y1, 0.24, 'facade', [
            (x_st_w + 0.6, xm0 - 0.6, y0 + 0.9, y0 + 2.5, 'glass_wall'),
        ], dado=True)

        if fl == 0:
            A.wall_z(acc, col, zs_w, zs_e, xm0, y0, y1, 0.24, 'facade', [
                (zs_w + 1.38, zs_e - 0.38, y0, y0 + 2.65, 'open'),
            ])
            A.add_chain_shutter_z(acc, col, zs_w + 1.38, zs_e - 0.38, xm0, y0, y0 + 2.65)
            _add_door(doors, 'north', xm0, y0, (zs_w + 1.38 + zs_e - 0.38) / 2, 'chain_shutter', 'west', 'curfew_22')
            A.box(acc, xm0 - 1.5, y0 + 2.68, zs_w + 1.1, xm0, y0 + 2.96, zs_e - 0.2, concrete)
            A.box(acc, xm0 - 0.8, 0.0, zs_w + 1.1, xm0, 0.25, zs_e - 0.2, concrete)
            A.wall_x(acc, col, xm0, xm1, zs_e, y0, y1, 0.24, 'facade', [
                (xm0 + 0.45, xm1 - 0.45, y0 + 0.9, y0 + 2.65, 'glass_wall'),
            ], dado=True)
            A.wall_x(acc, col, xm0, xm1, zs_w, y0, y1, 0.22, 'plaster', dado=True)
            A.wall_z(acc, col, zs_w, zs_e, xm1, y0, y1, 0.22, 'plaster', dado=True)
            A.wall_z(acc, col, zc_e1, zs_w, xm1, y0, y_ceil, 0.22, 'plaster', dado=True)
        elif fl == 1:
            A.wall_z(acc, col, zs_w, zs_e, xm0, y0, y1, 0.24, 'facade', [
                (zs_w + 0.35, zs_e - 0.35, y0 + 0.25, y0 + 2.85, 'glass_wall'),
            ])
            A.wall_x(acc, col, xm0, xm1, zs_e, y0, y1, 0.24, 'facade', [
                (xm0 + 0.45, xm1 - 0.45, y0 + 0.25, y0 + 2.85, 'glass_wall'),
            ])
            A.wall_z(acc, col, zs_w, zs_e, xm1, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.railing_x(acc, col, xm0 + 1.28, xm1 - 0.12, zs_w - 0.04, y0)
        else:
            A.wall_z(acc, col, zs_w, zs_e, xm0, y0, y1, 0.24, 'facade', [
                (zs_w + 0.35, zs_e - 0.35, y0 + 0.25, y0 + 2.85, 'glass_wall'),
            ])
            A.wall_x(acc, col, xm0, xm1, zs_e, y0, y1, 0.24, 'facade', [
                (xm0 + 0.45, xm1 - 0.45, y0 + 0.25, y0 + 2.85, 'glass_wall'),
            ])
            A.wall_x(acc, col, xm0, xm1, zs_w, y0, y_ceil, 0.20, 'plaster', [
                (xm0 + 2.6, xm0 + 3.6, y0, y0 + 2.2, 'door_leaf_open'),
                (xm0 + 0.5, xm0 + 2.2, y0 + 1.05, y0 + 2.45, 'window'),
            ], dado=True)
            _add_door(doors, 'north', xm0 + 3.1, y0, zs_w, 'study_room', 'north')
            _add_room(rooms, 'north', 'study_room', 3, xm0 + 0.24, zs_w + 0.22, xm1 - 0.24, zs_e - 0.24, y0)
        A.square_col(acc, col, xm0 + 0.14, zs_e - 0.14, 0.20, y0, y1, 'facade')

        A.wall_x(acc, col, x1 - 4.8, x1, zn_e, y0, y1, 0.24, 'facade', [
            (x1 - 4.0, x1 - 0.8, y0 + 0.85, y0 + 2.55, 'glass_wall'),
        ])
        A.wall_x(acc, col, x1 - 4.8, x1, zs_e, y0, y1, 0.24, 'facade', [
            (x1 - 4.0, x1 - 0.8, y0 + 0.9, y0 + 2.5, 'window'),
        ], dado=True)
        A.wall_z(acc, col, zn_e, zc_e0, x1 - 4.8, y0, y_ceil, 0.20, 'plaster', dado=True)

        if fl == 0:
            A.wall_x(acc, col, x0, xm0, zn_w, y0, y1, 0.24, 'facade', [(x0 + 1.5, xm0 - 1.5, y0 + 1.1, y0 + 2.45, 'glass_wall')], dado=True)
            A.wall_x(acc, col, x0, x_st_w, zs_w, y0, y1, 0.24, 'facade', [(x0 + 1.0, x_st_w - 1.0, y0 + 0.9, y0 + 2.5, 'glass_wall')], dado=True)
            A.wall_x(acc, col, x0, xm0, zc_w0, y0, y_ceil, 0.20, 'plaster', [(xm0 - 2.2, xm0 - 1.1, y0, y0 + 2.2, 'door_leaf_open')], dado=True)
            A.wall_x(acc, col, x0, x_st_w, zc_w1, y0, y_ceil, 0.20, 'plaster', [
                (x_st_w - 1.8, x_st_w - 0.8, y0, y0 + 2.2, 'door_leaf_open'),
                (x0 + 1.5, x_st_w - 2.4, y0 + 1.05, y0 + 2.35, 'window'),
            ], dado=True)
            _add_door(doors, 'north', xm0 - 1.65, y0, zc_w0, 'monitor_room', 'south')
            _add_door(doors, 'north', x_st_w - 1.3, y0, zc_w1, 'duty_room', 'north')
            _add_room(rooms, 'north', 'office', 1, x0 + 0.3, zn_w + 0.3, xm0 - 0.3, zc_w0 - 0.25, y0)
            _add_room(rooms, 'north', 'office', 1, x0 + 0.3, zc_w1 + 0.25, x_st_w - 0.2, zs_w - 0.3, y0)

            ex_end = x1 - 4.8
            A.wall_x(acc, col, xm1, ex_end, zn_e, y0, y1, 0.24, 'facade', [
                (xm1 + 1.2, ex_end - 1.2, y0 + 0.9, y0 + 2.5, 'glass_wall'),
            ], dado=True)
            A.wall_x(acc, col, xm1, ex_end, zc_e0, y0, y_ceil, 0.20, 'plaster', [
                (xm1 + 1.0, xm1 + 2.0, y0, y0 + 2.2, 'door_leaf_open'),
            ], dado=True)
            A.wall_z(acc, col, zn_e, zc_e0, xm1, y0, y_ceil, 0.20, 'plaster', dado=True)
            A.wall_x(acc, col, xm1, ex_end, zs_e, y0, y1, 0.24, 'facade', [
                (xm1 + 1.0, ex_end - 1.0, y0 + 0.85, y0 + 2.55, 'glass_wall'),
            ], dado=True)
        else:
            wx_rm = x0 + 3.2
            A.wall_z(acc, col, zn_w, zc_w0, wx_rm, y0, y_ceil, 0.18, 'plaster', dado=True)
            A.wall_z(acc, col, zc_w1, zs_w, wx_rm, y0, y_ceil, 0.18, 'plaster', dado=True)
            A.wall_z(acc, col, zn_w, zc_w0, x_st_w, y0, y_ceil, 0.18, 'plaster', dado=True)
            A.wall_x(acc, col, x0, xm0, zn_w, y0, y1, 0.24, 'facade', [
                (x0 + 0.7, wx_rm - 0.6, y0 + 1.2, y0 + 2.5, 'glass_wall'),
                (wx_rm + 0.7, x_st_w - 0.7, y0 + 0.9, y0 + 2.55, 'glass_wall'),
                (x_st_w + 0.7, xm0 - 0.7, y0 + 0.9, y0 + 2.55, 'glass_wall'),
            ], dado=True)
            A.wall_x(acc, col, x0, x_st_w, zs_w, y0, y1, 0.24, 'facade', [
                (x0 + 0.7, wx_rm - 0.6, y0 + 1.2, y0 + 2.5, 'glass_wall'),
                (wx_rm + 0.7, x_st_w - 0.7, y0 + 0.9, y0 + 2.55, 'glass_wall'),
            ], dado=True)
            w_mid = (wx_rm + x_st_w) / 2
            A.wall_x(acc, col, x0, xm0, zc_w0, y0, y_ceil, 0.20, 'plaster', [
                (x0 + 1.1, x0 + 2.0, y0, y0 + 2.2, 'door'),
                (w_mid - 0.48, w_mid + 0.48, y0, y0 + 2.2, 'door_leaf_open'),
                (x_st_w + 1.4, x_st_w + 2.35, y0, y0 + 2.2, 'door'),
            ], dado=True)
            A.wall_x(acc, col, x0, x_st_w, zc_w1, y0, y_ceil, 0.20, 'plaster', [
                (x0 + 1.1, x0 + 2.0, y0, y0 + 2.2, 'door'),
                (w_mid - 0.48, w_mid + 0.48, y0, y0 + 2.2, 'door_leaf_open'),
            ], dado=True)
            _add_door(doors, 'north', w_mid, y0, zc_w0, 'dorm', 'south')
            _add_door(doors, 'north', w_mid, y0, zc_w1, 'dorm', 'north')
            _add_room(rooms, 'north', 'dorm', fl + 1, wx_rm + 0.20, zn_w + 0.24, x_st_w - 0.20, zc_w0 - 0.20, y0, rot_override=0.0)
            _add_room(rooms, 'north', 'dorm', fl + 1, wx_rm + 0.20, zc_w1 + 0.20, x_st_w - 0.20, zs_w - 0.24, y0, rot_override=180.0)

            ex_end = x1 - 4.8
            w_rm = (ex_end - xm1) / 2
            for k in range(2):
                rx0, rx1 = xm1 + k * w_rm, xm1 + (k + 1) * w_rm
                rm_mid = (rx0 + rx1) / 2
                A.wall_z(acc, col, zn_e, zc_e0, rx0, y0, y_ceil, 0.18, 'plaster', dado=True)
                if k > 0:
                    A.wall_z(acc, col, zc_e1, zs_e, rx0, y0, y_ceil, 0.18, 'plaster', dado=True)
                A.wall_x(acc, col, rx0, rx1, zn_e, y0, y1, 0.24, 'facade', [
                    (rx0 + 0.75, rx1 - 0.75, y0 + 0.9, y0 + 2.55, 'glass_wall'),
                ], dado=True)
                A.wall_x(acc, col, rx0, rx1, zs_e, y0, y1, 0.24, 'facade', [
                    (rx0 + 0.75, rx1 - 0.75, y0 + 0.9, y0 + 2.55, 'glass_wall'),
                ], dado=True)
                A.wall_x(acc, col, rx0, rx1, zc_e0, y0, y_ceil, 0.20, 'plaster', [
                    (rm_mid - 0.48, rm_mid + 0.48, y0, y0 + 2.2, 'door_leaf_open'),
                ], dado=True)
                A.wall_x(acc, col, rx0, rx1, zc_e1, y0, y_ceil, 0.20, 'plaster', [
                    (rm_mid - 0.48, rm_mid + 0.48, y0, y0 + 2.2, 'door_leaf_open'),
                ], dado=True)
                _add_door(doors, 'north', rm_mid, y0, zc_e0, 'dorm', 'south')
                _add_door(doors, 'north', rm_mid, y0, zc_e1, 'dorm', 'north')
                _add_room(rooms, 'north', 'dorm', fl + 1, rx0 + 0.20, zn_e + 0.24, rx1 - 0.20, zc_e0 - 0.20, y0, rot_override=0.0)
                _add_room(rooms, 'north', 'dorm', fl + 1, rx0 + 0.20, zc_e1 + 0.20, rx1 - 0.20, zs_e - 0.24, y0, rot_override=180.0)
            A.wall_z(acc, col, zc_e1, zs_e, ex_end, y0, y_ceil, 0.20, 'plaster', dado=True)
            if fl == 2:
                A.wall_z(acc, col, zc_e1, zs_e, xm1, y0, y_ceil, 0.18, 'plaster', dado=True)

    yr = 0.25 + 3 * FLOOR_H
    A.slab_with_ceiling(acc, col, x0 - 0.12, zn_w - 0.12, xm0 + 0.12, zs_w + 0.12, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    A.slab_with_ceiling(acc, col, xm0 - 0.12, zn_e - 0.12, x1 + 0.12, zs_e + 0.12, yr - 0.22, yr, 'roof', 'concrete', add_col=True)
    for bx0, bz0, bx1, bz1 in (
        (x0 - 0.15, zn_w - 0.15, xm0 + 0.15, zn_w + 0.15),
        (x0 - 0.15, zs_w - 0.15, xm0, zs_w + 0.15),
        (x0 - 0.15, zn_w - 0.15, x0 + 0.15, zs_w + 0.15),
        (xm1, zn_e - 0.15, x1 + 0.15, zn_e + 0.15),
        (xm0 - 0.15, zs_e - 0.15, x1 + 0.15, zs_e + 0.15),
        (x1 - 0.15, zn_e - 0.15, x1 + 0.15, zs_e + 0.15),
    ):
        A.box(acc, bx0, yr, bz0, bx1, yr + 0.75, bz1, facade)
    A.box(acc, xm0 - 0.18, yr, zn_e - 0.18, xm1 + 0.18, yr + 1.05, zs_e + 0.18, facade, skip=('+y', '-y'))
    A.box(acc, xm0, yr + 0.9, zn_e, xm1, yr + 1.08, zs_e, concrete)
    A.solar_panels(acc, xm1 + 0.4, x1 - 4.8, zn_e + 0.6, zs_e - 0.6, yr + 0.04)


def _build_canteen(acc, col, x0, x1, z0, z1, rooms, doors):
    cm = L.mat('collision')
    facade, flr, concrete, roof_m, glass_b = L.mat('facade'), L.mat('floor'), L.mat('concrete'), L.mat('roof'), L.mat('glass_blue')
    h1, h2 = 4.2, 3.4
    y0, y1, y2 = 0.25, 0.25 + h1, 0.25 + h1 + h2
    R = 11.5
    acx, acz = x0 + R, z1 - R

    A.box(acc, x0, 0.0, z0, x1, y0, acz, flr)
    A.box(acc, acx, 0.0, acz, x1, y0, z1, flr)
    A.box(col, x0, 0.0, z0, x1, y0, acz, cm)
    A.box(col, acx, 0.0, acz, x1, y0, z1, cm)
    A.slab_with_ceiling(acc, col, x0, z0, x1, acz, y1 - 0.25, y1, 'concrete', 'concrete', add_col=True)
    A.slab_with_ceiling(acc, col, acx, acz, x1, z1, y1 - 0.25, y1, 'concrete', 'concrete', add_col=True)

    seg = 24
    a0, a1 = math.pi / 2, math.pi
    for yy, h_s, m_top, do_col in ((0.0, y0, flr, True), (y1 - 0.25, 0.25, L.mat('ceiling_white'), True), (y2 - 0.22, 0.22, roof_m, False)):
        for i in range(seg):
            t0, t1 = a0 + (a1 - a0) * i / seg, a0 + (a1 - a0) * (i + 1) / seg
            p0 = (acx, yy + h_s, acz)
            p1 = (acx + R * math.cos(t0), yy + h_s, acz + R * math.sin(t0))
            p2 = (acx + R * math.cos(t1), yy + h_s, acz + R * math.sin(t1))
            A.poly(acc, [p0, p2, p1], m_top)
            A.poly(acc, [p0, p1, p2], L.mat('ceiling_white'))
            if do_col:
                A.poly(col, [p0, p2, p1], cm)

    A.wall_x(acc, col, x0, x1, z0, y0, y1, 0.26, 'facade', [
        (x0 + 2.5, x0 + 10.0, y0 + 1.0, y0 + 3.2, 'window'),
        (x0 + 13.0, x1 - 3.5, y0 + 1.0, y0 + 3.2, 'window'),
    ], dado=True)
    A.wall_z(acc, col, z0, z1, x1, y0, y1, 0.26, 'facade', [
        (z0 + 3.0, z0 + 10.0, y0 + 1.1, y0 + 3.1, 'window'),
        (z1 - 10.5, z1 - 3.5, y0 + 1.1, y0 + 3.1, 'window'),
    ], dado=True)
    A.wall_z(acc, col, z0, acz, x0, y0, y1, 0.26, 'facade', [
        (z0 + 2.0, z0 + 7.5, y0 + 0.9, y0 + 3.25, 'glass_wall'),
        (acz - 4.0, acz - 1.2, y0, y0 + 2.65, 'door'),
    ], dado=True)
    _add_door(doors, 'north', x0, y0, acz - 2.6, 'canteen_entrance', 'west')
    A.wall_x(acc, col, acx, x1, z1, y0, y1, 0.26, 'facade', [
        (acx + 2.0, acx + 4.8, y0, y0 + 2.65, 'door'),
        (acx + 6.8, x1 - 3.0, y0 + 0.9, y0 + 3.25, 'glass_wall'),
    ], dado=True)
    _add_door(doors, 'north', acx + 3.4, y0, z1, 'canteen_entrance', 'south')

    for ly0, ly1 in ((y0, y1), (y1, y2)):
        A.arc_wall(acc, col, acx, acz, R - 0.26, R + 0.06, ly0 - (0.25 if ly0 > y0 else 0.0), ly0 + 0.75, a0, a1, facade, seg=seg, cap_ends=False)
        A.arc_wall(acc, col, acx, acz, R - 0.08, R - 0.02, ly0 + 0.75, ly1 - 0.35, a0, a1, glass_b, seg=seg, cap_ends=False)
        A.arc_wall(acc, col, acx, acz, R - 0.26, R + 0.14, ly1 - 0.35, ly1, a0, a1, facade, seg=seg, cap_ends=False)
        for ci in range(6):
            ang = a0 + (a1 - a0) * (ci + 0.5) / 6
            A.round_col(acc, col, acx + (R - 0.08) * math.cos(ang), acz + (R - 0.08) * math.sin(ang), 0.24, ly0, ly1, 'facade')

    A.box(acc, x0 - 1.8, y0 + 2.8, acz - 4.6, x0, y0 + 3.15, acz - 0.8, concrete)
    A.round_col(acc, col, x0 - 1.45, acz - 4.1, 0.20, 0.03, y0 + 2.8, 'facade')
    A.round_col(acc, col, x0 - 1.45, acz - 1.2, 0.20, 0.03, y0 + 2.8, 'facade')
    A.box(acc, x0 - 0.8, 0.0, acz - 4.4, x0, y0, acz - 1.0, concrete)

    kx = x1 - 6.5
    A.wall_z(acc, col, z0, z1, kx, y0, y1 - 0.25, 0.22, 'plaster', [
        (z0 + 2.5, z0 + 9.5, y0 + 1.05, y0 + 2.35, 'window'),
        (z0 + 12.0, z1 - 4.0, y0 + 1.05, y0 + 2.35, 'window'),
    ], dado=True)
    A.box(acc, kx - 0.65, y0, z0 + 2.2, kx + 0.25, y0 + 1.05, z1 - 3.8, concrete)
    A.box(col, kx - 0.65, y0, z0 + 2.2, kx + 0.25, y0 + 1.05, z1 - 3.8, cm)
    _add_room(rooms, 'north', 'canteen', 1, x0 + 3.0, z0 + 2.2, kx - 1.4, z1 - 3.0, y0, ceil_h=h1 - 0.28)

    A.box(acc, x0, y1, z0, x1, y2, acz, facade)
    A.box(acc, acx, y1, acz, x1, y2, z1, facade)
    A.box(col, x0, y1, z0, x1, y2 + 0.6, acz, cm)
    A.box(col, acx, y1, acz, x1, y2 + 0.6, z1, cm)
    for wx in range(int(x0) + 3, int(x1) - 4, 5):
        A._window_x(acc, None, wx, wx + 3.4, y1 + 0.8, y2 - 0.55, z0, 0.26, 'glass_blue')
    for wx in range(int(acx) + 2, int(x1) - 4, 5):
        A._window_x(acc, None, wx, wx + 3.4, y1 + 0.8, y2 - 0.55, z1, 0.26, 'glass_blue')
    for wz in range(int(z0) + 3, int(z1) - 4, 5):
        A._window_z(acc, None, wz, wz + 3.4, y1 + 0.8, y2 - 0.55, x1, 0.26, 'glass_blue')
    A.box(acc, x0 - 0.2, y2 - 0.22, z0 - 0.2, x1 + 0.2, y2 + 0.05, acz, concrete)
    A.box(acc, acx, y2 - 0.22, acz, x1 + 0.2, y2 + 0.05, z1 + 0.2, concrete)
    A.box(acc, x0, y2 + 0.05, z0, x1, y2 + 0.12, acz, roof_m)
    A.box(acc, acx, y2 + 0.05, acz, x1, y2 + 0.12, z1, roof_m)


def _build_shop(acc, col, s, coll, doors):
    x0, z0, x1, z1 = s['box']
    units = s.get('units', 3)
    H = 3.55
    cm = L.mat('collision')
    facade, stone = L.mat('facade'), L.mat('stone')

    A.box(acc, x0 - 0.3, 0.0, z0, x1 + 0.3, 0.22, z1 + 1.0, stone)
    A.box(acc, x0, 0.22, z0, x1, 0.25, z1, L.mat('floor'))
    w = (x1 - x0) / units
    A.box(acc, x0, 0.22, z0, x1, H, z0 + 0.24, facade)
    A.box(col, x0, 0.0, z0, x1, H + 0.8, z0 + 0.24, cm)

    for k in range(units + 1):
        xx = x0 + k * w
        if k == 1:
            A.wall_z(acc, col, z0, z1, xx, 0.22, H - 0.18, 0.24, 'plaster', [
                (z0 + 2.4, z0 + 4.3, 0.22, 2.45, 'door'),
            ], dado=True)
            _add_door(doors, 'north', xx, 0.22, z0 + 3.35, 'shop_inner', 'east')
        else:
            A.wall_z(acc, col, z0, z1, xx, 0.22, H, 0.26, 'facade', dado=True)

    A.slab_with_ceiling(acc, col, x0 - 0.2, z0 - 0.2, x1 + 0.2, z1 + 0.2, H - 0.18, H + 0.12, 'roof', 'concrete', add_col=True)
    A.box(acc, x0 - 0.2, H + 0.12, z1, x1 + 0.2, H + 0.68, z1 + 0.22, facade)

    dx = s['door_x']
    ux0, ux1 = x0 + 0.14, x0 + w - 0.14
    A.wall_x(acc, col, ux0, ux1, z1 - 0.12, 0.22, H, 0.24, 'facade', [
        (dx - 0.8, dx + 0.8, 0.22, 2.5, 'door'),
        (dx + 1.1, ux1 - 0.2, 0.88, 2.5, 'window'),
    ], dado=True)
    _add_door(doors, 'north', dx, 0.22, z1, 'shop', 'south')
    A.box(acc, ux0 + 0.45, 0.25, z0 + 1.6, ux0 + 2.6, 1.15, z0 + 2.2, L.mat('wood'))
    for sz in (z0 + 0.45, z0 + 4.3):
        A.box(acc, ux0 + 2.8, 0.25, sz, ux1 - 0.35, 1.95, sz + 0.45, L.mat('wood_dark'))
    A.box(acc, ux0 + 0.45, 0.25, z0 + 3.2, ux0 + 1.35, 1.85, z0 + 4.6, L.mat('glass_blue'))

    mx0, mx1 = x0 + w + 0.14, x0 + 2 * w - 0.14
    A.wall_x(acc, col, mx0, mx1, z1 - 0.12, 0.22, H, 0.24, 'facade', [
        (mx0 + 0.6, mx1 - 0.6, 0.88, 2.5, 'window'),
    ], dado=True)
    for sz in (z0 + 0.45, z0 + 2.3, z0 + 4.2):
        A.box(acc, mx0 + 0.9, 0.25, sz, mx1 - 1.3, 1.95, sz + 0.48, L.mat('wood_dark'))
    A.box(acc, mx1 - 1.0, 0.25, z0 + 1.2, mx1 - 0.3, 1.90, z0 + 4.8, L.mat('glass_blue'))

    sign_x0, sign_x1 = x0 + 0.25, x0 + 2 * w - 0.25
    A.box(acc, sign_x0, 2.68, z1, sign_x1, 3.45, z1 + 0.08, L.mat('red_sign'))
    A.text_mesh(coll, s.get('name', '小卖部'), ((sign_x0 + sign_x1) / 2, 3.05, z1 + 0.1), 0.54, 'plaster_yellow', facing='south')
    awn = L.mat('awning')
    A.poly(acc, [(sign_x0, 2.65, z1), (sign_x1, 2.65, z1), (sign_x1, 2.18, z1 + 1.15), (sign_x0, 2.18, z1 + 1.15)], awn)
    A.poly(acc, [(sign_x0, 2.18, z1 + 1.15), (sign_x1, 2.18, z1 + 1.15), (sign_x1, 2.65, z1), (sign_x0, 2.65, z1)], awn)

    ex0, ex1 = x0 + 2 * w + 0.14, x1 - 0.14
    A.box(acc, ex0, 0.22, z1 - 0.10, ex1, 2.85, z1 - 0.04, L.mat('shutter'))
    A.box(acc, ex0, 2.85, z1 - 0.24, ex1, H, z1, facade)
    A.box(col, ex0, 0.0, z1 - 0.24, ex1, H, z1, cm)

    # 门前四段紧凑绿篱（以 x0, z1 为相对基准自动对齐！）
    hz0, hz_m, hz1 = z1 + 0.2, z1 + 1.8, z1 + 3.9
    A.add_hedge(acc, col, x0 - 0.8, hz0, x0 + 0.6, hz1, 0.03, 0.88)
    A.add_hedge(acc, col, x0 + 4.8, hz0, x0 + 12.6, hz_m, 0.03, 0.88)
    A.add_hedge(acc, col, x0 + 4.8, hz_m - 0.04, x0 + 6.2, hz1, 0.03, 0.88)
    A.add_hedge(acc, col, x0 + 11.2, hz_m - 0.04, x0 + 12.6, hz1, 0.03, 0.88)
    A.add_hedge(acc, col, x1 - 0.6, hz0, x1 + 0.8, hz1, 0.03, 0.88)


# ================================================================ 6. playground（西南紧凑操场）

def build_playground(cfg, coll):
    pg = cfg['playground']
    src = os.path.join(ROOT, pg['source'])
    x0, z0, x1, z1 = pg['box']
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2

    bpy.ops.import_scene.gltf(filepath=src)
    bad_prefixes = (
        'PunishPillar', 'PunishPos', 'Speaker_01_01', 'Ceiling_parts_01_01',
        'Blackboard_01_01', 'GongGaoPai', 'TestVendingMachine', 'ShouHuoJi', 'PMxiang',
        'LaTiao', 'ShuPian', 'PPT', 'HuoTuiChang', 'navmesh', 'surface1',
    )
    del_set = set()
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) for p in bad_prefixes):
            del_set.add(obj)
    changed = True
    while changed:
        changed = False
        for obj in bpy.data.objects:
            if obj.parent in del_set and obj not in del_set:
                del_set.add(obj)
                changed = True
    for obj in list(del_set):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    root = bpy.data.objects.get('Set1')
    bpy.context.view_layer.update()
    pts = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            pts.extend(obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box)
    mn_x, mx_x = min(v.x for v in pts), max(v.x for v in pts)
    mn_y, mx_y = min(v.y for v in pts), max(v.y for v in pts)
    mn_z = min(v.z for v in pts)
    sx, sy = mx_x - mn_x, mx_y - mn_y
    mid_x, mid_y = (mn_x + mx_x) / 2, (mn_y + mx_y) / 2

    target_w, target_d = (x1 - x0) - 2.2, (z1 - z0) - 2.2
    scale = min(target_w / sy, target_d / sx, 1.15)

    wrap = bpy.data.objects.new('PlaygroundRoot', None)
    coll.objects.link(wrap)
    if root:
        root.parent = wrap
        root.location = (-mid_x, -mid_y, -mn_z)
    wrap.rotation_euler = (0.0, 0.0, math.pi / 2)
    wrap.scale = (scale, scale, scale)
    wrap.location = (cx, -cz, 0.04)

    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)
    A.box(acc, x0, 0.0, z0, x1, 0.032, z1, L.mat('asphalt'), skip=('-y',))
    A.box(acc, x0 - 0.22, 0.0, z0 - 0.22, x1 + 0.22, 0.13, z0, L.mat('concrete'))
    A.box(acc, x0 - 0.22, 0.0, z1, x1 + 0.22, 0.13, z1 + 0.22, L.mat('concrete'))
    A.box(acc, x0 - 0.22, 0.0, z0, x0, 0.13, z1, L.mat('concrete'))
    A.box(acc, x1, 0.0, z0, x1 + 0.22, 0.13, z1, L.mat('concrete'))
    A.box(col, x0, -0.2, z0, x1, 0.04, z1, L.mat('collision'))
    acc.build('playground_pad', coll)
    col.build('playground-colonly', coll)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = set(argv)
    cfg = json.load(open(CFG_PATH, encoding='utf-8'))
    rooms = json.load(open(ROOMS_PATH, encoding='utf-8')) if (only and os.path.exists(ROOMS_PATH)) else {}
    doors = json.load(open(DOORS_PATH, encoding='utf-8')) if (only and os.path.exists(DOORS_PATH)) else {}

    builders = [
        ('extras', lambda coll: build_extras(cfg, coll)),
        ('library', lambda coll: build_library(cfg, coll, doors)),
        ('gaosan', lambda coll: build_gaosan(cfg, coll, rooms, doors)),
        ('cuihua', lambda coll: build_cuihua(cfg, coll, rooms, doors)),
        ('north', lambda coll: build_north(cfg, coll, rooms, doors)),
        ('playground', lambda coll: build_playground(cfg, coll)),
    ]

    tex_out = os.path.join(OUT_DIR, 'playground_tex')
    if (not only or 'playground' in only) and os.path.isdir(tex_out):
        for fn in os.listdir(tex_out):
            if not fn.endswith('.import'):
                os.remove(os.path.join(tex_out, fn))

    for mod_id, fn in builders:
        if only and mod_id not in only:
            continue
        t0 = time.time()
        rooms.pop(mod_id, None)
        doors.pop(mod_id, None)
        L.reset_scene()
        coll = bpy.context.scene.collection
        fn(coll)
        out = os.path.join(OUT_DIR, mod_id + '.gltf')
        if mod_id == 'playground':
            bpy.ops.export_scene.gltf(
                filepath=out, export_format='GLTF_SEPARATE',
                export_texture_dir='playground_tex',
                export_apply=True,
            )
        else:
            L.export_gltf(out)
        print('OK %-12s %7d 面  %.1fs → %s' % (mod_id, L.tri_count(), time.time() - t0, out))

    json.dump(rooms, open(ROOMS_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(doors, open(DOORS_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, rs in rooms.items():
        types = [r['type'] for r in rs]
        print('房间 %-10s 共 %d 间：%s' % (k, len(rs), {t: types.count(t) for t in set(types)}))


if __name__ == '__main__':
    main()
