extends Node
## UI 管理（autoload "UI"）：分层根节点、面板加载 / 缓存、NORMAL 返回栈、POPUP 模态遮罩、快捷入口。
## 对应 KiHan 的 UIManager。
##
##   UI.open(ConfirmPopup, {"text": "确定吗？", "on_confirm": cb})
##   UI.close(panel) / UI.close_type(ConfirmPopup) / UI.back() / UI.close_layer(UILayer.HUD)
##   UI.get_panel(LoadingPanel) / UI.is_open(LoadingPanel)
##   UI.toast("提示") / UI.confirm("确定吗？", on_confirm, on_cancel)
##
## 面板脚本约定见 UIPanel。面板场景按 PANEL.address 通过 Assets 加载；
## 测试或运行时生成的面板可先 register_scene(地址, PackedScene)。

const SERVICE_DEPS: Array[StringName] = [&"Assets"]
const MASK_COLOR := Color(0, 0, 0, 0.6)

const ToastPanel = preload("res://ui/panels/common/toast_panel.gd")
const ConfirmPopup = preload("res://ui/panels/common/confirm_popup.gd")

var _layers := {}  # layer:int -> Control（该层的根）
var _panels := {}  # Script -> UIPanel
var _scenes := {}  # address -> PackedScene
var _normal_stack: Array[UIPanel] = []
var _popups: Array[UIPanel] = []
var _mask: ColorRect


func setup() -> void:
	for layer in UILayer.ALL:
		var cl := CanvasLayer.new()
		cl.layer = layer
		cl.name = "Layer_" + UILayer.name_of(layer)
		add_child(cl)
		var root := Control.new()
		root.name = "Root"
		root.set_anchors_preset(Control.PRESET_FULL_RECT)
		root.mouse_filter = Control.MOUSE_FILTER_IGNORE
		cl.add_child(root)
		_layers[layer] = root
	_mask = ColorRect.new()
	_mask.name = "PopupMask"
	_mask.color = MASK_COLOR
	_mask.set_anchors_preset(Control.PRESET_FULL_RECT)
	_mask.mouse_filter = Control.MOUSE_FILTER_STOP
	_mask.visible = false
	_layers[UILayer.POPUP].add_child(_mask)


func register_scene(address: String, scene: PackedScene) -> void:
	_scenes[address] = scene


func layer_root(layer: int) -> Control:
	return _layers.get(layer)


# ---------------- 打开 / 关闭 ----------------

func open(panel_script: Script, args: Variant = null) -> UIPanel:
	var meta := _meta(panel_script)
	if meta.is_empty():
		return null
	var panel: UIPanel = _panels.get(panel_script)
	if panel == null or not is_instance_valid(panel):
		panel = _instantiate(meta["address"], panel_script)
		if panel == null:
			return null
		var root: Control = _layers[meta["layer"]]
		root.add_child(panel)
		panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		_panels[panel_script] = panel
		panel._ui_create(meta["layer"])
	match panel.layer:
		UILayer.NORMAL:
			if not _normal_stack.is_empty() and _normal_stack[-1] != panel:
				_normal_stack[-1].visible = false
			_normal_stack.erase(panel)
			_normal_stack.append(panel)
		UILayer.POPUP:
			_popups.erase(panel)
			_popups.append(panel)
	panel.get_parent().move_child(panel, -1)
	panel._ui_open(args)
	_refresh_mask()
	return panel


func close(panel: UIPanel) -> void:
	if panel == null or not is_instance_valid(panel) or not panel.is_open:
		return
	var was_normal_top := panel.layer == UILayer.NORMAL and not _normal_stack.is_empty() and _normal_stack[-1] == panel
	_normal_stack.erase(panel)
	_popups.erase(panel)
	var script: Script = panel.get_script()
	var cache: bool = _meta(script).get("cache", true)
	panel._ui_close(func():
		if not is_instance_valid(panel) or panel.is_open:
			return  # 隐藏动画期间被重新打开
		if cache:
			panel.visible = false
		else:
			_panels.erase(script)
			panel._ui_release()
			panel.queue_free())
	if was_normal_top and not _normal_stack.is_empty():
		_normal_stack[-1].visible = true
	_refresh_mask()


func close_type(panel_script: Script) -> void:
	close(get_panel(panel_script))


## 返回：关闭最上层弹窗；没有弹窗时关闭 NORMAL 栈顶（栈底界面不关）。返回是否处理了。
func back() -> bool:
	if not _popups.is_empty():
		close(_popups[-1])
		return true
	if _normal_stack.size() > 1:
		close(_normal_stack[-1])
		return true
	return false


## 关闭某一层的全部面板（流程切换时用）。
func close_layer(layer: int) -> void:
	for p in _panels.values():
		if is_instance_valid(p) and p.is_open and p.layer == layer:
			close(p)


func close_all() -> void:
	for layer in UILayer.ALL:
		close_layer(layer)


func get_panel(panel_script: Script) -> UIPanel:
	var p: UIPanel = _panels.get(panel_script)
	return p if p != null and is_instance_valid(p) else null


func is_open(panel_script: Script) -> bool:
	var p := get_panel(panel_script)
	return p != null and p.is_open


func normal_stack_size() -> int:
	return _normal_stack.size()


func is_mask_visible() -> bool:
	return _mask.visible


# ---------------- 快捷入口 ----------------

func toast(message: String) -> void:
	var t = get_panel(ToastPanel) if is_open(ToastPanel) else open(ToastPanel)
	if t:
		t.enqueue(message)


func confirm(text: String, on_confirm: Callable = Callable(), on_cancel: Callable = Callable()) -> UIPanel:
	return open(ConfirmPopup, {"text": text, "on_confirm": on_confirm, "on_cancel": on_cancel})


# ---------------- 内部 ----------------

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and back():
		get_viewport().set_input_as_handled()


func _meta(panel_script: Script) -> Dictionary:
	if panel_script == null:
		Log.error("UI", "面板脚本为空")
		return {}
	var consts := panel_script.get_script_constant_map()
	if not consts.has("PANEL"):
		Log.error("UI", "%s 没有声明 const PANEL" % panel_script.resource_path)
		return {}
	return consts["PANEL"]


func _instantiate(address: String, panel_script: Script) -> UIPanel:
	var scene: PackedScene = _scenes.get(address)
	if scene == null:
		scene = Assets.load(address) as PackedScene
	if scene == null:
		Log.error("UI", "找不到面板场景 %s" % address)
		return null
	var inst := scene.instantiate()
	if inst.get_script() != panel_script:
		Log.error("UI", "面板场景 %s 的根节点没有挂 %s" % [address, panel_script.resource_path])
		inst.free()
		return null
	return inst


func _refresh_mask() -> void:
	var tops := _popups.filter(func(p): return is_instance_valid(p) and p.is_open)
	if tops.is_empty():
		_mask.visible = false
		return
	var top: UIPanel = tops[-1]
	var root := _mask.get_parent()
	root.move_child(_mask, -1)
	root.move_child(top, -1)
	_mask.visible = true
