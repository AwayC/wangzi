class_name PressBounce
extends Node
## 按钮 Q 弹按压：按下缩到 0.88，松开回弹并小幅过冲（对应 KiHan 的 UIPressBounce）。
## UIManager 打开面板前会自动给面板内所有按钮挂上；运行时动态生成的按钮调用 PressBounce.attach_to_buttons(root)。
## 有特殊按压设计的按钮：在按钮上设置元数据 ui_no_bounce = true，自动挂载会跳过它。

const META_SKIP := &"ui_no_bounce"

@export var pressed_scale := 0.88
@export var press_time := 0.06
@export var release_time := 0.28

var _btn: BaseButton
var _tw: Tween


static func attach_to_buttons(root: Node) -> void:
	for b in root.find_children("*", "BaseButton", true, false):
		if b.get_meta(META_SKIP, false) or b.has_node("PressBounce"):
			continue
		var pb := PressBounce.new()
		pb.name = "PressBounce"
		b.add_child(pb)


func _ready() -> void:
	_btn = get_parent() as BaseButton
	if _btn == null:
		return
	_btn.button_down.connect(_down)
	_btn.button_up.connect(_up)
	_btn.resized.connect(_center)
	_center()


func _center() -> void:
	_btn.pivot_offset = _btn.size / 2.0


func _down() -> void:
	if _btn.disabled:
		return
	_animate(Vector2.ONE * pressed_scale, press_time, Tween.TRANS_QUAD)


func _up() -> void:
	_animate(Vector2.ONE, release_time, Tween.TRANS_BACK)


func _animate(to: Vector2, t: float, trans: Tween.TransitionType) -> void:
	if _tw and _tw.is_valid():
		_tw.kill()
	_tw = _btn.create_tween().set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	_tw.tween_property(_btn, "scale", to, t).set_trans(trans).set_ease(Tween.EASE_OUT)
