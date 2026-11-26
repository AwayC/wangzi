"""v4.0 结构化校园建筑建模基础库（供 build_campus_v4.py 调用，在 Blender 中运行）。

全部接口直接使用游戏坐标（米，x 向东，z 向南，y 向上，地面 y=0），
内部复用 mc_lib 的程序化四方连续材质库（assets/env/campus/textures/）、MeshAcc 与 glTF 导出。
"""
import math
import os
import random

import bmesh
import bpy
import mc_lib as L

FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
Y0 = L.GROUND_Y  # mc_lib.to_bl 会减 GROUND_Y，这里统一补回使 y=0 为地面

# 补一个室内浅蓝墙裙材质（呼应 02_美术资源清单 ENV-T01 浅蓝墙裙 + 白墙）
if 'dado_blue' not in L._MDEF:
    L._MDEF['dado_blue'] = ('plaster', 4.0, (0.74, 0.84, 0.92), 0.85, 0, 'solid')
if 'ceiling_white' not in L._MDEF:
    L._MDEF['ceiling_white'] = ('plaster', 4.0, (1.06, 1.06, 1.05), 0.92, 0, 'solid')
if 'sign_graywhite' not in L._MDEF:
    L._MDEF['sign_graywhite'] = (None, 1, (0.84, 0.85, 0.86), 0.50, 0.02, 'solid')
if 'sign_darkgreen' not in L._MDEF:
    L._MDEF['sign_darkgreen'] = (None, 1, (0.06, 0.20, 0.11), 0.38, 0.15, 'solid')


def P(x, y, z):
    return L.to_bl(x, y + Y0, z)


def box(acc, x0, y0, z0, x1, y1, z1, m, skip=()):
    if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
        return
    acc.box(x0, y0 + Y0, z0, x1, y1 + Y0, z1, m, skip)


def obox(acc, cx, cz, length, width, y0, y1, ang, m):
    if length < 1e-4 or width < 1e-4 or y1 - y0 < 1e-4:
        return
    acc.obox(cx, cz, length, width, y0 + Y0, y1 + Y0, ang, m)


def poly(acc, pts_xyz, m):
    acc.poly([P(x, y, z) for x, y, z in pts_xyz], m)


def slab_with_ceiling(acc, col, x0, z0, x1, z1, y_bot, y_top, top_mat_key='floor', side_mat_key='concrete', add_col=True):
    """带白色底面吊顶、边缘混凝土梁面、顶面地砖/屋面的完整楼板。"""
    if x1 - x0 < 1e-4 or z1 - z0 < 1e-4 or y_top - y_bot < 1e-4:
        return
    box(acc, x0, y_bot, z0, x1, y_bot + 0.03, z1, L.mat('ceiling_white'), skip=('+y',))
    box(acc, x0, y_bot + 0.03, z0, x1, y_top - 0.03, z1, L.mat(side_mat_key), skip=('+y', '-y'))
    box(acc, x0, y_top - 0.03, z0, x1, y_top, z1, L.mat(top_mat_key), skip=('-y',))
    if add_col and col is not None:
        box(col, x0, y_bot, z0, x1, y_top, z1, L.mat('collision'))


def cyl(acc, cx, cz, r, y0, y1, m, seg=24, cap_top=True, cap_bot=True):
    """竖直圆柱（游戏坐标）。"""
    ring = [(cx + r * math.cos(2 * math.pi * i / seg), cz + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        j = (i + 1) % seg
        x0, z0 = ring[i]
        x1, z1 = ring[j]
        poly(acc, [(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)], m)
    if cap_top:
        poly(acc, [(x, y1, z) for x, z in reversed(ring)], m)
    if cap_bot:
        poly(acc, [(x, y0, z) for x, z in ring], m)


def clipped_cyl_slab(acc, col, cx, cz, r, x_clip, y_bot, y_top, top_mat_key='floor', seg=48):
    """仅保留 x <= x_clip 的弓形楼板，用于萃华楼玻璃圆塔与矩形门厅在 x = x_clip 零重叠无缝拼接。"""
    pts_2d = []
    for i in range(seg):
        a0 = 2 * math.pi * i / seg
        a1 = 2 * math.pi * (i + 1) / seg
        p0 = (cx + r * math.cos(a0), cz + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), cz + r * math.sin(a1))
        for pa, pb in ((p0, p1),):
            in_a, in_b = pa[0] <= x_clip + 1e-5, pb[0] <= x_clip + 1e-5
            if in_a:
                pts_2d.append(pa)
            if in_a != in_b:
                t = (x_clip - pa[0]) / (pb[0] - pa[0])
                pts_2d.append((x_clip, pa[1] + t * (pb[1] - pa[1])))
    if len(pts_2d) < 3:
        return
    # 扇形三角化（以圆心或弦中点为基准，凸弓形任意内点均可）
    piv_x = min(cx, x_clip - 0.5)
    piv_z = cz
    m_top = L.mat(top_mat_key)
    m_bot = L.mat('ceiling_white')
    m_side = L.mat('concrete')
    cm = L.mat('collision')
    n = len(pts_2d)
    for i in range(n):
        x0, z0 = pts_2d[i]
        x1, z1 = pts_2d[(i + 1) % n]
        poly(acc, [(piv_x, y_top, piv_z), (x1, y_top, z1), (x0, y_top, z0)], m_top)
        poly(acc, [(piv_x, y_bot, piv_z), (x0, y_bot, z0), (x1, y_bot, z1)], m_bot)
        poly(acc, [(x0, y_bot, z0), (x1, y_bot, z1), (x1, y_top, z1), (x0, y_top, z0)], m_side)
        if col is not None:
            poly(col, [(piv_x, y_top, piv_z), (x1, y_top, z1), (x0, y_top, z0)], cm)
            poly(col, [(piv_x, y_bot, piv_z), (x0, y_bot, z0), (x1, y_bot, z1)], cm)


def arc_wall(acc, col, cx, cz, r_in, r_out, y0, y1, a0, a1, m, seg=24, add_col=True, cap_ends=True):
    """弧形墙/弧形幕墙（角度从 +x 往 +z 弧度）。"""
    cm = L.mat('collision')
    for i in range(seg):
        t0 = a0 + (a1 - a0) * i / seg
        t1 = a0 + (a1 - a0) * (i + 1) / seg
        c0, s0 = math.cos(t0), math.sin(t0)
        c1, s1 = math.cos(t1), math.sin(t1)
        ox0, oz0 = cx + r_out * c0, cz + r_out * s0
        ox1, oz1 = cx + r_out * c1, cz + r_out * s1
        ix0, iz0 = cx + r_in * c0, cz + r_in * s0
        ix1, iz1 = cx + r_in * c1, cz + r_in * s1
        poly(acc, [(ox0, y0, oz0), (ox1, y0, oz1), (ox1, y1, oz1), (ox0, y1, oz0)], m)
        poly(acc, [(ix1, y0, iz1), (ix0, y0, iz0), (ix0, y1, iz0), (ix1, y1, iz1)], m)
        poly(acc, [(ox0, y1, oz0), (ox1, y1, oz1), (ix1, y1, iz1), (ix0, y1, iz0)], m)
        poly(acc, [(ox1, y0, oz1), (ox0, y0, oz0), (ix0, y0, iz0), (ix1, y0, iz1)], m)
        if add_col and col is not None:
            poly(col, [(ox0, y0, oz0), (ox1, y0, oz1), (ox1, y1, oz1), (ox0, y1, oz0)], cm)
            poly(col, [(ix1, y0, iz1), (ix0, y0, iz0), (ix0, y1, iz0), (ix1, y1, iz1)], cm)
    if cap_ends and abs((a1 - a0) - 2 * math.pi) > 1e-3:
        for ang, rev in ((a0, False), (a1, True)):
            c, s = math.cos(ang), math.sin(ang)
            pts = [(cx + r_in * c, y0, cz + r_in * s), (cx + r_out * c, y0, cz + r_out * s),
                   (cx + r_out * c, y1, cz + r_out * s), (cx + r_in * c, y1, cz + r_in * s)]
            poly(acc, list(reversed(pts)) if rev else pts, m)


def dome(acc, cx, cz, r, y_base, h, m, seg=32, rings=12):
    """光滑半球/椭球穹顶（内外双面，仰视与俯视均闭合）。"""
    m_in = L.mat('ceiling_white')
    for ri in range(rings):
        phi0 = (math.pi / 2) * ri / rings
        phi1 = (math.pi / 2) * (ri + 1) / rings
        r0, yy0 = r * math.cos(phi0), y_base + h * math.sin(phi0)
        r1, yy1 = r * math.cos(phi1), y_base + h * math.sin(phi1)
        for i in range(seg):
            a0 = 2 * math.pi * i / seg
            a1 = 2 * math.pi * (i + 1) / seg
            p00 = (cx + r0 * math.cos(a0), yy0, cz + r0 * math.sin(a0))
            p10 = (cx + r0 * math.cos(a1), yy0, cz + r0 * math.sin(a1))
            p11 = (cx + r1 * math.cos(a1), yy1, cz + r1 * math.sin(a1))
            p01 = (cx + r1 * math.cos(a0), yy1, cz + r1 * math.sin(a0))
            if ri == rings - 1:
                poly(acc, [p00, p10, (cx, y_base + h, cz)], m)
                poly(acc, [(cx, y_base + h, cz), p10, p00], m_in)
            else:
                poly(acc, [p00, p10, p11, p01], m)
                poly(acc, [p01, p11, p10, p00], m_in)


# ================================================================ 建筑墙体、门窗、墙裙

def _window_x(acc, col, ox0, ox1, oy0, oy1, z, thick, glass_key='glass'):
    frame = L.mat('frame')
    sill = L.mat('concrete')
    glass = L.mat(glass_key)
    # 窗台挑板
    box(acc, ox0 - 0.04, oy0 - 0.06, z - thick / 2 - 0.05, ox1 + 0.04, oy0, z + thick / 2 + 0.05, sill)
    # 玻璃与外框
    box(acc, ox0, oy0, z - 0.015, ox1, oy1, z + 0.015, glass)
    box(acc, ox0, oy0, z - 0.065, ox1, oy0 + 0.055, z + 0.065, frame)
    box(acc, ox0, oy1 - 0.055, z - 0.065, ox1, oy1, z + 0.065, frame)
    n_mul = max(1, int(round((ox1 - ox0) / 1.15)))
    for k in range(n_mul + 1):
        mx = ox0 + (ox1 - ox0) * k / n_mul
        box(acc, mx - 0.032, oy0, z - 0.055, mx + 0.032, oy1, z + 0.055, frame)
    if oy1 - oy0 > 1.45:
        my = oy0 + (oy1 - oy0) * 0.68
        box(acc, ox0, my - 0.028, z - 0.05, ox1, my + 0.028, z + 0.05, frame)
    if col is not None:
        box(col, ox0, oy0, z - thick / 2, ox1, oy1, z + thick / 2, L.mat('collision'))


def _window_z(acc, col, oz0, oz1, oy0, oy1, x, thick, glass_key='glass'):
    frame = L.mat('frame')
    sill = L.mat('concrete')
    glass = L.mat(glass_key)
    box(acc, x - thick / 2 - 0.05, oy0 - 0.06, oz0 - 0.04, x + thick / 2 + 0.05, oy0, oz1 + 0.04, sill)
    box(acc, x - 0.015, oy0, oz0, x + 0.015, oy1, oz1, glass)
    box(acc, x - 0.065, oy0, oz0, x + 0.065, oy0 + 0.055, oz1, frame)
    box(acc, x - 0.065, oy1 - 0.055, oz0, x + 0.065, oy1, oz1, frame)
    n_mul = max(1, int(round((oz1 - oz0) / 1.15)))
    for k in range(n_mul + 1):
        mz = oz0 + (oz1 - oz0) * k / n_mul
        box(acc, x - 0.055, oy0, mz - 0.032, x + 0.055, oy1, mz + 0.032, frame)
    if oy1 - oy0 > 1.45:
        my = oy0 + (oy1 - oy0) * 0.68
        box(acc, x - 0.05, my - 0.028, oz0, x + 0.05, my + 0.028, oz1, frame)
    if col is not None:
        box(col, x - thick / 2, oy0, oz0, x + thick / 2, oy1, oz1, L.mat('collision'))


def _door_frame_x(acc, ox0, ox1, oy0, oy1, z0, z1, kind='door'):
    frame = L.mat('frame')
    wood = L.mat('wood')
    dark = L.mat('metal_dark')
    box(acc, ox0, oy0, z0 - 0.015, ox0 + 0.06, oy1, z1 + 0.015, frame)
    box(acc, ox1 - 0.06, oy0, z0 - 0.015, ox1, oy1, z1 + 0.015, frame)
    box(acc, ox0, oy1 - 0.06, z0 - 0.015, ox1, oy1, z1 + 0.015, frame)
    if kind == 'door_leaf_open':
        # 向室内微开的木门扇（带后门观察小玻璃窗），不挡走道且房间视觉完整
        w = min(0.92, (ox1 - ox0) - 0.12)
        zc = (z0 + z1) / 2
        box(acc, ox0 + 0.06, oy0 + 0.02, zc - w, ox0 + 0.11, oy1 - 0.07, zc, wood)
        box(acc, ox0 + 0.055, oy0 + 1.25, zc - w * 0.68, ox0 + 0.115, oy0 + 1.85, zc - w * 0.28, L.mat('glass'))
    elif kind == 'stair_gate':
        # 23:00 楼梯口铁格栅门框（平时向侧壁敞开贴靠）
        box(acc, ox0 + 0.06, oy0 + 0.05, z0 - 0.02, ox0 + 0.12, oy1 - 0.06, z1 + 0.02, dark)


def _door_frame_z(acc, col, oz0, oz1, oy0, oy1, x0, x1, kind='door'):
    frame = L.mat('frame')
    dark = L.mat('metal_dark')
    metal = L.mat('metal')
    box(acc, x0 - 0.015, oy0, oz0, x1 + 0.015, oy1, oz0 + 0.06, frame)
    box(acc, x0 - 0.015, oy0, oz1 - 0.06, x1 + 0.015, oy1, oz1, frame)
    box(acc, x0 - 0.015, oy1 - 0.06, oz0, x1 + 0.015, oy1, oz1, frame)
    if kind == 'small_lab_door':
        # 小机房专属铁门：下半关死铁门 + 内侧压柄把手 + 上方防盗网格气窗（承接物理开锁玩法 LV-08！）
        xc = (x0 + x1) / 2
        ym = oy1 - 0.48
        box(acc, xc - 0.025, oy0, oz0 + 0.06, xc + 0.025, ym, oz1 - 0.06, metal)
        box(acc, xc - 0.035, ym - 0.05, oz0 + 0.06, xc + 0.035, ym, oz1 - 0.06, dark)
        # 门内侧压柄把手
        box(acc, xc - 0.10, oy0 + 1.02, oz1 - 0.22, xc - 0.025, oy0 + 1.06, oz1 - 0.18, dark)
        box(acc, xc - 0.10, oy0 + 1.02, oz1 - 0.34, xc - 0.08, oy0 + 1.05, oz1 - 0.18, dark)
        # 门上方防盗网格气窗
        for k in range(1, 5):
            zz = oz0 + 0.06 + (oz1 - oz0 - 0.12) * k / 5
            box(acc, xc - 0.012, ym, zz - 0.01, xc + 0.012, oy1 - 0.06, zz + 0.01, dark)
        box(acc, xc - 0.012, (ym + oy1 - 0.06) / 2 - 0.01, oz0 + 0.06, xc + 0.012, (ym + oy1 - 0.06) / 2 + 0.01, oz1 - 0.06, dark)
        if col is not None:
            box(col, x0, oy0, oz0, x1, oy1, oz1, L.mat('collision'))
    elif kind == 'closed_door':
        # 保留门扇外观但常闭不可进入（如萃华楼 3F 圆塔南侧封闭房间门）
        xc = (x0 + x1) / 2
        box(acc, xc - 0.025, oy0, oz0 + 0.06, xc + 0.025, oy1 - 0.06, oz1 - 0.06, L.mat('wood'))
        box(acc, xc + 0.025, oy0 + 1.0, oz1 - 0.22, xc + 0.07, oy0 + 1.05, oz1 - 0.16, dark)
        if col is not None:
            box(col, x0, oy0, oz0, x1, oy1, oz1, L.mat('collision'))


def wall_x(acc, col, x0, x1, z, y0, y1, thick=0.24, mat_key='facade', openings=(), dado=False):
    """沿 X 方向的闭合墙（两端外延 half_thick 消除转角缝隙）。
    openings: [(ox0, ox1, oy0, oy1, kind), ...]
    dado=True 时自动刷 1.05 m 高浅蓝墙裙。"""
    m = L.mat(mat_key)
    cm = L.mat('collision')
    z0, z1 = z - thick / 2, z + thick / 2
    ops = sorted(openings, key=lambda o: o[0])
    cur = x0

    def _solid_seg(sx0, sx1, sy0, sy1):
        if sx1 - sx0 <= 0.005 or sy1 - sy0 <= 0.005:
            return
        ym = y0 + 1.05
        if dado and sy0 < ym:
            top_d = min(sy1, ym)
            box(acc, sx0, sy0, z0, sx1, top_d, z1, L.mat('dado_blue'))
            if sy1 > ym + 0.005:
                box(acc, sx0, ym, z0, sx1, sy1, z1, m)
        else:
            box(acc, sx0, sy0, z0, sx1, sy1, z1, m)
        if col is not None:
            box(col, sx0, sy0, z0, sx1, sy1, z1, cm)

    for ox0, ox1, oy0, oy1, kind in ops:
        ox0, ox1 = max(cur, ox0), min(x1, ox1)
        if ox0 > cur + 0.005:
            _solid_seg(cur, ox0, y0, y1)
        if ox1 > ox0 + 0.005:
            if oy0 > y0 + 0.005:
                _solid_seg(ox0, ox1, y0, oy0)
            if oy1 < y1 - 0.005:
                _solid_seg(ox0, ox1, oy1, y1)
            if kind == 'window':
                _window_x(acc, col, ox0, ox1, oy0, oy1, z, thick, 'glass')
            elif kind == 'glass_wall':
                _window_x(acc, col, ox0, ox1, oy0, oy1, z, thick, 'glass_blue')
            elif kind in ('door', 'door_leaf_open', 'stair_gate'):
                _door_frame_x(acc, ox0, ox1, oy0, oy1, z0, z1, kind)
        cur = max(cur, ox1)
    if cur < x1 - 0.005:
        _solid_seg(cur, x1, y0, y1)


def wall_z(acc, col, z0, z1, x, y0, y1, thick=0.24, mat_key='facade', openings=(), dado=False):
    """沿 Z 方向的闭合墙。"""
    m = L.mat(mat_key)
    cm = L.mat('collision')
    x0, x1 = x - thick / 2, x + thick / 2
    ops = sorted(openings, key=lambda o: o[0])
    cur = z0

    def _solid_seg(sz0, sz1, sy0, sy1):
        if sz1 - sz0 <= 0.005 or sy1 - sy0 <= 0.005:
            return
        ym = y0 + 1.05
        if dado and sy0 < ym:
            top_d = min(sy1, ym)
            box(acc, x0, sy0, sz0, x1, top_d, sz1, L.mat('dado_blue'))
            if sy1 > ym + 0.005:
                box(acc, x0, ym, sz0, x1, sy1, sz1, m)
        else:
            box(acc, x0, sy0, sz0, x1, sy1, sz1, m)
        if col is not None:
            box(col, x0, sy0, sz0, x1, sy1, sz1, cm)

    for oz0, oz1, oy0, oy1, kind in ops:
        oz0, oz1 = max(cur, oz0), min(z1, oz1)
        if oz0 > cur + 0.005:
            _solid_seg(cur, oz0, y0, y1)
        if oz1 > oz0 + 0.005:
            if oy0 > y0 + 0.005:
                _solid_seg(oz0, oz1, y0, oy0)
            if oy1 < y1 - 0.005:
                _solid_seg(oz0, oz1, oy1, y1)
            if kind == 'window':
                _window_z(acc, col, oz0, oz1, oy0, oy1, x, thick, 'glass')
            elif kind == 'glass_wall':
                _window_z(acc, col, oz0, oz1, oy0, oy1, x, thick, 'glass_blue')
            elif kind in ('door', 'small_lab_door', 'closed_door'):
                _door_frame_z(acc, col, oz0, oz1, oy0, oy1, x0, x1, kind)
        cur = max(cur, oz1)
    if cur < z1 - 0.005:
        _solid_seg(cur, z1, y0, y1)


def railing_x(acc, col, x0, x1, z, y0, h=1.06, glass_panel=True):
    """沿 X 方向外廊栏杆（还原原版白色反坎 + 金属扶手 + 玻璃护栏板）。"""
    if x1 - x0 <= 0.05:
        return
    box(acc, x0, y0, z - 0.09, x1, y0 + 0.18, z + 0.09, L.mat('facade'))
    box(acc, x0, y0 + h - 0.05, z - 0.045, x1, y0 + h, z + 0.045, L.mat('metal_dark'))
    if glass_panel:
        box(acc, x0 + 0.04, y0 + 0.18, z - 0.012, x1 - 0.04, y0 + h - 0.06, z + 0.012, L.mat('glass'))
    else:
        box(acc, x0, y0 + h * 0.54, z - 0.025, x1, y0 + h * 0.54 + 0.03, z + 0.025, L.mat('metal'))
    n = max(1, int(round((x1 - x0) / 1.4)))
    for k in range(n + 1):
        xx = x0 + (x1 - x0) * k / n
        box(acc, xx - 0.03, y0 + 0.18, z - 0.03, xx + 0.03, y0 + h - 0.05, z + 0.03, L.mat('metal_dark'))
    if col is not None:
        box(col, x0, y0, z - 0.09, x1, y0 + h, z + 0.09, L.mat('collision'))


def railing_z(acc, col, z0, z1, x, y0, h=1.06, glass_panel=True):
    if z1 - z0 <= 0.05:
        return
    box(acc, x - 0.09, y0, z0, x + 0.09, y0 + 0.18, z1, L.mat('facade'))
    box(acc, x - 0.045, y0 + h - 0.05, z0, x + 0.045, y0 + h, z1, L.mat('metal_dark'))
    if glass_panel:
        box(acc, x - 0.012, y0 + 0.18, z0 + 0.04, x + 0.012, y0 + h - 0.06, z1 - 0.04, L.mat('glass'))
    n = max(1, int(round((z1 - z0) / 1.4)))
    for k in range(n + 1):
        zz = z0 + (z1 - z0) * k / n
        box(acc, x - 0.03, y0 + 0.18, zz - 0.03, x + 0.03, y0 + h - 0.05, zz + 0.03, L.mat('metal_dark'))
    if col is not None:
        box(col, x - 0.09, y0, z0, x + 0.09, y0 + h, z1, L.mat('collision'))


# ================================================================ 零错位楼梯系统（还原原版楼梯设计特点）

def build_stair_flights(acc, col, x0, x1, z_entry, z_far, y_base, n_floors, floor_h, slab_t=0.22):
    """零缝隙双跑折返楼梯（含每层入口平台、半层休息平台、现浇斜底板踏步、顶层井道护栏）。
    z_entry: 与走廊衔接边（各层走廊楼板止于 z_entry，本函数负责 z_entry → z_far 区间内的全部平台与踏步！）
    z_far: 楼梯间远端内壁。
    """
    sgn = 1.0 if z_far > z_entry else -1.0
    depth = abs(z_far - z_entry)
    entry_d = min(1.22, depth * 0.27)
    land_d = min(1.22, depth * 0.27)
    run_d = depth - entry_d - land_d
    z_l1 = z_entry + sgn * entry_d
    z_l2 = z_l1 + sgn * run_d

    xm = (x0 + x1) / 2
    gap = 0.08
    ax0, ax1 = x0 + 0.02, xm - gap      # 第一跑（西侧：上行离开入口）
    bx0, bx1 = xm + gap, x1 - 0.02      # 第二跑（东侧：折返上行回到上层入口平台）

    m_step = L.mat('floor')
    m_side = L.mat('concrete')
    m_ceil = L.mat('ceiling_white')
    m_rail = L.mat('metal_dark')
    cm = L.mat('collision')

    for fl in range(n_floors):
        yf = y_base + fl * floor_h
        # 1) 本层入口平台（z_entry .. z_l1），与走廊楼板零缝隙齐平
        ez0, ez1 = min(z_entry, z_l1), max(z_entry, z_l1)
        if fl == 0:
            box(acc, x0, yf - 0.02, min(z_entry, z_far), x1, yf, max(z_entry, z_far), m_step, skip=('-y',))
            if col is not None:
                box(col, x0, yf - 0.25, min(z_entry, z_far), x1, yf, max(z_entry, z_far), cm)
        else:
            slab_with_ceiling(acc, col, x0, ez0, x1, ez1, yf - slab_t, yf, 'floor', 'concrete', add_col=True)

        if fl < n_floors - 1:
            ym = yf + floor_h / 2
            yt = yf + floor_h
            # 2) 远端半层休息平台（z_l2 .. z_far）
            lz0, lz1 = min(z_l2, z_far), max(z_l2, z_far)
            slab_with_ceiling(acc, col, x0, lz0, x1, lz1, ym - 0.20, ym, 'floor', 'concrete', add_col=True)

            # 3) 第一跑（ax0..ax1，z_l1 -> z_l2，yf -> ym）与第二跑（bx0..bx1，z_l2 -> z_l1，ym -> yt）
            for (sx0, sx1, za, zb, ya, yb) in (
                (ax0, ax1, z_l1, z_l2, yf, ym),
                (bx0, bx1, z_l2, z_l1, ym, yt),
            ):
                steps = 9
                for i in range(steps):
                    t0, t1 = i / steps, (i + 1) / steps
                    zz0 = za + (zb - za) * t0
                    zz1 = za + (zb - za) * t1
                    y_step_bot = ya + (yb - ya) * t0
                    y_step_top = ya + (yb - ya) * t1
                    box(acc, sx0, y_step_bot, min(zz0, zz1), sx1, y_step_top, max(zz0, zz1), m_step)
                # 连续现浇斜底板（消除悬空台阶锯齿，仰视干净）
                d_soffit = 0.18
                p_b0 = (sx0, ya - d_soffit, za)
                p_b1 = (sx1, ya - d_soffit, za)
                p_t1 = (sx1, yb - d_soffit, zb)
                p_t0 = (sx0, yb - d_soffit, zb)
                poly(acc, [p_b0, p_b1, p_t1, p_t0], m_ceil)
                poly(acc, [p_t0, p_t1, p_b1, p_b0], m_ceil)
                # 两侧斜挡板闭合三角形缝隙
                for xx in (sx0, sx1):
                    poly(acc, [(xx, ya, za), (xx, yb, zb), (xx, yb - d_soffit, zb), (xx, ya - d_soffit, za)], m_side)
                    poly(acc, [(xx, ya - d_soffit, za), (xx, yb - d_soffit, zb), (xx, yb, zb), (xx, ya, za)], m_side)
                # 平滑斜坡碰撞
                if col is not None:
                    c0 = (sx0, ya, za)
                    c1 = (sx1, ya, za)
                    c2 = (sx1, yb, zb)
                    c3 = (sx0, yb, zb)
                    poly(col, [c0, c1, c2, c3], cm)
                    poly(col, [c3, c2, c1, c0], cm)
                # 临井道侧斜向金属扶手 + 栏杆立柱
                rx = sx1 - 0.03 if sx0 == ax0 else sx0 + 0.03
                poly(acc, [(rx, ya + 0.90, za), (rx, yb + 0.90, zb), (rx, yb + 0.96, zb), (rx, ya + 0.96, za)], m_rail)
                poly(acc, [(rx, ya + 0.96, za), (rx, yb + 0.96, zb), (rx, yb + 0.90, zb), (rx, ya + 0.90, za)], m_rail)
                for k in (1, 4, 8):
                    tk = k / steps
                    zk = za + (zb - za) * tk
                    yk = ya + (yb - ya) * tk
                    box(acc, rx - 0.02, yk, zk - 0.02, rx + 0.02, yk + 0.92, zk + 0.02, m_rail)
            # 半层休息平台井道横栏杆
            railing_x(acc, None, ax1 - 0.04, bx0 + 0.04, z_l2, ym, h=0.95, glass_panel=False)
        else:
            # 顶层没有继续向上的第一跑，在西半开口边（z_l1）加护栏防跌落！
            railing_x(acc, col, ax0, xm + 0.04, z_l1, yf, h=1.02, glass_panel=True)


def build_stair_flights_x(acc, col, z0, z1, x_entry, x_far, y_base, n_floors, floor_h, slab_t=0.22,
                          first_side='south', sub_half=False):
    """东西朝向（沿 X 轴上下行）的零缝隙双跑折返楼梯，支持半层休息平台开门进半层错层厕所（如萃华楼 -0.5F / 1.5F / 2.5F）！
    x_entry: 走廊入口侧；x_far: 远端半层休息平台外侧（|x_far - x_entry| >= 4.4 m）。
    first_side: 'south' 表示南半跑（zm..z1）先从 x_entry 上行至 x_far 半层平台，北半跑折返上行回 x_entry；'north' 反之。
    sub_half=True 时额外从 1F 入口平台沿返程侧向下设半跑到 y_base - floor_h/2 的 -0.5F 半层平台！
    """
    sgn = 1.0 if x_far > x_entry else -1.0
    depth = abs(x_far - x_entry)
    entry_d = 1.15
    land_d = 1.15
    run_d = depth - entry_d - land_d
    x_l1 = x_entry + sgn * entry_d
    x_l2 = x_l1 + sgn * run_d

    zm = (z0 + z1) / 2
    gap = 0.08
    if first_side == 'south':
        az0, az1 = zm + gap, z1 - 0.02   # 第一跑（上行去 x_far）
        bz0, bz1 = z0 + 0.02, zm - gap   # 第二跑（从 x_far 折返上行回 x_entry；sub_half 时 1F 此侧下往 -0.5F）
    else:
        az0, az1 = z0 + 0.02, zm - gap
        bz0, bz1 = zm + gap, z1 - 0.02

    m_step = L.mat('floor')
    m_side = L.mat('concrete')
    m_ceil = L.mat('ceiling_white')
    m_rail = L.mat('metal_dark')
    cm = L.mat('collision')

    def _flight_x(sz0, sz1, xa, xb, ya, yb):
        steps = 9
        for i in range(steps):
            t0, t1 = i / steps, (i + 1) / steps
            xx0 = xa + (xb - xa) * t0
            xx1 = xa + (xb - xa) * t1
            ys0 = ya + (yb - ya) * t0
            ys1 = ya + (yb - ya) * t1
            box(acc, min(xx0, xx1), min(ys0, ys1) - (0.14 if yb < ya else 0.0), sz0,
                max(xx0, xx1), max(ys0, ys1), sz1, m_step)
        d_soffit = 0.18
        p_b0 = (xa, ya - d_soffit, sz0)
        p_b1 = (xa, ya - d_soffit, sz1)
        p_t1 = (xb, yb - d_soffit, sz1)
        p_t0 = (xb, yb - d_soffit, sz0)
        poly(acc, [p_b0, p_b1, p_t1, p_t0], m_ceil)
        poly(acc, [p_t0, p_t1, p_b1, p_b0], m_ceil)
        for zz in (sz0, sz1):
            poly(acc, [(xa, ya, zz), (xb, yb, zz), (xb, yb - d_soffit, zz), (xa, ya - d_soffit, zz)], m_side)
            poly(acc, [(xa, ya - d_soffit, zz), (xb, yb - d_soffit, zz), (xb, yb, zz), (xa, ya, zz)], m_side)
        if col is not None:
            c0, c1, c2, c3 = (xa, ya, sz0), (xa, ya, sz1), (xb, yb, sz1), (xb, yb, sz0)
            poly(col, [c0, c1, c2, c3], cm)
            poly(col, [c3, c2, c1, c0], cm)
        rz = sz0 + 0.03 if sz0 > zm else sz1 - 0.03
        poly(acc, [(xa, ya + 0.90, rz), (xb, yb + 0.90, rz), (xb, yb + 0.96, rz), (xa, ya + 0.96, rz)], m_rail)
        poly(acc, [(xa, ya + 0.96, rz), (xb, yb + 0.96, rz), (xb, yb + 0.90, rz), (xa, ya + 0.90, rz)], m_rail)
        for k in (1, 4, 8):
            tk = k / steps
            xk = xa + (xb - xa) * tk
            yk = ya + (yb - ya) * tk
            box(acc, xk - 0.02, yk, rz - 0.02, xk + 0.02, yk + 0.92, rz + 0.02, m_rail)

    # 若含 -0.5F 半层下沉楼梯（1F 沿 bz0..bz1 从 x_l1 下到 x_l2 的 y_sub 平台）
    if sub_half:
        y_sub = y_base - floor_h / 2
        ex0, ex1 = min(x_entry, x_l1), max(x_entry, x_l1)
        slab_with_ceiling(acc, col, ex0, z0, ex1, z1, y_base - slab_t, y_base, 'floor', 'concrete', add_col=True)
        # 第一跑（az0..az1）底下的实心基底
        rx0, rx1 = min(x_l1, x_far), max(x_l1, x_far)
        box(acc, rx0, y_sub - 0.25, az0 - 0.08, rx1, y_base, az1 + 0.02, m_side)
        if col is not None:
            box(col, rx0, y_sub - 0.25, az0 - 0.08, rx1, y_base, az1 + 0.02, cm)
        # -0.5F 半层休息平台（x_l2..x_far, bz0..bz1）与下沉跑段
        lx0, lx1 = min(x_l2, x_far), max(x_l2, x_far)
        box(acc, lx0, y_sub - 0.25, z0, lx1, y_sub, bz1 + 0.08, m_step)
        if col is not None:
            box(col, lx0, y_sub - 0.25, z0, lx1, y_sub, bz1 + 0.08, cm)
        _flight_x(bz0, bz1, x_l1, x_l2, y_base, y_sub)

    for fl in range(n_floors):
        yf = y_base + fl * floor_h
        ex0, ex1 = min(x_entry, x_l1), max(x_entry, x_l1)
        if fl == 0 and not sub_half:
            box(acc, min(x_entry, x_far), yf - 0.02, z0, max(x_entry, x_far), yf, z1, m_step, skip=('-y',))
            if col is not None:
                box(col, min(x_entry, x_far), yf - 0.25, z0, max(x_entry, x_far), yf, z1, cm)
        elif fl > 0:
            slab_with_ceiling(acc, col, ex0, z0, ex1, z1, yf - slab_t, yf, 'floor', 'concrete', add_col=True)

        if fl < n_floors - 1:
            ym = yf + floor_h / 2
            yt = yf + floor_h
            lx0, lx1 = min(x_l2, x_far), max(x_l2, x_far)
            slab_with_ceiling(acc, col, lx0, z0, lx1, z1, ym - 0.20, ym, 'floor', 'concrete', add_col=True)
            _flight_x(az0, az1, x_l1, x_l2, yf, ym)
            _flight_x(bz0, bz1, x_l2, x_l1, ym, yt)
            # 仅在两跑之间的中央井道窄缝（zm-gap .. zm+gap）加短横栏，绝不横挡踏步通道！
            railing_z(acc, None, zm - gap - 0.04, zm + gap + 0.04, x_l2, ym, h=0.95, glass_panel=False)
        else:
            railing_z(acc, col, az0, az1, x_l1, yf, h=1.02, glass_panel=True)


def glass_stair_box_east(acc, col, x_junc, x_east, z0, z1, y_base, n_floors, floor_h):
    """朝外三面（北、东、南）全玻璃幕墙的东端楼梯间外罩（消除层间空隙与主体交接缝隙！）：
    - 从 y_base 连续通高至 y_roof，不留任何层间 0.22m 缝隙；
    - 西端嵌入主体 x_junc - 0.16，与教学楼/萃华楼主体零缝隙咬合；
    - 三面朝外墙体采用整幅通高蓝玻璃幕墙 + 纤细金属立梃横档 + 转角白柱 + 完整封闭顶盖。
    """
    facade = L.mat('facade')
    concrete = L.mat('concrete')
    glass_b = L.mat('glass_blue')
    frame = L.mat('frame')
    roof_m = L.mat('roof')
    cm = L.mat('collision')

    yr_main = y_base + n_floors * floor_h
    y_roof = yr_main + 0.48

    # 底座台基（向西咬合 0.20 m）
    box(acc, x_junc - 0.20, 0.0, z0 - 0.16, x_east + 0.16, y_base, z1 + 0.16, concrete)
    if col is not None:
        box(col, x_junc - 0.20, 0.0, z0 - 0.16, x_east + 0.16, y_base, z1 + 0.16, cm)

    # 四角通高立柱（西侧两根立柱嵌进主体 x_junc 消除竖向拼接缝！）
    for cx in (x_junc, x_east - 0.12):
        for cz in (z0 + 0.12, z1 - 0.12):
            box(acc, cx - 0.14, y_base, cz - 0.14, cx + 0.14, y_roof, cz + 0.14, facade)
            if col is not None:
                box(col, cx - 0.14, y_base, cz - 0.14, cx + 0.14, y_roof, cz + 0.14, cm)

    # 底部矮踢脚坎（0.25 .. 0.42）与顶部檐口梁（yr_main - 0.22 .. y_roof），包括西侧高差封口梁！
    for zz in (z0 + 0.10, z1 - 0.10):
        box(acc, x_junc - 0.14, y_base, zz - 0.12, x_east + 0.02, y_base + 0.18, zz + 0.12, facade)
        box(acc, x_junc - 0.14, yr_main - 0.22, zz - 0.12, x_east + 0.02, y_roof, zz + 0.12, facade)
    box(acc, x_east - 0.22, y_base, z0, x_east + 0.02, y_base + 0.18, z1, facade)
    box(acc, x_east - 0.22, yr_main - 0.22, z0, x_east + 0.02, y_roof, z1, facade)
    # 西侧屋面高差封口实梁（封闭主体屋顶 yr_main - 0.22 到楼梯间顶 y_roof 的高差，绝不漏天！）
    box(acc, x_junc - 0.14, yr_main - 0.24, z0, x_junc + 0.14, y_roof, z1, facade)

    # 北、南、东三面整幅连续通高玻璃幕墙（y_base + 0.18 .. yr_main - 0.22，零层间空隙！）
    gy0, gy1 = y_base + 0.18, yr_main - 0.22
    gx0, gx1 = x_junc + 0.12, x_east - 0.24
    gz0, gz1 = z0 + 0.24, z1 - 0.24

    for zz in (z0 + 0.08, z1 - 0.08):
        box(acc, gx0, gy0, zz - 0.02, gx1, gy1, zz + 0.02, glass_b)
        if col is not None:
            box(col, x_junc, y_base, zz - 0.10, x_east, y_roof, zz + 0.10, cm)
        n_mx = max(2, int(round((gx1 - gx0) / 1.25)))
        for k in range(n_mx + 1):
            mx = gx0 + (gx1 - gx0) * k / n_mx
            box(acc, mx - 0.03, gy0, zz - 0.055, mx + 0.03, gy1, zz + 0.055, frame)

    ex = x_east - 0.08
    box(acc, ex - 0.02, gy0, gz0, ex + 0.02, gy1, gz1, glass_b)
    if col is not None:
        box(col, ex - 0.10, y_base, z0, x_east, y_roof, z1, cm)
    n_mz = max(2, int(round((gz1 - gz0) / 1.20)))
    for k in range(n_mz + 1):
        mz = gz0 + (gz1 - gz0) * k / n_mz
        box(acc, ex - 0.055, gy0, mz - 0.03, ex + 0.055, gy1, mz + 0.03, frame)

    # 每层与半层处的连续金属横梃（紧贴玻璃幕墙内外，既分格美观又无任何穿透缝隙）
    for fl in range(1, n_floors * 2):
        hy = y_base + fl * (floor_h * 0.5)
        if gy0 + 0.2 < hy < gy1 - 0.2:
            for zz in (z0 + 0.08, z1 - 0.08):
                box(acc, gx0, hy - 0.035, zz - 0.06, gx1, hy + 0.035, zz + 0.06, frame)
            box(acc, ex - 0.06, hy - 0.035, gz0, ex + 0.06, hy + 0.035, gz1, frame)

    # 封闭顶盖（带白色平顶天花板）
    slab_with_ceiling(acc, col, x_junc - 0.14, z0 - 0.06, x_east + 0.06, z1 + 0.06,
                      y_roof - 0.22, y_roof, 'roof', 'concrete', add_col=True)
    box(acc, x_junc - 0.18, y_roof, z0 - 0.10, x_east + 0.10, y_roof + 0.18, z1 + 0.10, concrete)


def add_turnstiles(acc, col, x_left, x_right, z_center, y0=0.0):
    """在人行侧门通道放置两组刷卡翼闸通道（3 台不锈钢闸机机箱夹出 2 条可过人刷卡通道）。"""
    width = x_right - x_left
    ped_w = 0.24
    # 3 台闸机均匀夹出 2 个标准刷卡过道
    xs = [x_left + 0.18, (x_left + x_right) / 2, x_right - 0.18]
    m_body = L.mat('metal')
    m_top = L.mat('metal_dark')
    m_card = L.mat('glass_blue')
    m_wing = L.mat('red_sign')
    cm = L.mat('collision')
    for cx in xs:
        box(acc, cx - ped_w / 2, y0, z_center - 0.65, cx + ped_w / 2, y0 + 0.96, z_center + 0.65, m_body)
        box(acc, cx - ped_w / 2 - 0.01, y0 + 0.96, z_center - 0.66, cx + ped_w / 2 + 0.01, y0 + 1.02, z_center + 0.66, m_top)
        # 刷卡感应面板
        box(acc, cx - 0.08, y0 + 1.02, z_center + 0.35, cx + 0.08, y0 + 1.04, z_center + 0.55, m_card)
        box(acc, cx - 0.08, y0 + 1.02, z_center - 0.55, cx + 0.08, y0 + 1.04, z_center - 0.35, m_card)
        if col is not None:
            box(col, cx - ped_w / 2, y0, z_center - 0.65, cx + ped_w / 2, y0 + 1.02, z_center + 0.65, cm)
    # 两侧通道内的半透明红色亚克力挡翼（微缩留出过人宽度，不卡角色碰撞）
    for lane_cx in ((xs[0] + xs[1]) / 2, (xs[1] + xs[2]) / 2):
        gap_half = (xs[1] - xs[0] - ped_w) / 2
        box(acc, lane_cx - gap_half, y0 + 0.25, z_center - 0.03, lane_cx - 0.18, y0 + 0.85, z_center + 0.03, m_wing)
        box(acc, lane_cx + 0.18, y0 + 0.25, z_center - 0.03, lane_cx + gap_half, y0 + 0.85, z_center + 0.03, m_wing)


def add_chain_shutter_x(acc, col, x0, x1, z, y0, y1, clear_h=1.88):
    """沿 X 方向的【半升起、两侧无导轨、镂空铁链网孔式卷帘门】（连接片网状卷闸门）：
    - 两侧不设导轨槽，保持门洞柱面/墙垛干净；
    - 顶部设金属卷轴筒，下方半升起垂下一段由横向穿芯细圆杆 + 奇偶错缝双股链扣片组成的真实镂空铁链网帘（中间全部真透孔）；
    - 底边停在 y0 + clear_h（约 1.88 m），既一目了然看到镂空链条卷帘门，又不阻挡角色进出。
    """
    m_rod = L.mat('metal')
    m_dark = L.mat('metal_dark')
    y_roll_bot = y1 - 0.16
    y_bot = min(y_roll_bot - 0.52, y0 + clear_h)

    # 顶部卷帘横筒（缠绕收起的链帘卷筒，无两侧导轨！）
    box(acc, x0, y_roll_bot, z - 0.075, x1, y1, z + 0.075, m_dark)
    box(acc, x0 + 0.02, y_roll_bot + 0.02, z - 0.085, x1 - 0.02, y1 - 0.02, z + 0.085, m_rod)

    # 底梁扁钢与中央锁扣鼻
    bar_h = 0.038
    box(acc, x0 + 0.01, y_bot, z - 0.022, x1 - 0.01, y_bot + bar_h, z + 0.022, m_dark)
    xm = (x0 + x1) / 2
    box(acc, xm - 0.04, y_bot - 0.032, z - 0.026, xm + 0.04, y_bot + 0.01, z + 0.026, m_dark)

    # 镂空铁链网帘主体：横向穿杆 + 奇偶行交错双股铁链扣（真实透孔网格！）
    y_start = y_bot + bar_h
    span_h = y_roll_bot - y_start
    n_rows = max(4, int(round(span_h / 0.095)))
    row_h = span_h / n_rows
    pitch = 0.155

    for r in range(n_rows + 1):
        yr = y_start + r * row_h
        box(acc, x0 + 0.01, yr - 0.008, z - 0.009, x1 - 0.01, yr + 0.008, z + 0.009, m_rod)
        if r < n_rows:
            offset = (pitch * 0.5) if (r % 2 == 1) else 0.0
            xx = x0 + 0.06 + offset
            while xx < x1 - 0.05:
                # 双股链环竖扣（夹出链环质感，左右与相邻链扣之间留出约 12cm 宽真透孔！）
                for dx in (-0.015, 0.015):
                    box(acc, xx + dx - 0.006, yr + 0.006, z - 0.013,
                        xx + dx + 0.006, yr + row_h - 0.006, z + 0.013, m_rod)
                # 链环上下包头暗扣
                box(acc, xx - 0.024, yr - 0.011, z - 0.015, xx + 0.024, yr + 0.014, z + 0.015, m_dark)
                xx += pitch

    if col is not None:
        box(col, x0, y_bot, z - 0.06, x1, y1, z + 0.06, L.mat('collision'))


def add_chain_shutter_z(acc, col, z0, z1, x, y0, y1, clear_h=1.88):
    """沿 Z 方向的【半升起、两侧无导轨、镂空铁链网孔式卷帘门】。"""
    m_rod = L.mat('metal')
    m_dark = L.mat('metal_dark')
    y_roll_bot = y1 - 0.16
    y_bot = min(y_roll_bot - 0.52, y0 + clear_h)

    box(acc, x - 0.075, y_roll_bot, z0, x + 0.075, y1, z1, m_dark)
    box(acc, x - 0.085, y_roll_bot + 0.02, z0 + 0.02, x + 0.085, y1 - 0.02, z1 - 0.02, m_rod)

    bar_h = 0.038
    box(acc, x - 0.022, y_bot, z0 + 0.01, x + 0.022, y_bot + bar_h, z1 - 0.01, m_dark)
    zm = (z0 + z1) / 2
    box(acc, x - 0.026, y_bot - 0.032, zm - 0.04, x + 0.026, y_bot + 0.01, zm + 0.04, m_dark)

    y_start = y_bot + bar_h
    span_h = y_roll_bot - y_start
    n_rows = max(4, int(round(span_h / 0.095)))
    row_h = span_h / n_rows
    pitch = 0.155

    for r in range(n_rows + 1):
        yr = y_start + r * row_h
        box(acc, x - 0.009, yr - 0.008, z0 + 0.01, x + 0.009, yr + 0.008, z1 - 0.01, m_rod)
        if r < n_rows:
            offset = (pitch * 0.5) if (r % 2 == 1) else 0.0
            zz = z0 + 0.06 + offset
            while zz < z1 - 0.05:
                for dz in (-0.015, 0.015):
                    box(acc, x - 0.013, yr + 0.006, zz + dz - 0.006,
                        x + 0.013, yr + row_h - 0.006, zz + dz + 0.006, m_rod)
                box(acc, x - 0.015, yr - 0.011, zz - 0.024, x + 0.015, yr + 0.014, zz + 0.024, m_dark)
                zz += pitch

    if col is not None:
        box(col, x - 0.06, y_bot, z0, x + 0.06, y1, z1, L.mat('collision'))


def gaosan_south_stair_tower(acc, col, x0, x1, z_corr_s, z_out_s, y_base, n_floors, floor_h, open_west_1f=False):
    """高三楼原版标志性【南向凸出白腰带 + 三面转角玻璃窗楼梯塔】（精确还原 ref_gaosan_s.png）：
    - 从南外廊外沿 z_corr_s 向南凸出至 z_out_s（约 5.1 m 深）；
    - 四角白色实心窄柱 + 每层及半层交替叠合的白色实心护栏腰带 + 三面转角采光大窗 + 屋顶突出小女儿墙；
    - 内部集成零缝隙双跑折返楼梯；open_west_1f=True 时在 1F 西侧留出高三楼西口门厅入口（T 点）。
    """
    facade = L.mat('facade')
    concrete = L.mat('concrete')
    glass = L.mat('glass')
    frame = L.mat('frame')
    roof_m = L.mat('roof')
    cm = L.mat('collision')

    y_roof = y_base + n_floors * floor_h + 0.55
    # 底座台基
    box(acc, x0 - 0.18, 0.0, z_corr_s - 0.1, x1 + 0.18, y_base, z_out_s + 0.18, concrete)
    if col is not None:
        box(col, x0 - 0.18, 0.0, z_corr_s - 0.1, x1 + 0.18, y_base, z_out_s + 0.18, cm)
    # 1F 西口台阶（正对西段南外廊 z: z_corr_s - 2.6 .. z_corr_s，即 T 点入口）
    if open_west_1f:
        for st in range(2):
            sx0 = x0 - 0.72 + st * 0.36
            box(acc, sx0, 0.0, z_corr_s - 2.55, x0, (st + 1) * (y_base / 2), z_corr_s - 0.05, concrete)
        if col is not None:
            poly(col, [(x0 - 0.72, 0.0, z_corr_s - 2.55), (x0, y_base, z_corr_s - 2.55),
                       (x0, y_base, z_corr_s - 0.05), (x0 - 0.72, 0.0, z_corr_s - 0.05)], cm)

    # 四角立柱
    for cx in (x0 + 0.16, x1 - 0.16):
        for cz in (z_corr_s + 0.16, z_out_s - 0.16):
            box(acc, cx - 0.16, y_base, cz - 0.16, cx + 0.16, y_roof, cz + 0.16, facade)
            if col is not None:
                box(col, cx - 0.16, y_base, cz - 0.16, cx + 0.16, y_roof, cz + 0.16, cm)

    # 逐层白腰带 + 三面转角大窗（精确对应 ref_gaosan_s.png 中楼梯立面比例）
    for fl in range(n_floors):
        yf = y_base + fl * floor_h
        yt = yf + floor_h
        band_h = 1.05
        win_bot = yf + band_h
        win_top = yt - 0.22

        # 白色外挑实心护栏腰带（南面 + 东西两侧完整闭合）
        box(acc, x0 - 0.04, yf - (0.22 if fl > 0 else 0.0), z_out_s - 0.24, x1 + 0.04, win_bot, z_out_s + 0.04, facade)
        box(acc, x1 - 0.24, yf - (0.22 if fl > 0 else 0.0), z_corr_s, x1 + 0.04, win_bot, z_out_s + 0.04, facade)
        box(acc, x0 - 0.04, yf - (0.22 if fl > 0 else 0.0), z_corr_s, x0 + 0.24, win_bot, z_out_s + 0.04, facade)

        # 三面转角玻璃窗带 + 细窗梃
        _window_x(acc, col, x0 + 0.30, x1 - 0.30, win_bot, win_top, z_out_s - 0.10, 0.20, 'glass')
        _window_z(acc, col, z_corr_s + 0.30, z_out_s - 0.30, win_bot, win_top, x1 - 0.10, 0.20, 'glass')
        _window_z(acc, col, z_corr_s + 0.30, z_out_s - 0.30, win_bot, win_top, x0 + 0.10, 0.20, 'glass')

        # 层顶过梁
        box(acc, x0 - 0.04, win_top, z_out_s - 0.24, x1 + 0.04, yt, z_out_s + 0.04, facade)
        box(acc, x1 - 0.24, win_top, z_corr_s, x1 + 0.04, yt, z_out_s + 0.04, facade)
        box(acc, x0 - 0.04, win_top, z_corr_s, x0 + 0.24, yt, z_out_s + 0.04, facade)

        if col is not None:
            box(col, x0, yf, z_out_s - 0.24, x1, yt, z_out_s, cm)
            box(col, x1 - 0.24, yf, z_corr_s, x1, yt, z_out_s, cm)
            box(col, x0, yf, z_corr_s, x0 + 0.24, yt, z_out_s, cm)

    # 顶盖与屋顶女儿墙收头
    slab_with_ceiling(acc, col, x0 - 0.06, z_corr_s - 0.05, x1 + 0.06, z_out_s + 0.06, y_roof - 0.24, y_roof, 'roof', 'concrete', add_col=False)
    box(acc, x0 - 0.14, y_roof - 0.06, z_corr_s - 0.05, x1 + 0.14, y_roof + 0.38, z_out_s + 0.14, facade, skip=('+y', '-y'))
    box(acc, x0 + 0.10, y_roof, z_corr_s + 0.05, x1 - 0.10, y_roof + 0.05, z_out_s - 0.10, roof_m)

    # 内部零错位双跑楼梯（从 z_corr_s 往南 z_out_s - 0.26）
    build_stair_flights(acc, col, x0 + 0.26, x1 - 0.26, z_corr_s, z_out_s - 0.26, y_base, n_floors, floor_h)


def solar_panels(acc, x0, x1, z0, z1, y_roof):
    """宿舍屋顶太阳能集热板阵列（标志性外形特征）。"""
    m_panel = L.mat('glass_blue')
    m_frame = L.mat('metal_dark')
    z = z0 + 1.0
    while z < z1 - 1.5:
        x = x0 + 1.2
        while x < x1 - 2.6:
            box(acc, x + 0.18, y_roof, z, x + 0.26, y_roof + 0.58, z + 0.08, m_frame)
            box(acc, x + 1.92, y_roof, z, x + 2.00, y_roof + 0.58, z + 0.08, m_frame)
            box(acc, x + 0.18, y_roof, z + 1.0, x + 0.26, y_roof + 0.22, z + 1.08, m_frame)
            box(acc, x + 1.92, y_roof, z + 1.0, x + 2.00, y_roof + 0.22, z + 1.08, m_frame)
            p0 = (x, y_roof + 0.64, z)
            p1 = (x + 2.2, y_roof + 0.64, z)
            p2 = (x + 2.2, y_roof + 0.25, z + 1.15)
            p3 = (x, y_roof + 0.25, z + 1.15)
            poly(acc, [p0, p1, p2, p3], m_panel)
            poly(acc, [p3, p2, p1, p0], m_frame)
            x += 2.8
        z += 2.3


def square_col(acc, col, cx, cz, half_w, y0, y1, mat_key='facade', with_lamp=False, lamp_dir_z=-1):
    """原版高三楼/萃华楼标志性方形白立柱（可选附带外廊暖色小壁灯）。"""
    box(acc, cx - half_w, y0, cz - half_w, cx + half_w, y1, cz + half_w, L.mat(mat_key))
    if with_lamp:
        lz = cz + lamp_dir_z * (half_w + 0.04)
        box(acc, cx - 0.10, y1 - 0.55, lz - 0.05, cx + 0.10, y1 - 0.38, lz + 0.05, L.mat('light_warm'))
    if col is not None:
        box(col, cx - half_w, y0, cz - half_w, cx + half_w, y1, cz + half_w, L.mat('collision'))


def round_col(acc, col, cx, cz, r, y0, y1, mat_key='facade'):
    """建筑圆柱（用于图书馆门廊、雨棚、凉亭）。"""
    m = L.mat(mat_key)
    cap = L.mat('concrete')
    box(acc, cx - r * 1.15, y0, cz - r * 1.15, cx + r * 1.15, y0 + 0.18, cz + r * 1.15, cap)
    cyl(acc, cx, cz, r, y0 + 0.18, y1 - 0.15, m, seg=16, cap_top=False, cap_bot=False)
    box(acc, cx - r * 1.15, y1 - 0.15, cz - r * 1.15, cx + r * 1.15, y1, cz + r * 1.15, cap)
    if col is not None:
        cyl(col, cx, cz, r + 0.04, y0, y1, L.mat('collision'), seg=8)


# ================================================================ 干净植物与景观构件

def add_tree(acc, col, cx, cz, y0=0.0, scale=1.0, seed=0, species='oak'):
    """圆润饱满的现代校园乔木（多层球簇树冠，干净落地，无方块毛刺）。"""
    rng = random.Random(seed)
    trunk_h = 2.55 * scale
    r_base = 0.22 * scale
    cyl(acc, cx, cz, r_base, y0 - 0.05, y0 + trunk_h, L.mat('bark_' + species), seg=10, cap_top=False, cap_bot=False)
    if col is not None:
        cyl(col, cx, cz, r_base + 0.08, y0, y0 + 2.2, L.mat('collision'), seg=6)
    lmat = L.mat('leaves_%s_%d' % (species, seed % 3))
    crowns = [
        (0.0, trunk_h + 1.45 * scale, 0.0, 1.95 * scale),
        (0.88 * scale, trunk_h + 0.85 * scale, 0.52 * scale, 1.48 * scale),
        (-0.82 * scale, trunk_h + 0.92 * scale, -0.56 * scale, 1.48 * scale),
        (0.28 * scale, trunk_h + 0.78 * scale, -0.88 * scale, 1.38 * scale),
        (-0.36 * scale, trunk_h + 0.88 * scale, 0.82 * scale, 1.34 * scale),
    ]
    for dx, dy, dz, r in crowns:
        ang = rng.uniform(0, 6.283)
        ca, sa = math.cos(ang), math.sin(ang)
        rx, rz = dx * ca - dz * sa, dx * sa + dz * ca
        _icosphere_acc(acc, cx + rx, y0 + dy, cz + rz, r, lmat, sx=1.0, sy=0.84, sz=1.0, subdiv=2)


def add_bush(acc, cx, cz, y0=0.0, r=0.9, h=0.85, mat_key='hedge'):
    """干净落地的圆润灌木丛（可用于潜行遮挡）。"""
    _icosphere_acc(acc, cx, y0 + h * 0.45, cz, r, L.mat(mat_key), sx=1.0, sy=h / max(r * 1.4, 0.1), sz=1.0, subdiv=2)


def add_hedge(acc, col, x0, z0, x1, z1, y0=0.0, h=0.82):
    """规整倒角修剪矮绿篱。"""
    if x1 - x0 <= 0.15 or z1 - z0 <= 0.15:
        return
    m = L.mat('hedge')
    d = min(0.09, (x1 - x0) * 0.25, (z1 - z0) * 0.25)
    box(acc, x0, y0, z0, x1, y0 + h - d, z1, m, skip=('-y', '+y'))
    p00, p10, p11, p01 = (x0, y0 + h - d, z0), (x1, y0 + h - d, z0), (x1, y0 + h - d, z1), (x0, y0 + h - d, z1)
    q00, q10, q11, q01 = (x0 + d, y0 + h, z0 + d), (x1 - d, y0 + h, z0 + d), (x1 - d, y0 + h, z1 - d), (x0 + d, y0 + h, z1 - d)
    poly(acc, [q00, q01, q11, q10], m)
    poly(acc, [p00, p10, q10, q00], m)
    poly(acc, [p10, p11, q11, q10], m)
    poly(acc, [p11, p01, q01, q11], m)
    poly(acc, [p01, p00, q00, q01], m)
    if col is not None:
        box(col, x0, y0, z0, x1, y0 + h, z1, L.mat('collision'))


def add_bamboo_cluster(acc, cx, cz, y0=0.0, count=10, spread=1.6, seed=1):
    """庭院翠竹丛。"""
    rng = random.Random(seed)
    m_stem = L.mat('leaves_oak_2')
    m_leaf = L.mat('leaves_birch_1')
    for _ in range(count):
        bx = cx + rng.uniform(-spread, spread)
        bz = cz + rng.uniform(-spread, spread)
        bh = rng.uniform(4.2, 6.2)
        cyl(acc, bx, bz, 0.052, y0, y0 + bh, m_stem, seg=6, cap_bot=False)
        _icosphere_acc(acc, bx + rng.uniform(-0.2, 0.2), y0 + bh - 0.45, bz + rng.uniform(-0.2, 0.2), 0.78, m_leaf, sx=1.15, sy=0.62, sz=1.15)


def add_bench(acc, cx, cz, y0=0.0, ang=0.0):
    """校园木质休闲长椅。"""
    wood = L.mat('wood')
    metal = L.mat('metal_dark')
    obox(acc, cx, cz, 1.8, 0.48, y0 + 0.42, y0 + 0.48, ang, wood)
    ca, sa = math.cos(ang), math.sin(ang)
    for s in (-0.75, 0.75):
        obox(acc, cx + ca * s, cz + sa * s, 0.08, 0.44, y0, y0 + 0.42, ang, metal)
    obox(acc, cx - sa * 0.22, cz + ca * 0.22, 1.8, 0.06, y0 + 0.52, y0 + 0.88, ang, wood)


def _icosphere_acc(acc, cx, cy, cz, r, m, sx=1.0, sy=1.0, sz=1.0, subdiv=1):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    for f in bm.faces:
        pts = [(cx + v.co.x * sx, cy + v.co.z * sy, cz - v.co.y * sz) for v in f.verts]
        poly(acc, pts, m)
    bm.free()


def text_mesh(coll, s, pos_xyz, size, mat_key, facing='south'):
    """生成 3D 中文字牌。"""
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
    cu.extrude = 0.025
    ob = bpy.data.objects.new('text_' + s, cu)
    coll.objects.link(ob)
    x, y, z = pos_xyz
    ob.location = P(x, y, z)
    ob.rotation_euler = (math.pi / 2, 0, {'south': 0, 'north': math.pi, 'west': -math.pi / 2, 'east': math.pi / 2}[facing])
    ob.data.materials.append(L.mat(mat_key))
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(ob)
    mo = bpy.data.objects.new('sign_' + s, me)
    mo.matrix_world = ob.matrix_world
    coll.objects.link(mo)
    bpy.data.objects.remove(ob)
