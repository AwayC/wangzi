extends Node
## 应用入口（autoload "App"，必须排在所有服务 autoload 之前）。
##
## 服务约定：服务 = 一个 autoload，脚本里声明
##     const SERVICE_DEPS: Array[StringName] = [&"Events", ...]   # 依赖的其他服务（autoload 名）
##     func setup() -> void: ...                                  # 初始化，可以 await
## App 在所有 autoload 进树后自动发现这些服务，按依赖拓扑排序，依次 await setup()，
## 全部就绪后发 services_ready；运行游戏时（非工具/测试脚本）再调用名为 Flow 的服务的 boot()（业务层的流程入口，存在时才调用）。
## 缺依赖或循环依赖会报错并退出。
##
## 其他代码需要等服务就绪时：await App.wait_ready()

signal services_ready

var is_ready := false
var _services := {}  # StringName -> Node
var _order: Array = []


func _ready() -> void:
	_boot.call_deferred()


func _boot() -> void:
	var deps := {}
	for n in get_tree().root.get_children():
		if n == self or n.get_script() == null:
			continue
		var consts: Dictionary = n.get_script().get_script_constant_map()
		if not consts.has("SERVICE_DEPS"):
			continue
		var key := StringName(n.name)
		_services[key] = n
		deps[key] = consts["SERVICE_DEPS"]
	var r := ServiceGraph.resolve(deps)
	if r["error"] != "":
		Log.error("App", r["error"])
		get_tree().quit(1)
		return
	_order = r["order"]
	for key in _order:
		var t0 := Time.get_ticks_usec()
		var svc: Node = _services[key]
		if svc.has_method("setup"):
			await svc.setup()
		Log.debug("App", "服务 %s 就绪（%.1f ms）" % [key, (Time.get_ticks_usec() - t0) / 1000.0])
	is_ready = true
	Log.info("App", "服务全部就绪: %s" % ", ".join(_order.map(func(k): return str(k))))
	services_ready.emit()
	if not is_tool_run() and _services.has(&"Flow"):
		_services[&"Flow"].boot()


func wait_ready() -> void:
	if not is_ready:
		await services_ready


func service(key: StringName) -> Node:
	return _services.get(key)


func service_order() -> Array:
	return _order.duplicate()


## 是否在跑工具/测试脚本（--script），这时只初始化服务，不启动游戏流程。
func is_tool_run() -> bool:
	return get_tree().get_script() != null
