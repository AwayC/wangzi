extends UIPanel
## 飘字提示（排队依次显示）。用 UI.toast("...") 调用，不直接 open。

const PANEL := {"address": "ui/common/toast_panel", "layer": UILayer.TOAST, "cache": true}
const SHOW_SECONDS := 2.2
const FADE_SECONDS := 0.3

@onready var _box: Control = %Box
@onready var _message: Label = %Message

var _queue: PackedStringArray = []
var _time := 0.0


func _on_create() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_box.visible = false


func enqueue(message: String) -> void:
	_queue.append(message)
	if _time <= 0.0:
		_next()


func pending() -> int:
	return _queue.size() + (1 if _time > 0.0 else 0)


func _process(delta: float) -> void:
	if _time <= 0.0:
		return
	_time -= delta
	_box.modulate.a = clampf(_time / FADE_SECONDS, 0.0, 1.0)
	if _time <= 0.0:
		_next()


func _next() -> void:
	if _queue.is_empty():
		_box.visible = false
		_time = 0.0
		return
	_message.text = _queue[0]
	_queue.remove_at(0)
	_box.visible = true
	_box.modulate.a = 1.0
	_time = SHOW_SECONDS
