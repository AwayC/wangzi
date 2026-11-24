class_name AutoRecycle
extends Node
## 挂在池化场景根节点下：每次被取出（进入场景树）后自动归还父节点。
##   duration > 0：到时归还；
##   duration = 0：等父节点下所有粒子（GPUParticles3D / CPUParticles3D）播完再归还。

@export var duration := 0.0

var _token := 0


func _enter_tree() -> void:
	_token += 1
	_arm.call_deferred(_token)


func _arm(token: int) -> void:
	if token != _token or not is_inside_tree():
		return
	if duration > 0.0:
		await get_tree().create_timer(duration, false).timeout
	else:
		for p in _particles(get_parent()):
			p.restart()
		for p in _particles(get_parent()):
			if p.emitting:
				await p.finished
	if token == _token and is_inside_tree():
		Pool.recycle(get_parent())


func _particles(root: Node) -> Array:
	var out := []
	for c in root.find_children("*", "", true, false):
		if c is GPUParticles3D or c is CPUParticles3D:
			out.append(c)
	return out
