extends Node
## 全局事件总线（autoload "Events"）。
## 所有“跨系统”的事件都在这里集中声明成强类型信号：发送方 Events.xxx.emit(...)，接收方 Events.xxx.connect(...)。
## 不用字符串事件名，拼错会直接编译报错。系统内部的事件用该系统自己的信号，不要放这里。
##
## 新增事件的写法（业务层按需添加，并写清楚参数含义）：
##   ## 某学生被老师抓到（student: 学生节点，teacher: 老师节点）
##   signal student_caught(student: Node, teacher: Node)
##
## 当前框架层只定义与业务无关的通用事件。

const SERVICE_DEPS: Array[StringName] = []

## 游戏暂停状态变化
signal pause_changed(paused: bool)
## 界面提示文字（任何系统都可以发，HUD / Toast 负责显示）
signal notice(text: String)


func setup() -> void:
	pass
