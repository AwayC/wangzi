class_name LoadGroup
extends Resource
## 加载组：进入某个流程前一次性加载（并持有）的一批资源，加载界面显示它的进度。
## 放在 res://data/load_groups/，地址如 "data/load_groups/level_school"。
## 对应 KiHan 的“开局预热，局内 0 IO”。

## 明确列出的地址
@export var addresses: PackedStringArray = []
## 前缀匹配（如 "fx/" 表示 assets/fx 下全部资源）
@export var prefixes: PackedStringArray = []
## 加载完成后要在对象池里预热的实例：{地址: 数量}
@export var prewarm: Dictionary = {}


## 展开成去重、排序后的地址列表。
func resolve(manifest: AssetManifest) -> PackedStringArray:
	var seen := {}
	for a in addresses:
		seen[a] = true
	for p in prefixes:
		for a in manifest.with_prefix(p):
			seen[a] = true
	for a in prewarm:
		seen[a] = true
	var out := PackedStringArray(seen.keys())
	out.sort()
	return out
