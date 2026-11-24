extends Node
## 资源管理（autoload "Assets"）：所有业务代码通过“地址”取资源，不直接写 res://assets/... 路径。
##
##   Assets.load("props/desk")                       同步加载（局外 / 预热阶段用）
##   await Assets.load_async("props/desk")           异步加载
##   Assets.instantiate("props/desk")                加载 PackedScene 并实例化
##   await Assets.load_group("data/load_groups/xxx")  加载并持有一组资源，进度见 group_progress
##   Assets.release("data/load_groups/xxx")           释放这一组的持有（引用归零后 Godot 自动卸载）
##
## “持有”（holder）：被某个持有者引用的资源不会被卸载；加载组以自己的地址作为持有者。
## 底层加载由 AssetProvider 完成，可用 set_provider() 替换。

const SERVICE_DEPS: Array[StringName] = []

signal group_progress(group: String, progress: float)

var manifest: AssetManifest = AssetManifest.new()
var _provider: AssetProvider = AssetProvider.new()
var _holds := {}  # holder -> {address: Resource}


func setup() -> void:
	if ResourceLoader.exists(ManifestBuilder.MANIFEST_PATH):
		manifest = ResourceLoader.load(ManifestBuilder.MANIFEST_PATH)
		Log.debug("Assets", "资源清单 %d 项" % manifest.paths.size())
	else:
		Log.warn("Assets", "没有资源清单，先运行 tools/build_manifest.gd")


func set_provider(p: AssetProvider) -> void:
	_provider = p


func set_manifest(m: AssetManifest) -> void:
	manifest = m


func has(address: String) -> bool:
	return manifest.has(address)


func path_of(address: String) -> String:
	return manifest.path_of(address)


func load(address: String) -> Resource:
	var path := _resolve(address)
	return _provider.load_now(path) if path != "" else null


func load_async(address: String) -> Resource:
	var path := _resolve(address)
	if path == "":
		return null
	if not _provider.supports_threads():
		await get_tree().process_frame
		return _provider.load_now(path)
	_provider.request(path)
	while true:
		var st := _provider.poll(path)
		if st["state"] == AssetProvider.State.LOADED:
			return _provider.take(path)
		if st["state"] == AssetProvider.State.FAILED:
			Log.error("Assets", "加载失败: %s (%s)" % [address, path])
			return null
		await get_tree().process_frame
	return null


func instantiate(address: String) -> Node:
	var res := self.load(address)
	if res is PackedScene:
		return (res as PackedScene).instantiate()
	Log.error("Assets", "%s 不是场景，不能实例化" % address)
	return null


## 加载 LoadGroup 资源（按地址）描述的整组资源，并以组地址为持有者持有它们。
func load_group(group_address: String) -> LoadGroup:
	var group := self.load(group_address) as LoadGroup
	if group == null:
		Log.error("Assets", "%s 不是 LoadGroup" % group_address)
		return null
	await load_addresses(group.resolve(manifest), group_address)
	return group


## 加载一批地址并以 holder 持有；过程中发 group_progress(holder, 0~1)，结束时一定发 1.0。
## Provider 不支持线程时每帧同步加载一项（分摊卡顿），支持时并行后台加载。
func load_addresses(addresses: PackedStringArray, holder: String) -> void:
	if not _provider.supports_threads():
		await _load_sequential(addresses, holder)
		return
	var pending := {}  # address -> path
	var progress := {}
	for a in addresses:
		var path := _resolve(a)
		if path == "":
			progress[a] = 1.0
			continue
		pending[a] = path
		progress[a] = 0.0
		_provider.request(path)
	var last := -1.0
	while not pending.is_empty():
		for a in pending.keys():
			var st := _provider.poll(pending[a])
			if st["state"] == AssetProvider.State.LOADING:
				progress[a] = st["progress"]
				continue
			if st["state"] == AssetProvider.State.LOADED:
				_hold(holder, a, _provider.take(pending[a]))
			else:
				Log.error("Assets", "加载失败: %s (%s)" % [a, pending[a]])
			progress[a] = 1.0
			pending.erase(a)
		var p := _average(progress)
		if p > last:
			last = p
			group_progress.emit(holder, p)
		if not pending.is_empty():
			await get_tree().process_frame
	if last < 1.0:
		group_progress.emit(holder, 1.0)


func _load_sequential(addresses: PackedStringArray, holder: String) -> void:
	var total := addresses.size()
	for i in total:
		var a := addresses[i]
		var path := _resolve(a)
		if path != "":
			var res := _provider.load_now(path)
			if res != null:
				_hold(holder, a, res)
			else:
				Log.error("Assets", "加载失败: %s (%s)" % [a, path])
		group_progress.emit(holder, float(i + 1) / total)
		if i < total - 1:
			await get_tree().process_frame
	if total == 0:
		group_progress.emit(holder, 1.0)


## 让 holder 持有某个地址的资源（同步加载）。
func retain(address: String, holder: String) -> Resource:
	var res := self.load(address)
	if res != null:
		_hold(holder, address, res)
	return res


## 释放 holder 持有的全部资源。
func release(holder: String) -> void:
	_holds.erase(holder)


func is_retained(address: String) -> bool:
	for h in _holds:
		if _holds[h].has(address):
			return true
	return false


func held_by(holder: String) -> PackedStringArray:
	return PackedStringArray(_holds.get(holder, {}).keys())


func _hold(holder: String, address: String, res: Resource) -> void:
	if not _holds.has(holder):
		_holds[holder] = {}
	_holds[holder][address] = res


func _resolve(address: String) -> String:
	var path := manifest.path_of(address)
	if path == "":
		Log.error("Assets", "清单里没有地址: %s（新增资源后要运行 tools/build_manifest.gd）" % address)
	return path


static func _average(d: Dictionary) -> float:
	if d.is_empty():
		return 1.0
	var s := 0.0
	for k in d:
		s += d[k]
	return s / d.size()
