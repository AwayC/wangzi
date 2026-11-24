extends Node
## 对象池（autoload "Pool"）：局内频繁出现/消失的节点（特效、投射物、跳字、可复用角色）只取还，不反复实例化。
##
##   Pool.prewarm("fx/dust", 8, Pool.Category.FX)     开局预热
##   var n := Pool.spawn("fx/dust", parent)           取出并挂到 parent 下（池空时自动实例化）
##   Pool.recycle(n)                                   归还（从场景树移除，停止处理）
##   Pool.clear_category(Pool.Category.FX)             退出关卡时清理
##
## 池化节点可选实现 _on_spawn() / _on_recycle()（取出后 / 归还前调用）。
## 也可挂 AutoRecycle 子节点按时长或粒子结束自动归还。
## 不在清单里的场景（如运行时生成的）可先 register_scene(地址, PackedScene)。

const SERVICE_DEPS: Array[StringName] = [&"Assets"]

enum Category { DEFAULT, FX, ACTOR, UI, PROP }

const META_ADDR := &"_pool_address"
const META_CAT := &"_pool_category"

var _free := {}  # address -> Array[Node]（不在树上的空闲实例）
var _active := {}  # address -> int
var _scenes := {}  # address -> PackedScene


func setup() -> void:
	pass


func register_scene(address: String, scene: PackedScene) -> void:
	_scenes[address] = scene


func prewarm(address: String, count: int, category: Category = Category.DEFAULT) -> void:
	var need := count - available(address)
	for i in need:
		var n := _create(address, category)
		if n == null:
			return
		_free_list(address).append(n)


func spawn(address: String, parent: Node, category: Category = Category.DEFAULT) -> Node:
	var list := _free_list(address)
	var n: Node = list.pop_back() if not list.is_empty() else _create(address, category)
	if n == null:
		return null
	_active[address] = _active.get(address, 0) + 1
	parent.add_child(n)
	if n.has_method("_on_spawn"):
		n._on_spawn()
	return n


func recycle(n: Node) -> void:
	if n == null or not is_instance_valid(n):
		return
	if not n.has_meta(META_ADDR):
		Log.warn("Pool", "%s 不是从对象池取出的，直接释放" % n.name)
		n.queue_free()
		return
	var address: String = n.get_meta(META_ADDR)
	if _free_list(address).has(n):
		return  # 重复归还
	if n.has_method("_on_recycle"):
		n._on_recycle()
	if n.get_parent() != null:
		n.get_parent().remove_child(n)
	_active[address] = maxi(0, _active.get(address, 0) - 1)
	_free_list(address).append(n)


func available(address: String) -> int:
	return _free.get(address, []).size()


func active_count(address: String) -> int:
	return _active.get(address, 0)


## 释放某一类别的全部空闲实例（在用的实例由使用者自己归还或随场景释放）。
func clear_category(category: Category) -> void:
	for address in _free.keys():
		var keep: Array = []
		for n in _free[address]:
			if n.get_meta(META_CAT, Category.DEFAULT) == category:
				n.free()
			else:
				keep.append(n)
		_free[address] = keep


func clear_all() -> void:
	for address in _free:
		for n in _free[address]:
			n.free()
	_free.clear()
	_active.clear()


func _exit_tree() -> void:
	clear_all()


func _free_list(address: String) -> Array:
	if not _free.has(address):
		_free[address] = []
	return _free[address]


func _create(address: String, category: Category) -> Node:
	var scene: PackedScene = _scenes.get(address)
	if scene == null:
		scene = Assets.load(address) as PackedScene
	if scene == null:
		Log.error("Pool", "无法实例化 %s（不是场景或不在清单里）" % address)
		return null
	var n := scene.instantiate()
	n.set_meta(META_ADDR, address)
	n.set_meta(META_CAT, category)
	return n
