"""读取 MC 1.15 存档（Anvil），找出超平坦地面以上的建造区域，导出方块体素数据。
用法: python3 -I mc_scan.py <world目录> <输出目录>
输出: blocks.npy (y, z, x) 方块编号、palette.json 编号→方块名（带状态，如 minecraft:oak_stairs[facing=east,half=bottom,shape=straight]）、meta.json 范围信息
"""
import json, os, struct, sys, zlib
import numpy as np

WORLD, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

# ---------------- NBT ----------------
def read_nbt(buf, pos=0):
    tag = buf[pos]; pos += 1
    n = struct.unpack_from('>H', buf, pos)[0]; pos += 2 + n
    val, pos = read_payload(buf, pos, tag)
    return val

def read_payload(buf, pos, tag):
    if tag == 1: return struct.unpack_from('>b', buf, pos)[0], pos + 1
    if tag == 2: return struct.unpack_from('>h', buf, pos)[0], pos + 2
    if tag == 3: return struct.unpack_from('>i', buf, pos)[0], pos + 4
    if tag == 4: return struct.unpack_from('>q', buf, pos)[0], pos + 8
    if tag == 5: return struct.unpack_from('>f', buf, pos)[0], pos + 4
    if tag == 6: return struct.unpack_from('>d', buf, pos)[0], pos + 8
    if tag == 7:
        n = struct.unpack_from('>i', buf, pos)[0]; pos += 4
        return buf[pos:pos + n], pos + n
    if tag == 8:
        n = struct.unpack_from('>H', buf, pos)[0]; pos += 2
        return buf[pos:pos + n].decode('utf-8', 'replace'), pos + n
    if tag == 9:
        et = buf[pos]; n = struct.unpack_from('>i', buf, pos + 1)[0]; pos += 5
        out = []
        for _ in range(n):
            v, pos = read_payload(buf, pos, et); out.append(v)
        return out, pos
    if tag == 10:
        out = {}
        while True:
            t = buf[pos]; pos += 1
            if t == 0: return out, pos
            n = struct.unpack_from('>H', buf, pos)[0]; pos += 2
            name = buf[pos:pos + n].decode('utf-8', 'replace'); pos += n
            out[name], pos = read_payload(buf, pos, t)
    if tag == 11:
        n = struct.unpack_from('>i', buf, pos)[0]; pos += 4
        return np.frombuffer(buf, '>i4', n, pos), pos + 4 * n
    if tag == 12:
        n = struct.unpack_from('>i', buf, pos)[0]; pos += 4
        return np.frombuffer(buf, '>i8', n, pos).astype(np.int64).view(np.uint64), pos + 8 * n
    raise ValueError('bad tag %d' % tag)

# 1.15 BlockStates：位宽 max(4, ceil(log2(调色板长度)))，条目可以跨 long
def unpack(longs, bits, count=4096):
    idx = np.arange(count, dtype=np.uint64) * np.uint64(bits)
    li = (idx // 64).astype(np.int64); sh = idx % np.uint64(64)
    lo = longs[li] >> sh
    nxt = np.where(li + 1 < len(longs), li + 1, li)
    hi_shift = (np.uint64(64) - sh) % np.uint64(64)
    hi = np.where(sh + np.uint64(bits) > 64, longs[nxt] << hi_shift, np.uint64(0))
    return ((lo | hi) & np.uint64((1 << bits) - 1)).astype(np.int64)

# ---------------- 读取 ----------------
GROUND = {'minecraft:air', 'minecraft:cave_air', 'minecraft:bedrock', 'minecraft:dirt', 'minecraft:grass_block'}
palette_ids = {'minecraft:air': 0}
def pid(name):
    if name not in palette_ids:
        palette_ids[name] = len(palette_ids)
    return palette_ids[name]

# 保留建模需要的方块状态（朝向、上下半、门的合页等），写成 名字[k=v,...]
KEEP_PROPS = ('facing', 'half', 'type', 'hinge', 'open', 'axis', 'shape', 'north', 'south', 'east', 'west', 'up')
def block_name(p):
    props = p.get('Properties', {})
    kv = ','.join('%s=%s' % (k, props[k]) for k in KEEP_PROPS if k in props)
    return p['Name'] + ('[%s]' % kv if kv else '')

chunks = {}  # (cx, cz) -> 数组 (256, 16, 16) uint16
for fn in sorted(os.listdir(os.path.join(WORLD, 'region'))):
    if not fn.endswith('.mca'):
        continue
    data = open(os.path.join(WORLD, 'region', fn), 'rb').read()
    for i in range(1024):
        off = int.from_bytes(data[i * 4:i * 4 + 3], 'big') * 4096
        if off == 0:
            continue
        length = struct.unpack_from('>i', data, off)[0]
        comp = data[off + 4]
        raw = data[off + 5:off + 4 + length]
        if comp != 2:
            continue
        nbt = read_nbt(zlib.decompress(raw))
        lvl = nbt.get('Level', {})
        if lvl.get('Status') not in (None, 'full', 'postprocessed', 'heightmaps', 'spawn', 'light', 'features'):
            pass
        arr = np.zeros((256, 16, 16), np.uint16)
        built = False
        for sec in lvl.get('Sections', []):
            y = sec.get('Y', -1)
            if y < 0 or y > 15 or 'Palette' not in sec or 'BlockStates' not in sec:
                continue
            pal = [block_name(p) for p in sec['Palette']]
            bits = max(4, (len(pal) - 1).bit_length())
            ids = unpack(sec['BlockStates'], bits)
            mapping = np.array([pid(n) for n in pal], np.uint16)
            blk = mapping[np.clip(ids, 0, len(pal) - 1)].reshape(16, 16, 16)
            arr[y * 16:(y + 1) * 16] = blk
            if any(n not in GROUND for n in pal):
                built = True
        if built:
            chunks[(lvl['xPos'], lvl['zPos'])] = arr

names = [None] * len(palette_ids)
for n, i in palette_ids.items():
    names[i] = n
cxs = [c[0] for c in chunks]; czs = [c[1] for c in chunks]
print('建造区块数', len(chunks), '区块范围 x', min(cxs), max(cxs), ' z', min(czs), max(czs))

# 合成整体体素（只取有建造的区块包围盒）
x0, x1 = min(cxs) * 16, (max(cxs) + 1) * 16
z0, z1 = min(czs) * 16, (max(czs) + 1) * 16
ground = set(pid(n) for n in GROUND)
maxy = 0
for arr in chunks.values():
    occ = ~np.isin(arr, list(ground))
    ys = np.where(occ.any(axis=(1, 2)))[0]
    if len(ys): maxy = max(maxy, int(ys.max()))
H = maxy + 1
vol = np.zeros((H, z1 - z0, x1 - x0), np.uint16)
for (cx, cz), arr in chunks.items():
    vol[:, cz * 16 - z0:cz * 16 - z0 + 16, cx * 16 - x0:cx * 16 - x0 + 16] = arr[:H]
np.save(os.path.join(OUT, 'blocks.npy'), vol)
json.dump(names, open(os.path.join(OUT, 'palette.json'), 'w'), ensure_ascii=False)
json.dump({'x0': x0, 'z0': z0, 'height': H, 'size_x': x1 - x0, 'size_z': z1 - z0}, open(os.path.join(OUT, 'meta.json'), 'w'))
print('体素尺寸 (y,z,x)', vol.shape, '方块种类', len(names))
