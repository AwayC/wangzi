"""MC 里没有、需要新做的校园部件：小卖部、校门（含门卫室和伸缩门）、围墙、整片地面。由 build_mc_campus.py 调用。

坐标直接用游戏坐标（米，x 东、z 南、y 上），导出后场景里放在原点即可。
参数来自 data/map/campus_plots.json 的 extras。
"""
import math
import os

import bpy

import mc_lib as L

FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'


def G(x, y, z):
    """游戏坐标 → mc_lib 用的 MC 坐标（y + 4）。"""
    return x, y + L.GROUND_Y, z


def box(acc, x0, y0, z0, x1, y1, z1, m, skip=()):
    acc.box(x0, y0 + L.GROUND_Y, z0, x1, y1 + L.GROUND_Y, z1, m, skip)


def build(cfg, coll):
    ex = cfg['extras']
    acc = L.MeshAcc()
    col = L.MeshAcc(uv=False)
    _ground(acc, col, cfg)
    _wall(acc, col, cfg)
    _gate(acc, col, ex['gate'], coll)
    _shop(acc, col, ex['shop'], coll)
    acc.build('extras', coll)
    col.build('extras-colonly', coll)


# ---------------------------------------------------------------- 地面

def _ground(acc, col, cfg):
    """围墙内整片草地（地块之间的空隙也有地），比 MC 草地略低。"""
    ox, oz = cfg['origin_mc']
    xs = [p[0] - ox for p in cfg['wall']]
    zs = [p[1] - oz for p in cfg['wall']]
    # L 形用两块矩形拼：外包框减去西北缺角
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    cut = cfg['extras'].get('ground_cut', [])
    rects = [(x0, z0, x1, z1)] if not cut else [(cut[2], z0, x1, cut[3]), (x0, cut[3], x1, z1)]
    gm = L.mat('grass')
    for a, b, c, d in rects:
        box(acc, a, -0.6, b, c, -0.04, d, gm, skip=('-y',))
        box(col, a, -0.6, b, c, -0.04, d, L.mat('collision'))


# ---------------------------------------------------------------- 围墙

def _wall(acc, col, cfg):
    """2.4 m 实墙 + 0.6 m 铁艺：毛石墙基、涂料墙身、混凝土压顶，每 4 m 一根壁柱；南墙在校门处断开。"""
    ox, oz = cfg['origin_mc']
    pts = [(p[0] - ox, p[1] - oz) for p in cfg['wall']]
    g = cfg['extras']['gate']
    gx0, gx1, gz = g['x'][0] - 15, g['x'][1] + 15, g['z']  # 门洞两侧还有门柱、侧门、塔楼
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
        Y = L.GROUND_Y
        acc.obox(cx, cz, length + 0.4, 0.5, Y - 0.1, Y + 0.6, ang, stone)
        acc.obox(cx, cz, length + 0.3, 0.3, Y + 0.6, Y + 2.3, ang, plaster)
        acc.obox(cx, cz, length + 0.4, 0.42, Y + 2.3, Y + 2.42, ang, cap)
        col.obox(cx, cz, length + 0.4, 0.5, Y - 0.1, Y + 3.0, ang, cm)
        n = max(1, int(length / 4))
        for k in range(n + 1):
            t = k / n
            px, pz = a[0] + dx * t, a[1] + dz * t
            acc.obox(px, pz, 0.5, 0.5, Y + 0.6, Y + 2.5, ang, plaster)
            acc.obox(px, pz, 0.6, 0.6, Y + 2.5, Y + 2.62, ang, cap)
        # 铁艺：横杆 + 竖杆（每 0.2 m）
        acc.obox(cx, cz, length, 0.05, Y + 2.95, Y + 3.0, ang, iron)
        bars = int(length / 0.2)
        for k in range(bars):
            t = (k + 0.5) / bars
            acc.obox(a[0] + dx * t, a[1] + dz * t, 0.025, 0.025, Y + 2.42, Y + 3.0, ang, iron)


# ---------------------------------------------------------------- 校门

def _gate(acc, col, g, coll):
    """照 MC 原图的南校门：两侧阶梯状塔楼（米黄腰线，西塔底层是门卫室）+ 两根门柱 + 24 m 门洞（西半推拉铁门关着、东扇斜开）
    + 塔楼和门柱之间的人行侧门。g['x'] 是门洞东西两端，g['z'] 是围墙线。"""
    x0, x1, z = g['x'][0], g['x'][1], g['z']
    Y = L.GROUND_Y
    cm = L.mat('collision')
    facade, sand, cap, stone = L.mat('facade'), L.mat('sandstone'), L.mat('concrete'), L.mat('stone')
    metal, dark = L.mat('metal'), L.mat('metal_dark')
    # 门前门后铺地
    acc.box(x0 - 16, Y - 0.04, z - 12, x1 + 16, Y + 0.02, z + 8, L.mat('plaza'), skip=('-y',))
    for side in (-1, 1):
        # side=-1 西，+1 东；inner = 靠门洞的一边
        inner = x0 - 6 if side < 0 else x1 + 6      # 塔楼内侧（离门洞 6 m：门柱 3 + 侧门 3）
        outer = inner + side * 9                    # 塔楼外侧
        tx0, tx1 = min(inner, outer), max(inner, outer)
        tz0, tz1 = z - 5, z + 5
        # 底座 4 m（西塔里面是门卫室）
        _tower_base(acc, col, tx0, tx1, tz0, tz1, Y, side, guard=side < 0)
        # 内侧高塔 6 m 宽，到 13 m；外侧肩部 3 m 宽，到 8 m
        hx0, hx1 = (inner - 6, inner) if side < 0 else (inner, inner + 6)
        sx0, sx1 = (outer, outer + 3) if side < 0 else (outer - 3, outer)
        acc.box(hx0, Y + 4.2, tz0 + 1, hx1, Y + 9.4, tz1 - 1, facade)
        acc.box(hx0 - 0.15, Y + 9.4, tz0 + 0.85, hx1 + 0.15, Y + 10.6, tz1 - 0.85, sand)
        acc.box(hx0, Y + 10.6, tz0 + 1, hx1, Y + 12.0, tz1 - 1, facade)
        acc.box(hx0 - 0.2, Y + 12.0, tz0 + 0.8, hx1 + 0.2, Y + 13.0, tz1 - 0.8, sand)
        acc.box(hx0 - 0.25, Y + 13.0, tz0 + 0.75, hx1 + 0.25, Y + 13.15, tz1 - 0.75, cap)
        acc.box(sx0, Y + 4.2, tz0 + 1, sx1, Y + 7.0, tz1 - 1, facade)
        acc.box(sx0 - 0.15, Y + 7.0, tz0 + 0.85, sx1 + 0.15, Y + 8.0, tz1 - 0.85, sand)
        acc.box(sx0 - 0.2, Y + 8.0, tz0 + 0.8, sx1 + 0.2, Y + 8.12, tz1 - 0.8, cap)
        # 高塔正面竖向凹槽 + 窄窗
        for zz in (tz0 + 1, tz1 - 1):
            for k in range(3):
                wx = hx0 + 1.2 + k * 1.8
                acc.box(wx - 0.3, Y + 5.0, zz - 0.04, wx + 0.3, Y + 8.8, zz + 0.04, L.mat('glass_dark'))
                acc.box(wx - 0.36, Y + 4.94, zz - 0.06, wx + 0.36, Y + 5.0, zz + 0.06, L.mat('frame'))
        col.box(tx0, Y, tz0, tx1, Y + 13.2, tz1, cm)
        # 门柱 3 × 5，7 m，顶部米黄腰线 + 灯
        px0, px1 = (x0 - 3, x0) if side < 0 else (x1, x1 + 3)
        acc.box(px0 - 0.1, Y, z - 2.6, px1 + 0.1, Y + 0.6, z + 2.6, stone)
        acc.box(px0, Y + 0.6, z - 2.5, px1, Y + 6.0, z + 2.5, facade)
        acc.box(px0 - 0.15, Y + 6.0, z - 2.65, px1 + 0.15, Y + 7.0, z + 2.65, sand)
        acc.box(px0 - 0.2, Y + 7.0, z - 2.7, px1 + 0.2, Y + 7.12, z + 2.7, cap)
        acc.box((px0 + px1) / 2 - 0.25, Y + 7.12, z - 0.25, (px0 + px1) / 2 + 0.25, Y + 7.6, z + 0.25, L.mat('light_warm'))
        col.box(px0, Y, z - 2.6, px1, Y + 7.6, z + 2.6, cm)
        # 人行侧门（门柱与塔楼之间 3 m）：开着的格栅小门
        gx = px0 if side < 0 else px1
        _grille(acc, (gx, z), (gx, z + 1.4), 1.6, dark)  # 门扇向校内开着，贴在门柱侧面
    # 西半：推拉铁门关着；东扇：斜开
    mid = (x0 + x1) / 2
    _grille(acc, (x0, z), (mid, z), 1.8, metal, frame=dark)
    col.box(x0, Y, z - 0.1, mid, Y + 1.8, z + 0.1, cm)
    ang = math.radians(32)
    ex = (x1 - math.cos(ang) * (x1 - mid), z - math.sin(ang) * (x1 - mid))
    _grille(acc, (x1, z), ex, 1.8, metal, frame=dark)
    acc.box(x0 - 0.05, Y - 0.02, z - 0.08, x1 + 0.05, Y + 0.02, z + 0.08, dark)  # 地轨
    # 校名：西塔高塔南面，竖排红底金字
    hx = x0 - 6 - 3
    acc.box(hx - 0.9, Y + 4.6, z + 4.0, hx + 0.9, Y + 9.2, z + 4.08, L.mat('red_sign'))
    name = g.get('name', '荒烟中学')
    for k, ch in enumerate(name):
        _text(coll, ch, (hx, Y + 8.5 - k * 1.05, z + 4.1), 0.85, 'gold', facing='south')
    # 门外两侧花坛
    for px in (x0 - 13, x1 + 13):
        acc.box(px - 2, Y, z + 6, px + 2, Y + 0.5, z + 7.6, stone)
        acc.box(px - 1.85, Y + 0.5, z + 6.15, px + 1.85, Y + 0.52, z + 7.45, L.mat('soil'))
        col.box(px - 2, Y, z + 6, px + 2, Y + 0.5, z + 7.6, cm)


def _tower_base(acc, col, x0, x1, z0, z1, Y, side, guard):
    """塔楼底座：毛石勒脚 + 白墙；门卫室在里面，门和核验窗口开在朝侧门的一面。"""
    facade, stone, cap = L.mat('facade'), L.mat('stone'), L.mat('concrete')
    acc.box(x0 - 0.1, Y, z0 - 0.1, x1 + 0.1, Y + 0.5, z1 + 0.1, stone)
    inner_x = x1 if side < 0 else x0  # 朝门洞那面
    t = 0.3
    if not guard:
        acc.box(x0, Y + 0.5, z0, x1, Y + 4.0, z1, facade)
    else:
        # 四面墙：内侧墙开门（南）和核验窗口（北）
        acc.box(x0, Y + 0.5, z0, x1, Y + 4.0, z0 + t, facade)
        acc.box(x0, Y + 0.5, z1 - t, x1, Y + 4.0, z1, facade)
        outer_x = x0 if side < 0 else x1
        acc.box(min(outer_x, outer_x - side * t), Y + 0.5, z0, max(outer_x, outer_x - side * t), Y + 4.0, z1, facade)
        ix0, ix1 = (inner_x - t, inner_x) if side < 0 else (inner_x, inner_x + t)
        dz0, dz1 = z1 - 3.4, z1 - 2.2          # 门
        wz0, wz1 = z0 + 1.6, z0 + 4.2          # 核验窗口
        for a, b in ((z0, wz0), (wz1, dz0), (dz1, z1)):
            acc.box(ix0, Y + 0.5, a, ix1, Y + 4.0, b, facade)
        acc.box(ix0, Y + 0.5, wz0, ix1, Y + 1.5, wz1, facade)
        acc.box(ix0, Y + 2.8, wz0, ix1, Y + 4.0, wz1, facade)
        acc.box(ix0, Y + 2.7, dz0, ix1, Y + 4.0, dz1, facade)
        acc.box((ix0 + ix1) / 2 - 0.02, Y + 1.5, wz0, (ix0 + ix1) / 2 + 0.02, Y + 2.8, wz1, L.mat('glass'))
        acc.box(ix0 - 0.45 if side < 0 else ix1, Y + 1.45, wz0, ix1 + 0.45 if side > 0 else ix0, Y + 1.53, wz1, cap)  # 窗口台面
        acc.box((ix0 + ix1) / 2 - 0.03, Y + 0.5, dz0 + 0.05, (ix0 + ix1) / 2 + 0.03, Y + 2.65, dz1 - 0.05, L.mat('wood'))
        acc.box(x0 + t, Y + 0.5, z0 + t, x1 - t, Y + 0.55, z1 - t, L.mat('floor'))
        acc.box(x0 + 1.0, Y + 0.55, z0 + 1.0, x0 + 2.4, Y + 1.3, z0 + 1.8, L.mat('wood_dark'))  # 值班桌
        _text_sign(acc, inner_x, Y + 3.3, (wz0 + wz1) / 2, side)
        col.box(x0, Y, z0, x1, Y + 4.0, z0 + t, L.mat('collision'))
        col.box(x0, Y, z1 - t, x1, Y + 4.0, z1, L.mat('collision'))
    acc.box(x0 - 0.3, Y + 4.0, z0 - 0.3, x1 + 0.3, Y + 4.2, z1 + 0.3, cap)


def _text_sign(acc, x, y, z, side):
    acc.box(x - 0.04 if side < 0 else x, y - 0.2, z - 1.0, x + 0.04 if side > 0 else x, y + 0.2, z + 1.0, L.mat('red_sign'))


def _grille(acc, a, b, h, m, frame=None):
    """格栅门：上下框 + 竖杆（每 0.15 m），a→b 是门的走向（游戏坐标 x, z）。"""
    Y = L.GROUND_Y
    frame = frame or m
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dz)
    if length < 0.1:
        return
    ang = math.atan2(dz, dx)
    cx, cz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    acc.obox(cx, cz, length, 0.06, Y + 0.1, Y + 0.18, ang, frame)
    acc.obox(cx, cz, length, 0.06, Y + h - 0.08, Y + h, ang, frame)
    acc.obox(cx, cz, length, 0.04, Y + h * 0.55, Y + h * 0.55 + 0.05, ang, frame)
    n = int(length / 0.15)
    for k in range(n + 1):
        t = k / max(n, 1)
        acc.obox(a[0] + dx * t, a[1] + dz * t, 0.03, 0.03, Y + 0.1, Y + h, ang, m)
    for t in (0.0, 1.0):
        acc.obox(a[0] + dx * t, a[1] + dz * t, 0.08, 0.08, Y, Y + h + 0.05, ang, frame)


def _bar(acc, a, b, m, r=0.025):
    L._cyl_between(acc, a, b, r, r, m, seg=4)


def _wall_with_windows(acc, a, b, y0, y1, m):
    """小房子的墙：每 1.8 m 一扇窗（窗台 0.9 m、高 1.3 m）。"""
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dz)
    ang = math.atan2(dz, dx)
    ux, uz = dx / length, dz / length
    frame, glass = L.mat('frame'), L.mat('glass')
    n = max(1, int(length / 1.8))
    seg = length / n
    for k in range(n):
        s0 = k * seg
        cx, cz = a[0] + ux * (s0 + seg / 2), a[1] + uz * (s0 + seg / 2)
        acc.obox(cx, cz, seg, 0.24, y0, y0 + 0.9, ang, m)
        acc.obox(cx, cz, seg, 0.24, y0 + 2.2, y1, ang, m)
        acc.obox(cx, cz, 0.35, 0.24, y0 + 0.9, y0 + 2.2, ang, m)
        acc.obox(cx + ux * seg * 0.3, cz + uz * seg * 0.3, seg * 0.4 - 0.1, 0.24, y0 + 0.9, y0 + 2.2, ang, m)
        acc.obox(cx - ux * seg * 0.3, cz - uz * seg * 0.3, seg * 0.4 - 0.1, 0.24, y0 + 0.9, y0 + 2.2, ang, m)
        acc.obox(cx, cz, 0.62, 0.03, y0 + 0.92, y0 + 2.18, ang, glass)
        acc.obox(cx, cz, 0.7, 0.1, y0 + 0.88, y0 + 0.94, ang, frame)


# ---------------------------------------------------------------- 小卖部

def _shop(acc, col, s, coll):
    """食堂北侧一排单层铺面：最西一间小卖部（玻璃橱窗、门、遮阳棚、招牌、柜台货架），其余卷帘门；门前绿篱只在小卖部门口留缺口。"""
    x0, z0, x1, z1 = s['box']
    units = s.get('units', 3)
    Y = L.GROUND_Y
    H = 3.6
    cm = L.mat('collision')
    facade, cap, stone, frame, glass = L.mat('facade'), L.mat('concrete'), L.mat('stone'), L.mat('frame'), L.mat('glass')
    acc.box(x0 - 0.3, Y, z0, x1 + 0.3, Y + 0.3, z1 + 1.2, stone)  # 台基 + 门前台阶平台
    acc.box(x0, Y + 0.3, z0, x1, Y + 0.32, z1, L.mat('floor'))
    w = (x1 - x0) / units
    # 后墙、侧墙、隔墙
    acc.box(x0, Y + 0.3, z0, x1, Y + H, z0 + 0.25, facade)
    for k in range(units + 1):
        xx = x0 + k * w
        acc.box(xx - 0.15, Y + 0.3, z0, xx + 0.15, Y + H, z1, facade)
    # 屋面 + 女儿墙
    acc.box(x0 - 0.2, Y + H, z0 - 0.2, x1 + 0.2, Y + H + 0.3, z1 + 0.2, cap)
    acc.box(x0 - 0.2, Y + H + 0.3, z1, x1 + 0.2, Y + H + 0.9, z1 + 0.2, facade)
    col.box(x0, Y, z0, x1, Y + H + 0.9, z0 + 0.3, cm)
    for k in range(units):
        ux0, ux1 = x0 + k * w + 0.15, x0 + (k + 1) * w - 0.15
        if k == 0:
            _shop_front(acc, col, coll, ux0, ux1, z1, Y + 0.3, H - 0.3, s)
        else:  # 卷帘门 + 空白门头
            acc.box(ux0, Y + 0.3, z1 - 0.12, ux1, Y + 3.0, z1 - 0.05, L.mat('shutter'))
            acc.box(ux0, Y + 3.0, z1 - 0.35, ux1, Y + H, z1, facade)
            acc.box(ux0 + 0.3, Y + 3.05, z1, ux1 - 0.3, Y + 3.5, z1 + 0.06, L.mat('plaster_light_gray'))
            col.box(ux0, Y, z1 - 0.3, ux1, Y + H, z1, cm)
    # 门前绿篱：只在小卖部门口留缺口
    hz0, hz1 = z1 + 1.6, z1 + 2.5
    gap0, gap1 = s['door_x'] - 1.6, s['door_x'] + 1.6
    hm = L.mat('hedge')
    hedge = L.MeshAcc()
    for a, b in ((x0 - 0.5, gap0), (gap1, x1 + 0.5)):
        hedge.box(a, Y, hz0, b, Y + 1.1, hz1, hm, skip=('-y',))
        col.box(a, Y, hz0, b, Y + 1.1, hz1, cm)
    ob = hedge.build('shop_hedge', coll)
    if ob:
        L._round_edges(ob, 0.2)


def _shop_front(acc, col, coll, ux0, ux1, zf, y0, h, s):
    facade, frame, glass = L.mat('facade'), L.mat('frame'), L.mat('glass')
    cm = L.mat('collision')
    dx = s['door_x']
    # 窗下墙 + 橱窗 + 门
    for a, b in ((ux0, dx - 0.9), (dx + 0.9, ux1)):
        acc.box(a, y0, zf - 0.3, b, y0 + 0.8, zf, facade)
        acc.box(a, y0 + 0.8, zf - 0.16, b, y0 + 2.7, zf - 0.14, glass)
        n = max(1, int((b - a) / 1.2))
        for k in range(n + 1):
            xx = a + (b - a) * k / n
            acc.box(xx - 0.04, y0 + 0.8, zf - 0.2, xx + 0.04, y0 + 2.7, zf - 0.1, frame)
        acc.box(a, y0 + 0.78, zf - 0.22, b, y0 + 0.84, zf - 0.08, frame)
        col.box(a, y0, zf - 0.3, b, y0 + h, zf, cm)
    acc.box(dx - 0.9, y0 + 2.7, zf - 0.22, dx + 0.9, y0 + 2.76, zf - 0.08, frame)
    for xx in (dx - 0.9, dx + 0.9):
        acc.box(xx - 0.05, y0, zf - 0.22, xx + 0.05, y0 + 2.7, zf - 0.08, frame)
    # 敞开的玻璃门扇（推向室内）
    acc.box(dx - 0.85, y0, zf - 1.0, dx - 0.81, y0 + 2.6, zf - 0.22, glass)
    acc.box(dx - 0.88, y0, zf - 1.0, dx - 0.8, y0 + 0.08, zf - 0.22, frame)
    # 门头 + 招牌 + 遮阳棚
    acc.box(ux0, y0 + 2.7, zf - 0.3, ux1, y0 + h, zf, facade)
    acc.box(ux0 + 0.3, y0 + 2.75, zf, ux1 - 0.3, y0 + h - 0.05, zf + 0.08, L.mat('red_sign'))
    _text(coll, s.get('name', '小卖部'), ((ux0 + ux1) / 2, y0 + (2.75 + h) / 2 - 0.05, zf + 0.09), 0.5, 'plaster_yellow', facing='south')
    awn = L.mat('awning')
    for k in range(8):
        t0, t1 = k / 8, (k + 1) / 8
        acc.poly([L.to_bl(ux0, y0 + 2.6 - 0.5 * t0, zf + 1.2 * t0), L.to_bl(ux1, y0 + 2.6 - 0.5 * t0, zf + 1.2 * t0),
                  L.to_bl(ux1, y0 + 2.6 - 0.5 * t1, zf + 1.2 * t1), L.to_bl(ux0, y0 + 2.6 - 0.5 * t1, zf + 1.2 * t1)], awn)
    acc.box(ux0, y0 + 2.0, zf + 1.18, ux1, y0 + 2.12, zf + 1.22, awn)
    # 室内：柜台、货架、冰柜
    zi = zf - 0.3
    acc.box(ux1 - 4.0, y0, zi - 3.2, ux1 - 0.6, y0 + 1.0, zi - 2.6, L.mat('wood'))
    acc.box(ux1 - 4.1, y0 + 1.0, zi - 3.3, ux1 - 0.5, y0 + 1.05, zi - 2.5, L.mat('concrete'))
    for k in range(3):
        sx = ux0 + 0.6 + k * 1.6
        acc.box(sx, y0, zi - 7.3, sx + 1.3, y0 + 2.0, zi - 6.8, L.mat('wood_dark'))
        for lvl in (0.5, 1.0, 1.5):
            for j in range(5):
                c = ('red_sign', 'plaster_yellow', 'plaster_blue', 'plaster_green', 'plaster_orange')[(j + k + int(lvl * 2)) % 5]
                acc.box(sx + 0.05 + j * 0.25, y0 + lvl, zi - 6.8, sx + 0.25 + j * 0.25, y0 + lvl + 0.28, zi - 6.65, L.mat(c))
    acc.box(ux0 + 0.4, y0, zi - 2.0, ux0 + 1.2, y0 + 1.9, zi - 0.8, L.mat('plaster_white'))
    acc.box(ux0 + 1.2, y0 + 0.2, zi - 1.9, ux0 + 1.22, y0 + 1.8, zi - 0.9, glass)
    col.box(ux1 - 4.0, y0, zi - 3.2, ux1 - 0.6, y0 + 1.05, zi - 2.6, cm)


# ---------------------------------------------------------------- 文字

def _text(coll, s, pos, size, mat_key, facing='south'):
    """中文字：Blender 文字转网格。pos：游戏坐标的 MC 版（y 已加 4），字面中心。"""
    if not os.path.exists(FONT):
        return
    cu = bpy.data.curves.new('txt', 'FONT')
    try:
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except RuntimeError:
        return
    cu.body = s
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.extrude = 0.02
    ob = bpy.data.objects.new('text_' + s, cu)
    coll.objects.link(ob)
    x, y, z = pos
    ob.location = L.to_bl(x, y, z)
    # 文字默认躺在 XY 平面、朝 +Z；立起来后朝 -Y（Blender）= 南（+z 游戏）
    ob.rotation_euler = (math.pi / 2, 0, {'south': 0, 'north': math.pi, 'west': -math.pi / 2, 'east': math.pi / 2}[facing])
    ob.data.materials.append(L.mat(mat_key))
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(ob)
    mo = bpy.data.objects.new('sign_' + s, me)
    mo.matrix_world = ob.matrix_world
    coll.objects.link(mo)
    bpy.data.objects.remove(ob)
