class_name UIView
extends Control
## 可复用部件基类（对应 KiHan 的 UIView）：对外只提供 bind / refresh 等少量入口，
## 外部不直接操作部件内部的子节点。部件内部节点同样用 %唯一名称 绑定。


## 绑定数据并刷新显示（子类覆盖）。
func bind(_data: Variant) -> void:
	pass


## 数据变化后刷新（子类覆盖）。只在数值真正变化时改 UI。
func refresh() -> void:
	pass
