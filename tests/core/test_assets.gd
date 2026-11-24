extends TestCase
## 资源清单、地址加载、加载组进度与持有、对象池、自动回收。
## 使用 tests/fixtures 下的测试资源和测试专用清单，不依赖任何业务资源。

const ProbeScript = preload("res://tests/fixtures/pool_probe.gd")

var _saved_manifest: AssetManifest


func before_each() -> void:
	await App.wait_ready()
	_saved_manifest = Assets.manifest
	var m := AssetManifest.new()
	m.paths = {
		"test/a": "res://tests/fixtures/asset_a.tscn",
		"test/b": "res://tests/fixtures/asset_b.tscn",
		"test/c": "res://tests/fixtures/asset_c.tscn",
	}
	Assets.set_manifest(m)


func after_each() -> void:
	Assets.set_manifest(_saved_manifest)
	Assets.set_provider(AssetProvider.new())


func test_manifest_and_addresses() -> void:
	check(Assets.has("test/a"), "清单里有测试资源")
	eq(Assets.path_of("test/a"), "res://tests/fixtures/asset_a.tscn", "地址 → 路径")
	eq(ManifestBuilder.address_of("res://assets/fx/dust.tscn"), "fx/dust", "资源地址规则：assets/ 下去掉前缀和扩展名")
	eq(ManifestBuilder.address_of("res://ui/panels/common/toast_panel.tscn"), "ui/common/toast_panel", "面板地址规则")
	eq(ManifestBuilder.address_of("res://data/levels/school.tres"), "data/levels/school", "数据地址规则")
	eq(ManifestBuilder.address_of("res://core/x.gd"), "", "不在资源根目录下的路径没有地址")
	eq(ManifestBuilder.dep_path("uid://abc::PackedScene::res://a/b.tscn"), "res://a/b.tscn", "解析依赖条目")
	check(Assets.load("no/such/address") == null, "不存在的地址返回 null")
	var n := Assets.instantiate("test/a")
	check(n is Node3D and n.name == "AssetA", "按地址实例化场景")
	if n:
		n.free()
	check(_saved_manifest.has("ui/common/confirm_popup"), "正式清单里登记了通用面板")


func test_load_async() -> void:
	var res: Resource = await Assets.load_async("test/b")
	check(res is PackedScene, "异步加载得到 PackedScene：%s" % res)


func test_threaded_provider() -> void:
	Assets.set_provider(ThreadedAssetProvider.new())
	var res: Resource = await Assets.load_async("test/c")
	check(res is PackedScene, "线程 Provider 后台加载：%s" % res)
	await Assets.load_addresses(PackedStringArray(["test/a"]), "thread_group")
	check(Assets.is_retained("test/a"), "线程 Provider 加载组持有资源")
	Assets.release("thread_group")


func test_load_group_progress_and_release() -> void:
	var seen: Array[float] = []
	var cb := func(g: String, p: float): if g == "test_group": seen.append(p)
	Assets.group_progress.connect(cb)
	var group := LoadGroup.new()
	group.prefixes = PackedStringArray(["test/"])
	group.addresses = PackedStringArray(["no/such"])
	var list := group.resolve(Assets.manifest)
	eq(list.size(), 4, "前缀展开 3 个测试资源 + 1 个明确地址：%s" % [list])
	await Assets.load_addresses(list, "test_group")
	Assets.group_progress.disconnect(cb)
	check(seen.size() >= 1, "至少发出一次进度")
	eq(seen[-1], 1.0, "最后进度为 1")
	var mono := true
	for i in range(1, seen.size()):
		if seen[i] < seen[i - 1]:
			mono = false
	check(mono, "进度单调不减：%s" % [seen])
	check(Assets.is_retained("test/a"), "加载组持有资源")
	eq(Assets.held_by("test_group").size(), 3, "缺失地址不计入持有")
	Assets.release("test_group")
	check(not Assets.is_retained("test/a"), "释放后不再持有")


func _probe_scene(with_auto_recycle := 0.0) -> PackedScene:
	var root := Node3D.new()
	root.set_script(ProbeScript)
	if with_auto_recycle > 0.0:
		var ar := AutoRecycle.new()
		ar.duration = with_auto_recycle
		root.add_child(ar)
		ar.owner = root
	var ps := PackedScene.new()
	ps.pack(root)
	root.free()
	return ps


func test_pool_spawn_recycle() -> void:
	Pool.register_scene("test/probe", _probe_scene())
	Pool.prewarm("test/probe", 3, Pool.Category.FX)
	eq(Pool.available("test/probe"), 3, "预热 3 个")
	var parent := add_node(Node3D.new())
	var a = Pool.spawn("test/probe", parent)
	var b = Pool.spawn("test/probe", parent)
	eq(Pool.available("test/probe"), 1, "取出 2 个后剩 1")
	eq(Pool.active_count("test/probe"), 2, "在用 2 个")
	eq(a.spawned, 1, "取出时调用 _on_spawn")
	check(a.get_parent() == parent, "挂到指定父节点")
	Pool.recycle(a)
	Pool.recycle(a)
	eq(a.recycled, 1, "重复归还只算一次")
	check(not a.is_inside_tree(), "归还后离开场景树")
	eq(Pool.available("test/probe"), 2, "归还后空闲 2 个")
	var c = Pool.spawn("test/probe", parent)
	check(c == a, "再次取出复用同一实例")
	eq(c.spawned, 2, "复用时再次调用 _on_spawn")
	Pool.recycle(b)
	Pool.recycle(c)
	Pool.clear_category(Pool.Category.FX)
	eq(Pool.available("test/probe"), 0, "按类别清理空闲实例")


func test_pool_from_manifest() -> void:
	var parent := add_node(Node3D.new())
	var n := Pool.spawn("test/b", parent)
	check(n != null and n.name == "AssetB", "池空时按清单地址实例化")
	Pool.recycle(n)
	eq(Pool.available("test/b"), 1, "归还进池")
	Pool.clear_all()


func test_auto_recycle() -> void:
	Pool.register_scene("test/probe_auto", _probe_scene(0.1))
	var parent := add_node(Node3D.new())
	var n = Pool.spawn("test/probe_auto", parent)
	check(n.is_inside_tree(), "刚取出在树上")
	await tree.create_timer(0.3).timeout
	check(not n.is_inside_tree(), "0.1 秒后自动归还")
	eq(Pool.available("test/probe_auto"), 1, "自动归还进池")
	Pool.clear_all()
