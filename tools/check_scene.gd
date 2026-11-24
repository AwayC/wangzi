extends SceneTree
# 用法: Godot --headless --path <项目> --script res://tools/check_scene.gd -- res://scenes/x.tscn
func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var path: String = args[0] if args.size() > 0 else "res://scenes/main.tscn"
	var ps := load(path) as PackedScene
	if ps == null:
		push_error("load failed: " + path); quit(1); return
	var inst := ps.instantiate()
	print("OK ", path, " root=", inst.name, " nodes=", inst.get_child_count() + 1)
	inst.free()
	quit(0)
