class_name ServiceGraph
extends RefCounted
## 服务依赖排序（Kahn 拓扑排序，同层按名字排序保证结果稳定）。
## 输入 {服务名: [依赖的服务名, ...]}，输出 {order: [...], error: ""}；
## 依赖不存在或有循环时 order 为空、error 给出原因。


static func resolve(deps: Dictionary) -> Dictionary:
	for name in deps:
		for d in deps[name]:
			if not deps.has(d):
				return {"order": [], "error": "服务 %s 依赖的 %s 不存在" % [name, d]}
	var indegree := {}
	for name in deps:
		indegree[name] = deps[name].size()
	var ready: Array = []
	for name in deps:
		if indegree[name] == 0:
			ready.append(name)
	ready.sort_custom(_by_name)
	var order: Array = []
	while not ready.is_empty():
		var cur = ready.pop_front()
		order.append(cur)
		var unlocked: Array = []
		for name in deps:
			if deps[name].has(cur):
				indegree[name] -= 1
				if indegree[name] == 0:
					unlocked.append(name)
		unlocked.sort_custom(_by_name)
		ready.append_array(unlocked)
		ready.sort_custom(_by_name)
	if order.size() != deps.size():
		var stuck: Array = []
		for name in deps:
			if not order.has(name):
				stuck.append(str(name))
		stuck.sort_custom(_by_name)
		return {"order": [], "error": "服务存在循环依赖: %s" % ", ".join(stuck)}
	return {"order": order, "error": ""}


## StringName 的 < 不是字典序，排序前转成字符串比较。
static func _by_name(a, b) -> bool:
	return str(a) < str(b)
