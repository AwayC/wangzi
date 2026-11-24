"""校园总平面图：在校园场景的俯视截图上标出关键点、监控、校门和翻墙点（LV-02 的决策图）。

用法:
  1. 先出俯视截图（TopCamera，1600 × 1000，正交 260 m 高、中心 (205, 116)）：
     $G --path . --script res://tools/screenshot_scene.gd -- res://scenes/levels/campus.tscn /绝对路径/top.png 1600 1000 TopCamera
  2. python3 -I tools/map/site_plan.py /绝对路径/top.png [输出 png]
关键点、监控的坐标读 data/map/campus_plots.json（游戏坐标：x 向东、z 向南，单位米）。
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

if len(sys.argv) < 2 or not sys.argv[1].endswith('.png'):
    print(__doc__)
    sys.exit(2)
TOP = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else 'docs/production/img/site_plan.png'
CFG = 'data/map/campus_plots.json'
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
W, H = 1600, 1000
CENTER = (205, 116)
SCALE = H / 260.0  # 像素 / 米


def P(x, z):
    return (W / 2 + (x - CENTER[0]) * SCALE, H / 2 + (z - CENTER[1]) * SCALE)


def main():
    cfg = json.load(open(CFG, encoding='utf-8'))
    ox, oz = cfg['origin_mc']
    img = Image.open(TOP).convert('RGB')
    if img.size != (W, H):
        sys.exit('俯视截图必须是 %d × %d' % (W, H))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 18)
    fs = ImageFont.truetype(FONT, 14)
    poly = [P(x - ox, z - oz) for x, z in cfg['wall']]
    d.line(poly + poly[:1], fill=(120, 60, 40), width=4)
    g = cfg['extras']['gate']  # 游戏坐标
    d.line([P(g['x'][0], g['z']), P(g['x'][1], g['z'])], fill=(250, 250, 250), width=8)
    gx, gz = P(sum(g['x']) / 2, g['z'])
    d.text((gx - 20, gz - 26), '校门', font=f, fill=(0, 0, 0))
    for k, (x, y, z, label) in cfg.get('cameras', {}).items():
        cx, cz = P(x, z)
        d.ellipse([cx - 9, cz - 9, cx + 9, cz + 9], fill=(25, 25, 25), outline=(255, 255, 255))
        d.text((cx - 4, cz - 9), k, font=fs, fill=(255, 255, 255))
    for k, (x, y, z, label) in cfg.get('points', {}).items():
        cx, cz = P(x, z)
        d.ellipse([cx - 13, cz - 13, cx + 13, cz + 13], fill=(40, 90, 200), outline=(255, 255, 255), width=2)
        d.text((cx - 6, cz - 12), k, font=f, fill=(255, 255, 255))
        bb = d.textbbox((cx + 16, cz - 10), label, font=fs)
        d.rectangle(bb, fill=(255, 255, 255))
        d.text((cx + 16, cz - 10), label, font=fs, fill=(20, 40, 120))
    bx, bz = W - 260, H - 40
    d.line([(bx, bz), (bx + 100 * SCALE, bz)], fill=(0, 0, 0), width=4)
    d.text((bx, bz + 6), '100 m', font=fs, fill=(0, 0, 0))
    d.text((20, H - 34), '北 ↑   蓝点 = 关键点，黑点 = 监控，红褐线 = 围墙', font=f, fill=(0, 0, 0))
    img.save(OUT)
    print('OK', OUT, img.size)


main()
