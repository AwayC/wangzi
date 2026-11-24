"""生成校园用的可平铺贴图（numpy 程序化，四方连续），输出到 assets/env/campus/textures/。

用法: python3 -I tools/blender/make_textures.py
每张贴图对应的真实尺寸（米）写在 TILE 里，Blender 重建时按这个尺寸算 UV，所以砖缝、地砖、草叶在场景里大小一致。
"""
import os

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'assets', 'env', 'campus', 'textures')
N = 1024
rng = np.random.default_rng(20261124)

# 贴图名 → 一张图覆盖的真实边长（米）；Blender 侧 campus 材质表要和这里一致
TILE = {
    'facade_tile': 2.0, 'plaster': 4.0, 'concrete': 4.0, 'paving': 4.0, 'plaza_stone': 4.0, 'asphalt': 6.0,
    'grass': 4.0, 'soil': 3.0, 'wood': 2.0, 'bark': 1.5, 'leaves': 2.0, 'roof': 4.0, 'metal': 2.0, 'water': 8.0,
    'stone_wall': 3.0, 'gravel': 2.0, 'shutter': 2.0, 'roof_tile': 2.0,
}


def noise(scale, n=N, aniso=(1.0, 1.0)):
    """四方连续的分形噪声：白噪声在频域做高斯低通。scale = 特征尺寸（像素）。"""
    w = rng.standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None] * aniso[0]
    fx = np.fft.fftfreq(n)[None, :] * aniso[1]
    f = np.sqrt(fx * fx + fy * fy)
    g = np.exp(-(f * scale) ** 2 * 2.0)
    r = np.real(np.fft.ifft2(np.fft.fft2(w) * g))
    return (r - r.mean()) / (r.std() + 1e-9)


def fbm(scales, weights, n=N, aniso=(1.0, 1.0)):
    out = np.zeros((n, n))
    for s, wgt in zip(scales, weights):
        out += noise(s, n, aniso) * wgt
    return out


def save(name, rgb):
    os.makedirs(OUT, exist_ok=True)
    img = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(img).save(os.path.join(OUT, name + '.png'), optimize=True)
    print('OK', name, img.shape)


def colorize(base, var):
    base = np.array(base)[None, None, :]
    return base * (1 + var[..., None])


def tiles(cell_px, grout_px, base, tile_var, grout_col, offset_rows=False, n=N):
    """规则砖 / 地砖：每块随机明暗，砖缝颜色单独。"""
    yy, xx = np.mgrid[0:n, 0:n]
    row = yy // cell_px[1]
    shift = (row % 2) * (cell_px[0] // 2) if offset_rows else 0
    col = (xx + shift) // cell_px[0]
    ncol, nrow = n // cell_px[0] + 2, n // cell_px[1] + 2
    per = rng.normal(0, tile_var, (nrow + 2, ncol + 2))
    tv = per[row % nrow, col % ncol]
    gx = ((xx + shift) % cell_px[0]) < grout_px
    gy = (yy % cell_px[1]) < grout_px
    grout = gx | gy
    rgb = colorize(base, tv[..., ] + 0.03 * noise(3) + 0.02 * noise(40))
    rgb[grout] = np.array(grout_col) * (1 + 0.04 * noise(4)[grout][..., None])
    # 砖边一点点暗，显得有厚度
    edge = (((xx + shift) % cell_px[0]) < grout_px + 2) | ((yy % cell_px[1]) < grout_px + 2)
    rgb[edge & ~grout] *= 0.93
    return rgb


def main():
    # 外墙面砖：0.25 m 一块（2 m = 8 块），乳白，竖向雨渍
    rgb = tiles((128, 128), 2, (0.90, 0.89, 0.86), 0.010, (0.80, 0.80, 0.78))
    streak = noise(60, aniso=(0.15, 1.0))
    rgb *= (1 - 0.02 * np.clip(streak, 0, None))[..., None]
    save('facade_tile', rgb)
    # 涂料墙：低频污渍 + 细砂
    v = 0.018 * fbm([200, 60], [1, 0.5]) + 0.015 * noise(1.5)
    save('plaster', colorize((0.90, 0.89, 0.86), v))
    # 混凝土：灰，斑点和模板缝
    v = 0.03 * fbm([150, 30], [1, 0.6]) + 0.025 * noise(1.2)
    rgb = colorize((0.66, 0.66, 0.64), v)
    rgb[:, :3] *= 0.85
    rgb[:3, :] *= 0.85
    save('concrete', rgb)
    # 铺地：0.5 m 方砖（4 m = 8 块）
    save('paving', tiles((128, 128), 4, (0.68, 0.67, 0.64), 0.04, (0.48, 0.48, 0.46)))
    # 广场石材：1 m × 0.5 m 错缝条石
    save('plaza_stone', tiles((256, 128), 4, (0.62, 0.60, 0.57), 0.05, (0.42, 0.41, 0.39), offset_rows=True))
    # 沥青
    v = 0.06 * noise(1.0) + 0.05 * fbm([120, 20], [1, 0.5])
    save('asphalt', colorize((0.30, 0.30, 0.31), v))
    # 草地：多尺度绿色 + 草叶高光
    v = fbm([180, 50, 8], [0.10, 0.08, 0.10])
    rgb = colorize((0.30, 0.50, 0.19), v)
    blades = noise(1.2, aniso=(0.3, 1.0))
    rgb[..., 1] += 0.05 * np.clip(blades, 0, None)
    rgb[..., 0] += 0.02 * np.clip(noise(90), 0, None)
    save('grass', rgb)
    # 泥土
    v = fbm([60, 10, 1.5], [0.08, 0.06, 0.06])
    save('soil', colorize((0.40, 0.29, 0.19), v))
    # 碎石
    v = 0.12 * noise(2.5) + 0.05 * noise(20)
    save('gravel', colorize((0.55, 0.53, 0.50), v))
    # 木板：0.2 m 宽（2 m = 10 条）
    yy, xx = np.mgrid[0:N, 0:N]
    plank = (yy // 102)
    pv = rng.normal(0, 0.06, 20)[plank % 20]
    grain = noise(3, aniso=(1.0, 0.05))
    rgb = colorize((0.58, 0.42, 0.26), pv + 0.08 * grain + 0.03 * noise(30))
    rgb[(yy % 102) < 2] *= 0.6
    save('wood', rgb)
    # 树皮：竖向裂纹
    v = noise(6, aniso=(0.08, 1.0)) * 0.18 + noise(30) * 0.06
    rgb = colorize((0.36, 0.28, 0.20), v)
    cracks = noise(3, aniso=(0.05, 1.0)) < -1.1
    rgb[cracks] *= 0.55
    save('bark', rgb)
    # 树叶：深浅叶团
    v = fbm([30, 10, 3], [0.12, 0.08, 0.05])
    rgb = colorize((0.22, 0.44, 0.16), v)
    holes = noise(6) < -1.6
    rgb[holes] *= 0.7
    hi = noise(5) > 1.5
    rgb[hi] *= 1.12
    save('leaves', rgb)
    # 屋面：灰色卷材，1 m 接缝
    v = 0.04 * fbm([150, 25], [1, 0.5]) + 0.03 * noise(1.2)
    rgb = colorize((0.52, 0.53, 0.54), v)
    rgb[(yy % 256) < 3] *= 0.85
    save('roof', rgb)
    # 金属：拉丝
    v = 0.05 * noise(2, aniso=(0.02, 1.0)) + 0.02 * noise(60)
    save('metal', colorize((0.68, 0.69, 0.70), v))
    # 卷帘门
    rgb = colorize((0.70, 0.71, 0.72), 0.03 * noise(40))
    rgb[(yy % 32) < 5] *= 0.78
    save('shutter', rgb)
    # 青瓦：0.2 m 一垄（2 m = 10 垄），垄面圆弧明暗 + 每片瓦的接缝
    col = (xx % 102) / 102.0
    shade = 0.75 + 0.35 * np.sin(col * np.pi)
    rows = (yy % 85) < 6
    rgb = colorize((0.33, 0.35, 0.37), 0.06 * noise(2) + 0.04 * noise(40)) * shade[..., None]
    rgb[rows] *= 0.7
    save('roof_tile', rgb)
    # 水
    v = 0.08 * fbm([120, 30], [1, 0.5])
    save('water', colorize((0.18, 0.36, 0.52), v))
    # 毛石墙
    v = noise(10)
    cell = np.abs(noise(16)) < 0.12
    rgb = colorize((0.52, 0.51, 0.49), 0.10 * v + 0.05 * noise(1.5))
    rgb[cell] *= 0.6
    save('stone_wall', rgb)


if __name__ == '__main__':
    main()
