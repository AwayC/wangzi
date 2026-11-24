class_name UILayer
extends RefCounted
## UI 层级（值即 CanvasLayer.layer，越大越靠上）。对应 KiHan 的 UILayer。
##   HUD     局内 HUD：非模态、不进返回栈、返回键不关
##   NORMAL  全屏界面：返回栈，打开新界面时隐藏下面的
##   POPUP   弹窗：模态，最上层弹窗下自动放遮罩
##   TOAST   飘字提示
##   LOADING 切换加载界面
##   SYSTEM  系统级（调试、断线提示等）

const HUD := 10
const NORMAL := 20
const POPUP := 30
const TOAST := 40
const LOADING := 50
const SYSTEM := 60

const ALL := [HUD, NORMAL, POPUP, TOAST, LOADING, SYSTEM]


static func name_of(layer: int) -> String:
	match layer:
		HUD: return "Hud"
		NORMAL: return "Normal"
		POPUP: return "Popup"
		TOAST: return "Toast"
		LOADING: return "Loading"
		SYSTEM: return "System"
	return "Layer%d" % layer
