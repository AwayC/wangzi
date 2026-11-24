extends TestCase
## 服务依赖排序、App 启动、命令行参数。


func test_resolve_order() -> void:
	var r := ServiceGraph.resolve({&"UI": [&"Assets", &"Events"], &"Assets": [&"Events"], &"Events": [], &"Pool": [&"Assets"]})
	eq(r["error"], "", "无错误")
	var order: Array = r["order"]
	eq(order.size(), 4, "四个服务都排进去")
	check(order.find(&"Events") < order.find(&"Assets"), "Events 在 Assets 前：%s" % [order])
	check(order.find(&"Assets") < order.find(&"UI"), "Assets 在 UI 前：%s" % [order])
	check(order.find(&"Assets") < order.find(&"Pool"), "Assets 在 Pool 前：%s" % [order])
	# 同一输入结果稳定
	eq(ServiceGraph.resolve({&"B": [], &"A": [], &"C": [&"A"]})["order"], [&"A", &"B", &"C"], "同层按名字排序")


func test_resolve_errors() -> void:
	var missing := ServiceGraph.resolve({&"UI": [&"Assets"]})
	check(missing["error"].contains("Assets"), "缺依赖要报出名字：%s" % missing["error"])
	eq(missing["order"], [], "出错时 order 为空")
	var cycle := ServiceGraph.resolve({&"A": [&"B"], &"B": [&"C"], &"C": [&"A"], &"D": []})
	check(cycle["error"].contains("循环") and cycle["error"].contains("A") and not cycle["error"].contains("D"),
		"循环依赖只列出环上的服务：%s" % cycle["error"])


func test_app_boots_services() -> void:
	await App.wait_ready()
	check(App.is_ready, "App 就绪")
	check(App.service(&"Events") == Events, "能按名字取到 Events 服务")
	check(App.service_order().has(&"Events"), "启动顺序里有 Events：%s" % [App.service_order()])
	check(App.is_tool_run(), "测试运行时识别为工具模式（不启动游戏流程）")


func test_debug_args() -> void:
	var d := DebugArgs.parse(PackedStringArray(["--time-scale=40", "--log", "--start-phase=1", "junk"]))
	eq(d.get("time-scale"), "40", "键值参数")
	eq(d.get("log"), true, "开关参数")
	check(not d.has("junk"), "忽略非 -- 开头的参数")
	var saved := DebugArgs.all()
	DebugArgs.override(d)
	eq(DebugArgs.get_float("time-scale", 1.0), 40.0, "get_float")
	eq(DebugArgs.get_int("start-phase", 0), 1, "get_int")
	eq(DebugArgs.get_float("missing", 2.5), 2.5, "缺省值")
	eq(DebugArgs.get_str("log", "x"), "x", "开关参数取字符串时用缺省值")
	DebugArgs.override(saved)
