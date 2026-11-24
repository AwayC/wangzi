extends UIPanel
## 通用确认弹窗。用 UI.confirm(text, on_confirm, on_cancel) 打开，或
##   UI.open(ConfirmPopup, {"text", "on_confirm", "on_cancel", "confirm_text", "cancel_text", "show_cancel"})
## 按返回键关闭时不触发任何回调。

const PANEL := {"address": "ui/common/confirm_popup", "layer": UILayer.POPUP, "cache": true}

@onready var _text: Label = %Text
@onready var _confirm_btn: Button = %ConfirmBtn
@onready var _cancel_btn: Button = %CancelBtn

var _args := {}


func _on_create() -> void:
	_confirm_btn.pressed.connect(_on_confirm)
	_cancel_btn.pressed.connect(_on_cancel)


func _on_open(args: Variant) -> void:
	_args = args if args is Dictionary else {}
	_text.text = _args.get("text", "")
	_confirm_btn.text = _args.get("confirm_text", "确定")
	_cancel_btn.text = _args.get("cancel_text", "取消")
	_cancel_btn.visible = _args.get("show_cancel", true)


func _on_confirm() -> void:
	var cb = _args.get("on_confirm", Callable())
	close()
	if cb is Callable and cb.is_valid():
		cb.call()


func _on_cancel() -> void:
	var cb = _args.get("on_cancel", Callable())
	close()
	if cb is Callable and cb.is_valid():
		cb.call()
