class_name TestCase
extends RefCounted
## 测试基类。tests/**/test_*.gd 继承它，写 test_ 开头的方法（可以 await）。
## 由 tools/run_tests.gd 发现并运行；断言失败不会中断当前测试，最后统一汇总。
##
## 断言描述里写清楚期望值的来历，实际值由断言自动附上。

var tree: SceneTree
var _failures: PackedStringArray = []
var _checks := 0
var _owned: Array[Node] = []


## 每个测试前后的钩子（可覆盖）。
func before_each() -> void:
	pass


func after_each() -> void:
	pass


func check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_failures.append(msg)


func eq(actual: Variant, expected: Variant, msg: String) -> void:
	_checks += 1
	var same: bool = is_equal_approx(actual, expected) if (actual is float or expected is float) else actual == expected
	if not same:
		_failures.append("%s（期望 %s，实际 %s）" % [msg, str(expected), str(actual)])


func near(actual: float, expected: float, tol: float, msg: String) -> void:
	_checks += 1
	if absf(actual - expected) > tol:
		_failures.append("%s（期望 %s±%s，实际 %s）" % [msg, expected, tol, actual])


func fail(msg: String) -> void:
	_failures.append(msg)


## 把节点挂到场景树上，测试结束自动释放。
func add_node(n: Node) -> Node:
	tree.root.add_child(n)
	_owned.append(n)
	return n


func wait_frames(n: int = 1) -> void:
	for i in n:
		await tree.process_frame


func _cleanup() -> void:
	for n in _owned:
		if is_instance_valid(n):
			n.queue_free()
	_owned.clear()
