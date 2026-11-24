extends SceneTree
## 资源校验（tools/test.sh 会自动运行）：
##   1. 清单是最新的（与重新扫描的结果一致）；
##   2. 清单里每个地址的文件都存在，记录的依赖都存在；
##   3. 业务代码（game/ ui/）里没有绕过 Assets 直接加载资源目录的路径（preload 脚本 .gd 不算）；
##   4. 每个面板场景：根节点挂了面板脚本、PANEL.address 与场景位置一致、脚本里的 %名字 在场景里都存在。
## 输出 OK / ERR 行，最后一行 RESULT errors=N；有错误时退出码为 1。

const CODE_DIRS := ["res://game", "res://ui"]
## 业务代码中禁止出现的直接加载（必须通过 Assets 地址）
const FORBIDDEN := ["load(\"res://assets/", "load(\"res://scenes/", "load(\"res://ui/panels/"]

var errors := 0


func _init() -> void:
	_check_manifest()
	_check_code()
	_check_panels.call_deferred()


func _finish() -> void:
	print("RESULT errors=%d" % errors)
	quit(1 if errors > 0 else 0)


## 面板校验要加载面板脚本（引用了 UI 等 autoload），所以放到 call_deferred 里。
func _check_panels() -> void:
	var m := ManifestBuilder.build()
	var count := 0
	var re := RegEx.create_from_string("@onready\\s+var\\s+\\w+[^=]*=\\s*%(\\w+)")
	for address in m.with_prefix("ui/"):
		var path := m.path_of(address)
		if not path.ends_with(".tscn"):
			continue
		count += 1
		var inst := (load(path) as PackedScene).instantiate()
		var script: Script = inst.get_script()
		if script == null or not inst.has_method("_ui_create"):  # 不用 `is UIPanel`：会在 _init 阶段提前编译依赖 autoload 的脚本
			_err("%s 的根节点没有挂 UIPanel 面板脚本" % path)
			inst.free()
			continue
		var meta: Dictionary = script.get_script_constant_map().get("PANEL", {})
		if meta.get("address", "") != address:
			_err("%s 的 PANEL.address 是 \"%s\"，应为 \"%s\"" % [script.resource_path, meta.get("address", ""), address])
		for mt in re.search_all(script.source_code):
			var uname := mt.get_string(1)
			if inst.get_node_or_null("%" + uname) == null:
				_err("%s 引用了 %%%s，但场景里没有这个唯一名称节点" % [script.resource_path, uname])
		inst.free()
	print("OK 检查面板 %d 个" % count)
	_finish()


func _err(msg: String) -> void:
	errors += 1
	print("ERR " + msg)


func _check_manifest() -> void:
	if not ResourceLoader.exists(ManifestBuilder.MANIFEST_PATH):
		_err("没有资源清单，运行 tools/build_manifest.gd")
		return
	var saved: AssetManifest = load(ManifestBuilder.MANIFEST_PATH)
	var fresh := ManifestBuilder.build()
	for a in fresh.paths:
		if not saved.paths.has(a):
			_err("清单过期：缺少新资源 %s（运行 tools/build_manifest.gd）" % a)
		elif saved.paths[a] != fresh.paths[a]:
			_err("清单过期：%s 路径已变为 %s" % [a, fresh.paths[a]])
	for a in saved.paths:
		if not fresh.paths.has(a):
			_err("清单过期：%s 对应的文件已不存在（运行 tools/build_manifest.gd）" % a)
	for a in fresh.deps:
		for d in fresh.deps[a]:
			if not ResourceLoader.exists(d) and not FileAccess.file_exists(d):
				_err("%s 依赖的 %s 不存在" % [a, d])
	print("OK 清单 %d 个地址" % fresh.paths.size())


func _check_code() -> void:
	var files: Array[String] = []
	for d in CODE_DIRS:
		_collect(d, files)
	for f in files:
		var text := FileAccess.get_file_as_string(f)
		var lines := text.split("\n")
		for i in lines.size():
			if lines[i].contains(".gd\"") or lines[i].strip_edges().begins_with("#"):
				continue
			for pat in FORBIDDEN:
				if lines[i].contains(pat):
					_err("%s:%d 直接加载资源路径，请改用 Assets 地址：%s" % [f, i + 1, lines[i].strip_edges()])
	print("OK 检查代码 %d 个文件" % files.size())


func _collect(dir_path: String, out: Array[String]) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		_collect(dir_path.path_join(sub), out)
	for f in dir.get_files():
		if f.ends_with(".gd"):
			out.append(dir_path.path_join(f))
