class_name AssetManifest
extends Resource
## 资源清单：地址 → 路径。由 tools/build_manifest.gd 扫描生成到 res://data/asset_manifest.tres，不要手改。
## 地址规则见 ManifestBuilder.ROOTS（根目录前缀 + 相对路径去扩展名）。
## 换美术时只要新资源放在同一地址（同目录同名），或在生成后的清单里改路径，业务代码不用动。

## 地址 → res:// 路径
@export var paths: Dictionary = {}
## 地址 → 依赖的 res:// 路径（构建时记录，用于校验）
@export var deps: Dictionary = {}


func has(address: String) -> bool:
	return paths.has(address)


func path_of(address: String) -> String:
	return paths.get(address, "")


func addresses() -> PackedStringArray:
	var out := PackedStringArray(paths.keys())
	out.sort()
	return out


## 前缀匹配的全部地址（如 "fx/"）。
func with_prefix(prefix: String) -> PackedStringArray:
	var out := PackedStringArray()
	for a in paths:
		if (a as String).begins_with(prefix):
			out.append(a)
	out.sort()
	return out
