extends UIPanel
## 切换加载界面。GameFlow 打开它并调用 set_progress(0~1)；args: {"title": "进入市第一中学"}

const PANEL := {"address": "ui/common/loading_panel", "layer": UILayer.LOADING, "cache": true}
const TIPS := [
	"小贴士：脱离老师视线 3 秒后坐回座位，就能混进人群。",
	"小贴士：熄灯后开手电很显眼，老师在更远的地方就能看到你。",
	"小贴士：按 Q 切换成 AI 步态，混在走廊人群里不容易被认出来。",
	"小贴士：06:00 前回到教室或宿舍，否则撤离系数会下降。",
	"小贴士：22:00 宿舍楼锁门，想通宵就得提前留在外面。",
]

@onready var _title: Label = %Title
@onready var _bar: ProgressBar = %Bar
@onready var _tip: Label = %Tip


func _on_open(args: Variant) -> void:
	var a: Dictionary = args if args is Dictionary else {}
	_title.text = a.get("title", "加载中……")
	_tip.text = TIPS.pick_random()
	set_progress(0.0)


func set_progress(p: float) -> void:
	_bar.value = clampf(p, 0.0, 1.0) * 100.0


func progress() -> float:
	return _bar.value / 100.0
