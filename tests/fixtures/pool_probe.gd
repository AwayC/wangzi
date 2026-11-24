extends Node3D
## 测试用池化对象：记录 _on_spawn / _on_recycle 调用次数。
var spawned := 0
var recycled := 0


func _on_spawn() -> void:
	spawned += 1


func _on_recycle() -> void:
	recycled += 1
