class_name ManifestBuilder
extends RefCounted
## 扫描资源目录生成 AssetManifest（build_manifest / validate_assets 共用）。

const MANIFEST_PATH := "res://data/asset_manifest.tres"

## 扫描根目录 → 地址前缀
const ROOTS := {
	"res://assets/": "",
	"res://scenes/": "scenes/",
	"res://ui/panels/": "ui/",
	"res://data/": "data/",
}

## 纳入清单的扩展名（导入类资源按源文件路径登记，load 时 Godot 自动走导入产物）
const EXTENSIONS := ["tscn", "scn", "tres", "res", "png", "jpg", "jpeg", "webp", "svg",
	"ogg", "wav", "mp3", "glb", "gltf", "fbx", "ttf", "otf"]


static func build() -> AssetManifest:
	var m := AssetManifest.new()
	for root in ROOTS:
		_scan(root, root, ROOTS[root], m)
	return m


## 由路径算地址；不在任何根目录下返回 ""。
static func address_of(path: String) -> String:
	for root in ROOTS:
		if path.begins_with(root):
			return ROOTS[root] + path.substr(root.length()).get_basename()
	return ""


static func _scan(dir_path: String, root: String, prefix: String, m: AssetManifest) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		if sub.begins_with("."):
			continue
		_scan(dir_path.path_join(sub), root, prefix, m)
	for f in dir.get_files():
		var path := dir_path.path_join(f)
		if path == MANIFEST_PATH or not EXTENSIONS.has(f.get_extension().to_lower()):
			continue
		var address := prefix + path.substr(root.length()).get_basename()
		if m.paths.has(address):
			push_error("地址冲突：%s 同时对应 %s 和 %s（同目录下不要有同名不同扩展名的资源）" % [address, m.paths[address], path])
			continue
		m.paths[address] = path
		var dep_paths := PackedStringArray()
		for d in ResourceLoader.get_dependencies(path):
			var p := dep_path(d)
			if p != "":
				dep_paths.append(p)
		if not dep_paths.is_empty():
			m.deps[address] = dep_paths


## get_dependencies 返回的条目形如 "uid://xxx::类型::res://路径"，取出 res:// 路径。
static func dep_path(entry: String) -> String:
	for part in entry.split("::"):
		if part.begins_with("res://"):
			return part
	return ""
