class_name UITransition
extends Node
## 面板显示 / 隐藏动画：挂在面板根节点下（第一个 UITransition 子节点生效），没有则立即显示 / 隐藏。
## 动画在暂停时也播放（UI 不受游戏暂停影响）。

enum Kind { SCALE, FADE, SLIDE_LEFT, SLIDE_RIGHT, SLIDE_TOP, SLIDE_BOTTOM }

@export var kind: Kind = Kind.SCALE
@export var show_time := 0.18
@export var hide_time := 0.12

var _tween: Tween


func play(showing: bool, done: Callable) -> void:
	var c := get_parent() as Control
	if _tween and _tween.is_valid():
		_tween.kill()
	c.pivot_offset = c.size / 2.0
	var t := show_time if showing else hide_time
	_tween = c.create_tween().set_pause_mode(Tween.TWEEN_PAUSE_PROCESS).set_parallel(true)
	match kind:
		Kind.SCALE:
			if showing:
				c.scale = Vector2(0.85, 0.85)
				c.modulate.a = 0.0
			_tween.tween_property(c, "scale", Vector2.ONE if showing else Vector2(0.9, 0.9), t) \
				.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			_tween.tween_property(c, "modulate:a", 1.0 if showing else 0.0, t)
		Kind.FADE:
			if showing:
				c.modulate.a = 0.0
			_tween.tween_property(c, "modulate:a", 1.0 if showing else 0.0, t)
		_:
			var off := _slide_offset(c)
			if showing:
				c.position = off
			_tween.tween_property(c, "position", Vector2.ZERO if showing else off, t) \
				.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_tween.chain().tween_callback(func():
		if not showing:
			c.scale = Vector2.ONE
			c.modulate.a = 1.0
			c.position = Vector2.ZERO
		if done.is_valid():
			done.call())


func _slide_offset(c: Control) -> Vector2:
	match kind:
		Kind.SLIDE_LEFT: return Vector2(-c.size.x, 0)
		Kind.SLIDE_RIGHT: return Vector2(c.size.x, 0)
		Kind.SLIDE_TOP: return Vector2(0, -c.size.y)
	return Vector2(0, c.size.y)
