"""按 MC 的布局和体量重建校园地块（data/map/campus_plots.json），每块导出一个 .gltf（+ .bin）到 assets/env/campus/，贴图共用 assets/env/campus/textures/。

用法:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/build_mc_campus.py -- <MC 扫描目录> [地块 id ...]
MC 扫描目录由 tools/mc/mc_scan.py 生成（python3 -I tools/mc/mc_scan.py ~/Downloads/world <输出目录>）。
之后要 $G --headless --path . --import，再跑 tools/build_campus.gd 拼场景。

每个 .gltf 里：
  <id>_building      建筑（多材质）
  <id>_*_leaves      树冠 / 绿篱（圆润化过）
  <id>_trunks        树干
  <id>_plants        草和花
  <id>-colonly       碰撞（Godot 导入成三角网格碰撞）
  <替换 id>          光滑圆塔 / 圆顶
门的位置另存到 data/map/campus_doors.json，识别出的房间（类型、范围、门）存到 data/map/campus_rooms.json（MC 坐标），拼场景时放门位、摆套件家具。
"""
import json
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mc_lib as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CFG = os.path.join(ROOT, 'data', 'map', 'campus_plots.json')
OUT_DIR = os.path.join(ROOT, 'assets', 'env', 'campus')
DOORS = os.path.join(ROOT, 'data', 'map', 'campus_doors.json')
ROOMS = os.path.join(ROOT, 'data', 'map', 'campus_rooms.json')


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if not argv:
        print('用法: -- <MC 扫描目录> [地块 id ...]')
        sys.exit(2)
    scan = argv[0]
    only = set(argv[1:])
    cfg = json.load(open(CFG, encoding='utf-8'))
    doors = json.load(open(DOORS, encoding='utf-8')) if os.path.exists(DOORS) else {}
    rooms = json.load(open(ROOMS, encoding='utf-8')) if os.path.exists(ROOMS) else {}
    for spec in cfg['plots']:
        if only and spec['id'] not in only:
            continue
        t0 = time.time()
        L.reset_scene()
        coll = bpy.context.scene.collection
        plot = L.Plot(scan, spec)
        rooms[spec['id']] = plot.detect_rooms(cfg.get('room_rules', {}))
        _, col = plot.build(coll)
        veg = plot.build_vegetation(coll, col)
        for r in spec.get('replace', []):
            if r['type'] == 'tower':
                L.build_tower(plot, r, coll, col)
            elif r['type'] == 'dome':
                L.build_dome(r, coll)
        col.build(spec['id'] + '-colonly', coll)
        out = os.path.join(OUT_DIR, spec['id'] + '.gltf')
        L.export_gltf(out)
        doors[spec['id']] = plot.doors
        print('OK %-10s %7d 面  植物对象 %d  门 %d  %.1fs → %s' % (spec['id'], L.tri_count(), len(veg), len(plot.doors), time.time() - t0, out))
    if not only or 'extras' in only:
        import campus_extras
        L.reset_scene()
        campus_extras.build(cfg, bpy.context.scene.collection)
        out = os.path.join(OUT_DIR, 'extras.gltf')
        L.export_gltf(out)
        print('OK extras     %7d 面  → %s' % (L.tri_count(), out))
    json.dump(doors, open(DOORS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(rooms, open(ROOMS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, rs in rooms.items():
        typed = [r['type'] for r in rs if r['type']]
        print('房间 %-8s 共 %d 间，摆家具 %d 间：%s' % (k, len(rs), len(typed), {t: typed.count(t) for t in set(typed)}))


main()
