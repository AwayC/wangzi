extends UIPanel
## 测试用面板（tests/core/test_ui.gd）：记录生命周期调用次数。
const PANEL := {"address": "test/ui_popup", "layer": UILayer.POPUP, "cache": true}
var created := 0
var opened := 0
var closed := 0
var last_args: Variant = null


func _on_create() -> void:
	created += 1


func _on_open(args: Variant) -> void:
	opened += 1
	last_args = args


func _on_close() -> void:
	closed += 1
