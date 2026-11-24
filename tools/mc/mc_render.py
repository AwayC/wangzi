"""把 mc_scan 导出的体素渲染成俯视图 / 高度图 / 指定高度的水平切片。
用法:
  python3 -I mc_render.py <mc目录> top                  → top.png、height.png、blocks_top.txt
  python3 -I mc_render.py <mc目录> slice <y> [x0 z0 x1 z1] [scale] → slice_<y>.png（局部坐标，相对体素原点）
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw

D = sys.argv[1]
vol = np.load(os.path.join(D, 'blocks.npy'))
names = json.load(open(os.path.join(D, 'palette.json')))
meta = json.load(open(os.path.join(D, 'meta.json')))
H, Z, X = vol.shape

COLOR_WORDS = {
    'white': (235, 235, 235), 'orange': (230, 130, 40), 'magenta': (190, 70, 180), 'light_blue': (110, 170, 220),
    'yellow': (240, 210, 60), 'lime': (120, 200, 50), 'pink': (240, 150, 170), 'light_gray': (160, 160, 155),
    'gray': (90, 95, 100), 'cyan': (40, 140, 150), 'purple': (120, 50, 170), 'blue': (50, 60, 160),
    'brown': (110, 75, 45), 'green': (80, 110, 40), 'red': (170, 45, 40), 'black': (30, 30, 35),
}


def color_of(n):
    s = n.replace('minecraft:', '')
    if s in ('air', 'cave_air', 'void_air'):
        return None
    for w in sorted(COLOR_WORDS, key=len, reverse=True):
        if s.startswith(w + '_'):
            c = COLOR_WORDS[w]
            return tuple(int(v * 0.85) for v in c) if 'terracotta' in s else c
    if 'glass' in s: return (170, 210, 230)
    if 'water' in s: return (60, 100, 200)
    if 'leaves' in s or s in ('grass', 'tall_grass', 'fern') or 'sapling' in s: return (60, 130, 50)
    if s == 'grass_block': return (100, 150, 70)
    if 'log' in s or 'wood' in s: return (100, 75, 50)
    if 'oak' in s or 'spruce' in s or 'birch' in s or 'jungle' in s or 'acacia' in s or 'planks' in s: return (160, 125, 80)
    if 'brick' in s and 'stone' not in s and 'nether' not in s: return (150, 80, 65)
    if 'quartz' in s: return (230, 225, 215)
    if 'sand' in s: return (215, 200, 150)
    if 'iron' in s: return (200, 200, 200)
    if 'stone' in s or 'andesite' in s or 'cobble' in s or 'diorite' in s or 'granite' in s: return (125, 125, 125)
    if 'snow' in s: return (245, 245, 250)
    if 'dirt' in s or 'path' in s or 'farmland' in s: return (130, 95, 60)
    return (200, 80, 200)


lut = np.zeros((len(names), 3), np.uint8)
is_air = np.zeros(len(names), bool)
for i, n in enumerate(names):
    c = color_of(n)
    if c is None:
        is_air[i] = True
    else:
        lut[i] = c

mode = sys.argv[2]
if mode == 'top':
    solid = ~is_air[vol]
    # 自上而下第一个非空气方块
    any_solid = solid.any(axis=0)
    top = np.where(any_solid, H - 1 - np.argmax(solid[::-1], axis=0), 0)
    top_id = np.take_along_axis(vol, top[None], axis=0)[0]
    rgb = lut[top_id].astype(np.float32)
    shade = 0.55 + 0.45 * np.clip(top / max(H - 1, 1), 0, 1)
    img = (rgb * shade[..., None]).clip(0, 255).astype(np.uint8)
    Image.fromarray(img).save(os.path.join(D, 'top.png'))
    hm = (np.clip((top - 3) / (H - 4), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(hm).save(os.path.join(D, 'height.png'))
    # 统计
    cnt = np.bincount(vol[4:].ravel(), minlength=len(names))
    order = np.argsort(-cnt)
    with open(os.path.join(D, 'blocks_top.txt'), 'w') as f:
        for i in order[:80]:
            if cnt[i] and not is_air[i]:
                f.write('%-45s %d\n' % (names[i], cnt[i]))
    # 每层占用数（找楼层）
    per_y = (~is_air[vol]).sum(axis=(1, 2))
    with open(os.path.join(D, 'per_y.txt'), 'w') as f:
        for y in range(H):
            f.write('%3d %d\n' % (y, per_y[y]))
    print('ok', top.min(), top.max())
elif mode == 'slice':
    y = int(sys.argv[3])
    if len(sys.argv) >= 8:
        xa, za, xb, zb = map(int, sys.argv[4:8])
    else:
        xa, za, xb, zb = 0, 0, X, Z
    scale = int(sys.argv[8]) if len(sys.argv) >= 9 else 2
    sl = vol[y, za:zb, xa:xb]
    below = vol[y - 1, za:zb, xa:xb]
    rgb = lut[sl].astype(np.float32)
    air = is_air[sl]
    # 空气处显示下面一层（地板）并压暗，便于读平面图
    rgb[air] = lut[below][air] * 0.45
    img = Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).resize(((xb - xa) * scale, (zb - za) * scale), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for gx in range(0, xb - xa, 16):
        d.line([(gx * scale, 0), (gx * scale, img.height)], fill=(255, 0, 0) if (gx + xa) % 64 == 0 else (90, 0, 0))
    for gz in range(0, zb - za, 16):
        d.line([(0, gz * scale), (img.width, gz * scale)], fill=(255, 0, 0) if (gz + za) % 64 == 0 else (90, 0, 0))
    out = os.path.join(D, 'slice_%d_%d_%d.png' % (y, xa, za))
    img.save(out)
    print(out)
