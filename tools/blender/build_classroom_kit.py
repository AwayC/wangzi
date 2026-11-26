"""教室套件（ENV-T01/T02、ENV-R01 的一部分）：原创造型，规格按 docs/production/02_美术资源清单.md 1.1。

用法（在项目根目录）:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python tools/blender/build_classroom_kit.py -- [资源名 ...]
不写资源名 = 全部重建。输出到 assets/props/classroom/、office/、dorm/、canteen/ 与 assets/env/teaching/。
朝向：正面朝 +Y（Blender）= 导出后朝 -Z（Godot）。
  课桌 / 椅子：坐着的学生看向正面；讲台、黑板、柜子、钟、喇叭：给人看的那面是正面；
  墙模块：正面 = 室内一侧；门：正面 = 室内一侧，门扇枢轴在合页处。
"""
import math
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_lib as K  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROPS = os.path.join(ROOT, 'assets', 'props', 'classroom')
ENV = os.path.join(ROOT, 'assets', 'env', 'teaching')
OFFICE = os.path.join(ROOT, 'assets', 'props', 'office')
DORM = os.path.join(ROOT, 'assets', 'props', 'dorm')
CANTEEN = os.path.join(ROOT, 'assets', 'props', 'canteen')
TMP = tempfile.mkdtemp(prefix='wangzi_bake_')

R = math.radians
ASSETS = {}


def asset(out_dir, res=1024, ao=0.4):
    def deco(fn):
        ASSETS[fn.__name__] = (fn, out_dir, res, ao)
        return fn
    return deco


# ================================================================ 道具

@asset(PROPS)
def desk_student():
    """单人课桌：铁架 + 木纹桌面 + 桌斗（开口朝学生）。桌面高 0.75。"""
    b = K.Part('desk_student')
    b.box((0.60, 0.42, 0.022), (0, 0, 0.739), 'wood_desk', 0.005)
    # 桌斗
    b.box((0.55, 0.35, 0.010), (0, 0.01, 0.600), 'steel_light', 0.002)
    for sx in (-1, 1):
        b.box((0.010, 0.35, 0.13), (sx * 0.270, 0.01, 0.665), 'steel_light', 0.002)
    b.box((0.55, 0.010, 0.13), (0, 0.180, 0.665), 'steel_light', 0.002)
    # 铁架
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.024, 0.024, 0.715), (sx * 0.285, sy * 0.190, 0.0155 + 0.3575), 'steel_frame', 0.003)
            b.box((0.030, 0.030, 0.016), (sx * 0.285, sy * 0.190, 0.008), 'rubber', 0.003)
        b.box((0.020, 0.36, 0.020), (sx * 0.285, 0, 0.14), 'steel_frame', 0.003)
        b.box((0.020, 0.36, 0.020), (sx * 0.285, 0, 0.716), 'steel_frame', 0.003)
    b.box((0.55, 0.020, 0.020), (0, 0.190, 0.716), 'steel_frame', 0.003)
    # 书包挂钩
    b.tube([(0.297, -0.05, 0.70), (0.315, -0.05, 0.70), (0.315, -0.05, 0.66)], 0.004, 'steel_dark', 0.008)
    return [b, K.collider('desk_student', (0.60, 0.42, 0.75), (0, 0, 0.375))]


@asset(PROPS)
def chair_student():
    """钢管椅：两侧一体弯管 + 木座面 + 木靠背。座高 0.44。"""
    b = K.Part('chair_student')
    for sx in (-1, 1):
        x = sx * 0.175
        b.tube([(x, 0.17, 0.012), (x, 0.17, 0.425), (x, -0.16, 0.425), (x, -0.18, 0.012)], 0.011, 'steel_frame', 0.04)
        b.tube([(x, -0.16, 0.425), (x, -0.20, 0.83)], 0.011, 'steel_frame', 0)
        for y in (0.17, -0.18):
            b.cyl(0.013, (x, y, 0.0), (x, y, 0.014), 'rubber', 10)
    b.cyl(0.008, (-0.175, 0.17, 0.12), (0.175, 0.17, 0.12), 'steel_frame', 8)
    b.cyl(0.008, (-0.175, -0.177, 0.12), (0.175, -0.177, 0.12), 'steel_frame', 8)
    b.box((0.40, 0.38, 0.020), (0, 0.005, 0.447), 'wood_desk', 0.006)
    b.box((0.40, 0.018, 0.15), (0, -0.172, 0.71), 'wood_desk', 0.005, rot=(R(-6), 0, 0))
    return [b, K.collider('chair_student', (0.40, 0.40, 0.83), (0, 0, 0.415))]


@asset(PROPS)
def podium():
    """讲台：深色木柜身 + 浅色台面与正面装饰板，背面一个抽屉。"""
    b = K.Part('podium')
    b.box((1.12, 0.57, 0.06), (0, 0, 0.03), 'steel_dark', 0.006)
    b.box((1.10, 0.55, 0.90), (0, 0, 0.51), 'wood_dark', 0.008)
    b.box((1.20, 0.64, 0.04), (0, 0, 0.98), 'wood_desk', 0.008)
    b.box((0.86, 0.012, 0.56), (0, 0.278, 0.52), 'wood_desk', 0.004)
    b.box((0.70, 0.016, 0.03), (0, 0.282, 0.86), 'trim', 0.003)
    b.box((0.48, 0.012, 0.13), (0, -0.278, 0.82), 'wood_desk', 0.004)
    b.box((0.14, 0.020, 0.018), (0, -0.290, 0.82), 'steel_light', 0.004)
    return [b, K.collider('podium', (1.20, 0.64, 1.0), (0, 0, 0.5))]


@asset(PROPS)
def blackboard():
    """4 m 黑板：铝边框、粉笔槽、几支粉笔和一块板擦。枢轴在边框底边中点（挂墙时离地约 0.9 m）。"""
    b = K.Part('blackboard')
    b.box((4.0, 0.03, 1.20), (0, 0, 0.64), 'board_green', 0.002)
    for z in (0.02, 1.26):
        b.box((4.08, 0.045, 0.04), (0, 0.004, z), 'alu', 0.004)
    for sx in (-1, 1):
        b.box((0.04, 0.045, 1.28), (sx * 2.02, 0.004, 0.64), 'alu', 0.004)
    b.box((3.70, 0.09, 0.012), (0, 0.06, 0.03), 'alu', 0.002)
    b.box((3.70, 0.008, 0.026), (0, 0.103, 0.043), 'alu', 0.002)
    random.seed(3)
    for i in range(5):
        x = -1.4 + i * 0.12 + random.uniform(-0.03, 0.03)
        b.cyl(0.0055, (x, 0.05, 0.043), (x + 0.075, 0.07, 0.043), 'chalk', 8)
    b.box((0.14, 0.05, 0.028), (1.2, 0.06, 0.051), 'wood_dark', 0.005)
    b.box((0.13, 0.045, 0.012), (1.2, 0.06, 0.031), 'felt', 0.002)
    return [b]


@asset(PROPS)
def locker_steel():
    """双开门铁皮文件柜（藏匿点 / 没收柜都可用）。门扇单独对象，枢轴在合页。"""
    b = K.Part('locker_steel')
    b.box((0.90, 0.42, 1.80), (0, 0, 0.95), 'steel_light', 0.008)
    b.box((0.86, 0.38, 0.05), (0, 0, 0.025), 'steel_dark', 0.004)
    parts = [b]
    for side, sx in (('door_l', -1), ('door_r', 1)):
        d = K.Part(side, origin=(sx * 0.445, 0.211, 0.0), parent=b)
        d.box((0.44, 0.016, 1.70), (sx * 0.224, 0.220, 0.95), 'steel_light', 0.004)
        d.box((0.016, 0.030, 0.13), (sx * 0.03, 0.238, 1.00), 'steel_dark', 0.004)
        for k in range(4):
            d.box((0.20, 0.006, 0.010), (sx * 0.23, 0.229, 1.56 + k * 0.03), 'steel_dark', 0.002)
        d.box((0.10, 0.004, 0.05), (sx * 0.23, 0.229, 1.30), 'white_plastic', 0.001)
        parts.append(d)
    parts.append(K.collider('locker_steel', (0.90, 0.44, 1.85), (0, 0.01, 0.925)))
    return parts


@asset(PROPS)
def bookshelf():
    """教室后排图书角：开放木书架 + 一排排书。"""
    b = K.Part('bookshelf')
    for sx in (-1, 1):
        b.box((0.022, 0.30, 1.20), (sx * 0.589, 0, 0.60), 'wood_desk', 0.004)
    for z in (0.04, 0.42, 0.80, 1.19):
        b.box((1.156, 0.30, 0.020), (0, 0, z), 'wood_desk', 0.003)
    b.box((1.20, 0.010, 1.20), (0, -0.146, 0.60), 'wood_dark', 0.002)
    b.box((1.156, 0.012, 0.04), (0, 0.144, 0.02), 'wood_dark', 0.002)
    random.seed(11)
    cols = ['book_red', 'book_blue', 'book_green', 'book_yellow', 'book_white', 'book_teal']
    for z0 in (0.05, 0.43, 0.81):
        x = -0.565
        while x < 0.50:
            w = random.uniform(0.022, 0.05)
            h = random.uniform(0.20, 0.30)
            d = random.uniform(0.17, 0.22)
            if random.random() < 0.12:
                x += 0.05
                continue
            b.box((w, d, h), (x + w / 2, 0.02, z0 + h / 2), random.choice(cols), 0)
            x += w + 0.002
    return [b, K.collider('bookshelf', (1.20, 0.30, 1.20), (0, 0, 0.60))]


@asset(PROPS, res=512, ao=0.05)
def wall_clock():
    """挂钟：枢轴在背面中心，表盘朝正面。"""
    b = K.Part('wall_clock')
    b.cyl(0.17, (0, 0, 0), (0, 0.045, 0), 'clock_rim', 32)
    b.cyl(0.152, (0, 0.045, 0), (0, 0.048, 0), 'white_plastic', 32)
    for k in range(12):
        a = k * math.pi / 6
        long = 0.03 if k % 3 == 0 else 0.016
        r = 0.132
        b.box((0.008, 0.003, long), (math.sin(a) * r, 0.049, math.cos(a) * r), 'black', 0, rot=(0, a, 0))
    b.box((0.010, 0.003, 0.085), (0.03, 0.051, 0.03), 'black', 0, rot=(0, R(-45), 0))
    b.box((0.006, 0.003, 0.125), (-0.044, 0.053, 0.044), 'black', 0, rot=(0, R(45), 0))
    b.cyl(0.010, (0, 0.048, 0), (0, 0.056, 0), 'clock_rim', 12)
    return [b]


@asset(PROPS, res=512, ao=0.1)
def speaker_box():
    """广播喇叭：米色木箱 + 深色网罩，枢轴在背面中心。"""
    b = K.Part('speaker_box')
    b.box((0.34, 0.14, 0.24), (0, 0.07, 0), 'beige_plastic', 0.012)
    b.box((0.28, 0.010, 0.17), (0, 0.142, -0.01), 'grill', 0.004)
    b.box((0.06, 0.010, 0.014), (0.11, 0.142, 0.095), 'black', 0.002)
    b.box((0.10, 0.03, 0.03), (0, 0.015, 0.13), 'steel_dark', 0.004)
    return [b]


@asset(PROPS, res=512, ao=0.1)
def ceiling_light():
    """日光灯：枢轴在天花板挂点，灯体下垂 0.3 m。灯管单独对象（tube），程序可单独给自发光。"""
    b = K.Part('ceiling_light')
    for sx in (-1, 1):
        b.cyl(0.004, (sx * 0.45, 0, 0), (sx * 0.45, 0, -0.28), 'steel_dark', 6)
    b.box((1.26, 0.16, 0.045), (0, 0, -0.30), 'white_plastic', 0.008)
    t = K.Part('tube', origin=(0, 0, -0.35), parent=b)
    for sy in (-1, 1):
        t.cyl(0.013, (-0.60, sy * 0.035, -0.345), (0.60, sy * 0.035, -0.345), 'tube_white', 10)
    return [b, t]


@asset(PROPS, res=512, ao=0.15)
def ceiling_fan():
    """吊扇：枢轴在天花板挂点；扇叶单独对象（rotor），绕 Y（Godot）旋转。"""
    b = K.Part('ceiling_fan')
    b.cyl(0.06, (0, 0, 0), (0, 0, -0.05), 'fan_green', 16)
    b.cyl(0.012, (0, 0, -0.05), (0, 0, -0.50), 'steel_light', 8)
    b.cyl(0.12, (0, 0, -0.50), (0, 0, -0.60), 'fan_green', 24, r2=0.09)
    r = K.Part('rotor', origin=(0, 0, -0.62), parent=b)
    r.cyl(0.075, (0, 0, -0.60), (0, 0, -0.64), 'steel_light', 20)
    for k in range(3):
        a = k * 2 * math.pi / 3
        rx, ry = math.cos(a), math.sin(a)
        r.box((0.12, 0.02, 0.008), (rx * 0.12, ry * 0.12, -0.625), 'steel_dark', 0.002, rot=(0, 0, a))
        r.box((0.52, 0.11, 0.006), (rx * 0.44, ry * 0.44, -0.625), 'fan_green', 0.003, rot=(R(8), 0, a))
    return [b, r]


# ================================================================ 墙地门窗模块

H = 3.4          # 层高
T = 0.2          # 墙厚
WAIN = 1.10      # 墙裙高
SKIRT = 0.12     # 踢脚高


def _clip(a0, a1, b0, b1):
    lo, hi = max(a0, b0), min(a1, b1)
    return (lo, hi) if hi - lo > 1e-4 else None


def _wall(name, rects, cols):
    """rects: [(x0, x1, z0, z1)] 实心矩形。两面都有踢脚、墙裙、腰线。"""
    b = K.Part(name)
    for x0, x1, z0, z1 in rects:
        w = x1 - x0
        cx = (x0 + x1) / 2
        b.box((w, T, z1 - z0), (cx, 0, (z0 + z1) / 2), 'wall_white', 0)
        for sy in (-1, 1):
            for (lo, hi, mat, dep) in ((0, SKIRT, 'trim', 0.012), (SKIRT, WAIN, 'wall_blue', 0.004), (WAIN, WAIN + 0.03, 'trim', 0.010)):
                c = _clip(z0, z1, lo, hi)
                if c:
                    b.box((w, dep, c[1] - c[0]), (cx, sy * (T / 2 + dep / 2), (c[0] + c[1]) / 2), mat, 0)
    parts = [b]
    for i, (x0, x1, z0, z1) in enumerate(cols):
        parts.append(K.collider('%s_%d' % (name, i), (x1 - x0, T, z1 - z0), ((x0 + x1) / 2, 0, (z0 + z1) / 2)))
    return parts


@asset(ENV, ao=0.6)
def wall_plain_4m():
    """4 m 直墙。枢轴在底边中点，墙厚居中。"""
    return _wall('wall_plain_4m', [(-2, 2, 0, H)], [(-2, 2, 0, H)])


@asset(ENV, ao=0.6)
def wall_window_4m():
    """4 m 带窗墙：窗洞 2.6 × 1.8（窗台 0.9 m），铝合金推拉窗两扇。"""
    wx, z0, z1 = 1.3, 0.9, 2.7
    parts = _wall('wall_window_4m', [(-2, 2, 0, z0), (-2, 2, z1, H), (-2, -wx, z0, z1), (wx, 2, z0, z1)], [(-2, 2, 0, H)])
    b = parts[0]
    f = 0.05
    b.box((2 * wx + 0.06, 0.28, 0.03), (0, 0.04, z0 + 0.015), 'sill', 0.004)
    b.box((2 * wx, 0.10, f), (0, 0, z1 - f / 2), 'window_frame', 0.003)
    b.box((2 * wx, 0.10, f), (0, 0, z0 + 0.03 + f / 2), 'window_frame', 0.003)
    for sx in (-1, 1):
        b.box((f, 0.10, z1 - z0), (sx * (wx - f / 2), 0, (z0 + z1) / 2), 'window_frame', 0.003)
    glass = K.Part('glass', bake=False)
    gz0, gz1 = z0 + 0.03 + f, z1 - f
    for k, (sx, y) in enumerate(((-1, -0.022), (1, 0.022))):
        sw = wx - f + 0.03
        cx = sx * (sw / 2 - 0.015)
        for zz in (gz0 + 0.02, gz1 - 0.02):
            b.box((sw, 0.035, 0.04), (cx, y, zz), 'window_frame', 0.003)
        for xx in (cx - sw / 2 + 0.02, cx + sw / 2 - 0.02):
            b.box((0.04, 0.035, gz1 - gz0), (xx, y, (gz0 + gz1) / 2), 'window_frame', 0.003)
        b.box((0.014, 0.02, 0.10), (cx - sx * (sw / 2 - 0.06), y + 0.025, (gz0 + gz1) / 2), 'steel_dark', 0.003)
        glass.box((sw - 0.06, 0.006, gz1 - gz0 - 0.06), (cx, y, (gz0 + gz1) / 2), 'glass', 0)
    return parts + [glass]


@asset(ENV, ao=0.6)
def wall_door_4m():
    """4 m 带门洞墙：门洞 1.6 × 2.2 居中，配 door_classroom。"""
    return _wall('wall_door_4m', [(-2, -0.8, 0, H), (0.8, 2, 0, H), (-0.8, 0.8, 2.2, H)],
                 [(-2, -0.8, 0, H), (0.8, 2, 0, H), (-0.8, 0.8, 2.2, H)])


@asset(ENV)
def door_classroom():
    """教室双开门（1.6 × 2.2，导航宽度要求），每扇带观察小窗。枢轴在门洞底边中点；门扇 leaf_l / leaf_r 枢轴在合页。"""
    fr = K.Part('door_frame')
    for sx in (-1, 1):
        fr.box((0.06, 0.24, 2.26), (sx * 0.83, 0, 1.13), 'wood_dark', 0.004)
    fr.box((1.72, 0.24, 0.06), (0, 0, 2.23), 'wood_dark', 0.004)
    parts = [fr]
    for name, sx in (('leaf_l', -1), ('leaf_r', 1)):
        lf = K.Part(name, origin=(sx * 0.80, 0, 0), parent=fr)

        def X(a, b_):  # 门扇局部 x 区间（从合页量起）→ 世界 x
            p, q = sx * (0.80 - a), sx * (0.80 - b_)
            return (min(p, q), max(p, q))
        wz0, wz1 = 1.35, 1.85
        for (a, b_), (z0, z1) in (((0.0, 0.795), (0.01, wz0)), ((0.0, 0.795), (wz1, 2.19)),
                                   ((0.0, 0.42), (wz0, wz1)), ((0.62, 0.795), (wz0, wz1))):
            x0, x1 = X(a, b_)
            lf.box((x1 - x0, 0.045, z1 - z0), ((x0 + x1) / 2, 0, (z0 + z1) / 2), 'wood_door', 0.003)
        gx0, gx1 = X(0.42, 0.62)
        for sy in (-1, 1):
            lf.box((gx1 - gx0 + 0.04, 0.008, 0.02), ((gx0 + gx1) / 2, sy * 0.026, wz0), 'wood_dark', 0.002)
            lf.box((gx1 - gx0 + 0.04, 0.008, 0.02), ((gx0 + gx1) / 2, sy * 0.026, wz1), 'wood_dark', 0.002)
            lf.box((0.70, 0.004, 0.22), (sx * 0.40, sy * 0.0245, 0.13), 'steel_light', 0.002)
            hx = sx * 0.06
            lf.box((0.02, 0.012, 0.03), (hx, sy * 0.028, 1.0), 'steel_dark', 0.002)
            lf.box((0.12, 0.02, 0.018), (hx + sx * 0.05, sy * 0.042, 1.0), 'steel_light', 0.004)
        g = K.Part(name + '_glass', bake=False, origin=(sx * 0.80, 0, 0), parent=lf)
        g.box((gx1 - gx0, 0.006, wz1 - wz0), ((gx0 + gx1) / 2, 0, (wz0 + wz1) / 2), 'glass', 0)
        parts += [lf, g, K.collider(name, (0.80, 0.045, 2.19), (sx * 0.40, 0, 1.10), parent=lf, origin=(sx * 0.80, 0, 0))]
    return parts


@asset(ENV, ao=0.3)
def floor_tile_4m():
    """4 × 4 m 地砖（0.6 m 砖）。上表面在 z=0。"""
    b = K.Part('floor_tile_4m')
    b.box((4.0, 4.0, 0.05), (0, 0, -0.025), 'floor_tile', 0)
    return [b, K.collider('floor_tile_4m', (4.0, 4.0, 0.05), (0, 0, -0.025))]


@asset(ENV, ao=0.3)
def podium_platform():
    """讲台地台 6 × 1.5 × 0.2，前沿包铝条。"""
    b = K.Part('podium_platform')
    b.box((6.0, 1.5, 0.19), (0, 0, 0.095), 'wood_dark', 0.006)
    b.box((6.0, 0.03, 0.012), (0, 0.75, 0.194), 'alu', 0.002)
    b.box((6.0, 0.012, 0.19), (0, 0.756, 0.095), 'trim', 0.002)
    return [b, K.collider('podium_platform', (6.0, 1.5, 0.2), (0, 0, 0.1))]


# ================================================================ 机房 / 办公 / 宿舍 / 食堂

@asset(OFFICE)
def computer_desk():
    """机房电脑桌：1.2 × 0.6 木桌面 + 钢架，显示器、键盘、鼠标、主机。人坐在 -Y 一侧，屏幕朝人。"""
    b = K.Part('computer_desk')
    b.box((1.20, 0.60, 0.025), (0, 0, 0.7375), 'wood_desk', 0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.03, 0.03, 0.725), (sx * 0.57, sy * 0.27, 0.3625), 'steel_light', 0.003)
        b.box((0.025, 0.52, 0.025), (sx * 0.57, 0, 0.12), 'steel_light', 0.003)
    b.box((1.10, 0.012, 0.30), (0, 0.27, 0.55), 'steel_light', 0.002)  # 挡板
    for sx in (-0.30, 0.30):
        # 显示器：底座 + 支杆 + 屏
        b.box((0.20, 0.16, 0.012), (sx, 0.14, 0.756), 'black', 0.003)
        b.box((0.04, 0.03, 0.20), (sx, 0.17, 0.85), 'black', 0.004)
        b.box((0.50, 0.035, 0.30), (sx, 0.15, 1.05), 'black', 0.008)
        b.box((0.47, 0.004, 0.27), (sx, 0.131, 1.05), 'screen', 0)
        b.box((0.42, 0.14, 0.018), (sx, -0.12, 0.759), 'black', 0.003)  # 键盘
        b.box((0.06, 0.10, 0.025), (sx + 0.28, -0.12, 0.762), 'black', 0.008)  # 鼠标
        b.box((0.18, 0.42, 0.40), (sx, 0.05, 0.22), 'beige_plastic', 0.006)  # 主机（桌下）
        b.box((0.10, 0.004, 0.03), (sx, -0.162, 0.36), 'black', 0)
    return [b, K.collider('computer_desk', (1.20, 0.60, 0.75), (0, 0, 0.375))]


@asset(OFFICE)
def office_desk():
    """办公桌：1.4 × 0.7，右侧三抽屉柜，桌上一台显示器、一摞作业本、笔筒。人坐在 -Y 一侧。"""
    b = K.Part('office_desk')
    b.box((1.40, 0.70, 0.03), (0, 0, 0.745), 'wood_dark', 0.006)
    b.box((0.03, 0.66, 0.73), (-0.685, 0, 0.365), 'wood_dark', 0.004)
    b.box((0.42, 0.66, 0.73), (0.48, 0, 0.365), 'wood_dark', 0.004)
    for k in range(3):
        z = 0.14 + k * 0.23
        b.box((0.38, 0.01, 0.20), (0.48, -0.335, z + 0.07), 'wood_desk', 0.004)
        b.box((0.10, 0.02, 0.015), (0.48, -0.345, z + 0.13), 'alu', 0.003)
    b.box((1.0, 0.012, 0.45), (-0.2, 0.33, 0.48), 'wood_dark', 0.003)
    b.box((0.45, 0.03, 0.28), (-0.25, 0.22, 1.02), 'black', 0.008)
    b.box((0.42, 0.004, 0.25), (-0.25, 0.203, 1.02), 'screen', 0)
    b.box((0.18, 0.14, 0.012), (-0.25, 0.22, 0.766), 'black', 0.003)
    b.box((0.035, 0.03, 0.12), (-0.25, 0.235, 0.83), 'black', 0.004)
    for k, col in enumerate(('book_white', 'book_blue', 'book_white', 'book_red', 'book_white')):
        b.box((0.21, 0.29, 0.012), (0.40 + (k % 2) * 0.01, -0.05, 0.766 + k * 0.013), col, 0.002)
    b.cyl(0.04, (0.62, 0.20, 0.76), (0.62, 0.20, 0.87), 'black', 12)
    return [b, K.collider('office_desk', (1.40, 0.70, 0.76), (0, 0, 0.38))]


@asset(DORM)
def bunk_bed():
    """宿舍上下铺铁床：0.9 × 2.0，床头梯子在 +X 端，蓝格被子、白枕头。长边沿 Y。"""
    b = K.Part('bunk_bed')
    w, l = 0.92, 2.02
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.04, 0.04, 1.80), (sx * (w / 2 - 0.02), sy * (l / 2 - 0.02), 0.90), 'steel_frame', 0.004)
    for z in (0.30, 1.30):
        for sx in (-1, 1):
            b.box((0.03, l, 0.05), (sx * (w / 2 - 0.02), 0, z), 'steel_frame', 0.003)
        for sy in (-1, 1):
            b.box((w, 0.03, 0.05), (0, sy * (l / 2 - 0.02), z), 'steel_frame', 0.003)
        b.box((w - 0.06, l - 0.06, 0.02), (0, 0, z + 0.02), 'wood_desk', 0.003)
        b.box((w - 0.10, l - 0.10, 0.12), (0, 0, z + 0.09), 'mattress', 0.03)
        b.box((w - 0.12, l * 0.62, 0.07), (0, -l * 0.17, z + 0.18), 'blanket_blue', 0.03)
        b.box((0.55, 0.32, 0.10), (0, l / 2 - 0.25, z + 0.19), 'pillow', 0.04)
    for sy in (-1, 1):  # 床头床尾护栏
        for z in (0.55, 1.55, 1.75):
            b.box((w, 0.025, 0.025), (0, sy * (l / 2 - 0.02), z), 'steel_frame', 0.003)
    for sy in (0.25, 0.60):  # 上铺侧护栏
        b.box((0.025, 0.5, 0.025), (-(w / 2 - 0.02), sy, 1.62), 'steel_frame', 0.003)
    # 梯子
    for y in (-l / 2 + 0.05, -l / 2 + 0.40):
        b.box((0.03, 0.03, 1.50), (w / 2 + 0.04, y, 0.75), 'steel_frame', 0.003)
    for k in range(4):
        b.box((0.03, 0.38, 0.025), (w / 2 + 0.04, -l / 2 + 0.225, 0.35 + k * 0.33), 'steel_frame', 0.003)
    return [b, K.collider('bunk_bed', (w, l, 1.80), (0, 0, 0.90))]


@asset(CANTEEN)
def canteen_table():
    """食堂连凳餐桌：不锈钢框架，1.6 × 0.7 桌面，两侧各一条长凳（橙色塑料凳面）。长边沿 X。"""
    b = K.Part('canteen_table')
    b.box((1.60, 0.70, 0.025), (0, 0, 0.7375), 'white_plastic', 0.008)
    b.box((1.60, 0.72, 0.012), (0, 0, 0.72), 'stainless', 0.003)
    for sx in (-1, 1):
        b.tube([(sx * 0.70, -0.62, 0.02), (sx * 0.70, -0.62, 0.42), (sx * 0.70, -0.30, 0.42), (sx * 0.70, -0.20, 0.72)], 0.018, 'stainless', 0.05)
        b.tube([(sx * 0.70, 0.62, 0.02), (sx * 0.70, 0.62, 0.42), (sx * 0.70, 0.30, 0.42), (sx * 0.70, 0.20, 0.72)], 0.018, 'stainless', 0.05)
        b.cyl(0.016, (sx * 0.70, -0.62, 0.10), (sx * 0.70, 0.62, 0.10), 'stainless', 10)
    for sy in (-1, 1):
        b.box((1.50, 0.30, 0.03), (0, sy * 0.60, 0.445), 'plastic_orange', 0.01)
        b.cyl(0.015, (-0.70, sy * 0.60, 0.42), (0.70, sy * 0.60, 0.42), 'stainless', 10)
    return [b, K.collider('canteen_table', (1.60, 1.56, 0.75), (0, 0, 0.375))]


@asset(PROPS)
def reading_sofa():
    """校园阅览角双人布艺沙发（正面朝 +Y）：木质短腿 + 厚坐垫 + 斜靠背 + 扶手 + 靠枕。"""
    b = K.Part('reading_sofa')
    # 四只木脚
    for sx in (-0.64, 0.64):
        for sy in (-0.28, 0.28):
            b.cyl(0.028, (sx, sy, 0.0), (sx, sy, 0.11), 'wood_dark', 10)
    # 底座框架与左右宽扶手
    b.box((1.44, 0.72, 0.14), (0, 0, 0.18), 'blanket_blue', 0.02)
    for sx in (-0.64, 0.64):
        b.box((0.16, 0.72, 0.48), (sx, 0, 0.38), 'blanket_blue', 0.03)
    # 两块厚实浅色坐垫
    for sx in (-0.28, 0.28):
        b.box((0.55, 0.58, 0.14), (sx, 0.05, 0.32), 'mattress', 0.03)
    # 微后倾靠背与两个小抱枕
    b.box((1.12, 0.16, 0.46), (0, -0.27, 0.56), 'blanket_blue', 0.035, rot=(R(-8), 0, 0))
    b.box((0.28, 0.10, 0.26), (-0.34, -0.16, 0.50), 'book_yellow', 0.03, rot=(R(-14), 0, R(8)))
    b.box((0.28, 0.10, 0.26), (0.34, -0.16, 0.50), 'pillow', 0.03, rot=(R(-14), 0, R(-8)))
    return [b, K.collider('reading_sofa', (1.44, 0.74, 0.80), (0, 0, 0.40))]


# ================================================================

def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    names = argv or list(ASSETS)
    report = []
    for n in names:
        fn, out_dir, res, ao = ASSETS[n]
        K.reset_scene()
        parts = fn()
        out = os.path.join(out_dir, n + '.glb')
        tris = K.finish(n, parts, out, res=res, ao_dist=ao, tmp_dir=TMP)
        report.append((n, tris, res))
        print('KIT %-18s %6d tris  %d²  -> %s' % (n, tris, res, os.path.relpath(out, ROOT)), flush=True)
    print('KIT DONE', len(report))


main()
