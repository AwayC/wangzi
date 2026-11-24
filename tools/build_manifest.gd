extends SceneTree
## 扫描 assets/ scenes/ ui/panels/ data/ 生成资源清单 res://data/asset_manifest.tres。
## 新增、移动、删除资源后运行一次：
##   Godot --headless --path . --script res://tools/build_manifest.gd


func _init() -> void:
	DirAccess.make_dir_recursive_absolute("res://data")
	var m := ManifestBuilder.build()
	var err := ResourceSaver.save(m, ManifestBuilder.MANIFEST_PATH)
	print("asset_manifest.tres: %s，%d 个地址，%d 个有依赖" % [error_string(err), m.paths.size(), m.deps.size()])
	quit(0 if err == OK else 1)
