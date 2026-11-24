class_name UIPanel
extends Control
## 面板基类（全屏界面 / 弹窗 / HUD）。由 UI（UIManager）加载、挂到层级下并驱动生命周期，
## 面板自己不 show / hide / queue_free 自己，关闭用 close()。
##
## 每个面板脚本必须声明：
##   const PANEL := {"address": "ui/<模块>/<文件名>", "layer": UILayer.POPUP, "cache": true}
##   address 是面板场景的资源地址（res://ui/panels/<模块>/<文件名>.tscn）；cache=false 时关闭即销毁。
## 打开：UI.open(XxxPanel, 参数)
##
## 生命周期（子类覆盖）：
##   _on_create()      实例化后只调一次（%节点已就绪、按钮已挂按压回弹；在这里连接按钮信号）
##   _on_open(args)    每次打开（显示动画前）
##   _on_close()       每次关闭（隐藏动画前；断开 _on_open 里的订阅）
##   _on_release()     销毁前
##
## 节点绑定：在 .tscn 里把节点设为“唯一名称”(%)，脚本里写
##   @onready var _ok_btn: Button = %ConfirmBtn
## tools/validate_assets.gd 会检查每个 %名字 在面板场景里都存在。

var is_open := false
var layer := 0
var _transition: UITransition
var _created := false


func _on_create() -> void:
	pass


func _on_open(_args: Variant) -> void:
	pass


func _on_close() -> void:
	pass


func _on_release() -> void:
	pass


## 关闭自己
func close() -> void:
	UI.close(self)


# ---- 以下由 UIManager 调用 ----

func _ui_create(p_layer: int) -> void:
	if _created:
		return
	_created = true
	layer = p_layer
	for c in get_children():
		if c is UITransition:
			_transition = c
			break
	PressBounce.attach_to_buttons(self)
	_on_create()


func _ui_open(args: Variant) -> void:
	is_open = true
	visible = true
	_on_open(args)
	if _transition:
		_transition.play(true, Callable())


func _ui_close(on_hidden: Callable) -> void:
	if not is_open:
		return
	is_open = false
	_on_close()
	if _transition and is_visible_in_tree():
		_transition.play(false, on_hidden)
	else:
		on_hidden.call()


func _ui_release() -> void:
	_on_release()
