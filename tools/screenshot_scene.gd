extends SceneTree
## 渲染一个场景的截图（用场景里 current 的 Camera3D）。需要图形环境，不能加 --headless。
## 用法: $G --path . --script res://tools/screenshot_scene.gd -- <场景 res 路径> <输出 png 绝对路径> [宽 高 [相机节点名]]


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() < 2:
		push_error("用法: -- <scene> <out.png> [w h]")
		quit(2)
		return
	var w := int(a[2]) if a.size() > 3 else 1600
	var h := int(a[3]) if a.size() > 3 else 900
	var vp := SubViewport.new()
	vp.size = Vector2i(w, h)
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	get_root().add_child(vp)
	var ps: PackedScene = load(a[0])
	if ps == null:
		push_error("场景加载失败: " + a[0])
		quit(1)
		return
	var inst := ps.instantiate()
	vp.add_child(inst)
	if a.size() > 4:
		var cam := inst.find_child(a[4], true, false) as Camera3D
		if cam == null:
			push_error("找不到相机: " + a[4])
			quit(1)
			return
		cam.current = true
	for i in 8:
		await RenderingServer.frame_post_draw
	var err := vp.get_texture().get_image().save_png(a[1])
	print("RESULT ", "OK " if err == OK else "ERR ", a[1])
	quit(0 if err == OK else 1)
