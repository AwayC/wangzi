extends TestCase
## UI 框架：返回栈、弹窗遮罩、返回键、缓存 / 销毁、生命周期、按压回弹、通用面板。

const NormalA = preload("res://tests/fixtures/ui_normal_a.gd")
const NormalB = preload("res://tests/fixtures/ui_normal_b.gd")
const PopupP = preload("res://tests/fixtures/ui_popup.gd")
const ConfirmPopup = preload("res://ui/panels/common/confirm_popup.gd")
const LoadingPanel = preload("res://ui/panels/common/loading_panel.gd")
const ToastPanel = preload("res://ui/panels/common/toast_panel.gd")


func before_each() -> void:
	await App.wait_ready()
	for s in [NormalA, NormalB, PopupP]:
		var root := Control.new()
		root.set_script(s)
		var btn := Button.new()
		btn.name = "Btn"
		root.add_child(btn)
		btn.owner = root
		var ps := PackedScene.new()
		ps.pack(root)
		root.free()
		UI.register_scene(s.get_script_constant_map()["PANEL"]["address"], ps)


func after_each() -> void:
	UI.close_all()
	await tree.create_timer(0.3).timeout


func test_normal_stack_and_back() -> void:
	var a = UI.open(NormalA, {"x": 1})
	check(a != null and a.is_open, "打开 A")
	eq(a.created, 1, "A 的 _on_create 调用一次")
	eq(a.last_args, {"x": 1}, "参数传给 _on_open")
	check(a.get_parent() == UI.layer_root(UILayer.NORMAL), "A 挂在 NORMAL 层")
	var b = UI.open(NormalB)
	eq(UI.normal_stack_size(), 2, "栈里 2 个界面")
	check(not a.visible and b.visible, "打开 B 时隐藏（不关闭）A")
	check(a.is_open, "A 仍是打开状态")
	check(UI.back(), "返回键处理了")
	await tree.create_timer(0.2).timeout
	check(not UI.is_open(NormalB), "返回关闭栈顶 B")
	check(a.visible, "关闭 B 后恢复 A")
	check(UI.get_panel(NormalB) == null, "B 是 cache=false，关闭后销毁")
	check(not UI.back(), "只剩栈底界面时返回键不处理")
	check(UI.is_open(NormalA), "栈底界面不被返回键关闭")


func test_popup_mask() -> void:
	UI.open(NormalA)
	check(not UI.is_mask_visible(), "没有弹窗时没有遮罩")
	var p = UI.open(PopupP)
	check(UI.is_mask_visible(), "打开弹窗出现遮罩")
	var mask := UI.layer_root(UILayer.POPUP).get_node("PopupMask")
	check(mask.get_index() < p.get_index(), "遮罩在弹窗下面")
	UI.back()
	await tree.create_timer(0.2).timeout
	check(not UI.is_mask_visible(), "关闭弹窗后遮罩消失")
	check(UI.is_open(NormalA), "返回先关弹窗，不关下面的界面")


func test_cache_and_reopen() -> void:
	# 缓存面板会跨测试保留（UI 是常驻服务），所以按增量断言
	var a = UI.open(NormalA)
	var opened0: int = a.opened
	var closed0: int = a.closed
	a.close()
	await tree.create_timer(0.2).timeout
	check(not a.visible, "cache=true 关闭后隐藏")
	var a2 = UI.open(NormalA)
	check(a2 == a, "再次打开复用同一实例")
	eq(a.created, 1, "复用时不再 _on_create")
	eq(a.opened - opened0, 1, "复用时再次 _on_open")
	eq(a.closed - closed0, 1, "关闭调用 _on_close")


func test_press_bounce_attached() -> void:
	var a = UI.open(NormalA)
	check(a.get_node("Btn").has_node("PressBounce"), "面板内按钮自动挂上按压回弹")


func test_common_panels() -> void:
	var confirmed := [false]
	var c = UI.confirm("要溜进机房吗？", func(): confirmed[0] = true)
	check(c != null and UI.is_open(ConfirmPopup), "确认弹窗打开")
	eq(c.get_node("%Text").text, "要溜进机房吗？", "弹窗文字")
	c.get_node("%ConfirmBtn").pressed.emit()
	check(confirmed[0], "点确定触发回调")
	check(not UI.is_open(ConfirmPopup), "点确定后关闭")
	var l = UI.open(LoadingPanel, {"title": "进入市第一中学"})
	l.set_progress(0.4)
	near(l.progress(), 0.4, 0.001, "加载进度")
	eq(l.get_node("%Title").text, "进入市第一中学", "加载标题")
	UI.toast("第一条")
	UI.toast("第二条")
	var t = UI.get_panel(ToastPanel)
	eq(t.pending(), 2, "飘字排队 2 条")
	eq(t.get_node("%Message").text, "第一条", "先显示第一条")
