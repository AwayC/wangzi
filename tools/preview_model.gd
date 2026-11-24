extends SceneTree
## 给一个模型（glb / tscn）在标准灯光下截图，评审用。需要图形环境，不能加 --headless。
## 用法: $G --path . --script res://tools/preview_model.gd -- <模型 res 路径> <输出 png 绝对路径> <相机 x,y,z> <看向 x,y,z> [宽 高 [fov]]
## 例: ... -- res://assets/env/campus/cuihua.glb /tmp/a.png 560,40,560 500,10,470


func _init() -> void:
	call_deferred("_run")


func _v3(s: String) -> Vector3:
	var p := s.split(",")
	return Vector3(float(p[0]), float(p[1]), float(p[2]))


func _run() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() < 4:
		push_error("用法: -- <模型> <out.png> <相机 x,y,z> <看向 x,y,z> [宽 高 [fov]]")
		quit(2)
		return
	var w := int(a[4]) if a.size() > 5 else 1600
	var h := int(a[5]) if a.size() > 5 else 1000
	var vp := SubViewport.new()
	vp.size = Vector2i(w, h)
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	get_root().add_child(vp)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.42, 0.60, 0.86)
	sm.sky_horizon_color = Color(0.80, 0.86, 0.92)
	sm.ground_horizon_color = Color(0.80, 0.86, 0.92)
	sm.ground_bottom_color = Color(0.55, 0.58, 0.6)
	sky.sky_material = sm
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.ambient_light_energy = 0.9
	e.ssao_enabled = true
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_white = 6.0
	env.environment = e
	vp.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -40, 0)
	sun.light_energy = 1.4
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 400.0
	vp.add_child(sun)
	var res = load(a[0])
	if res == null:
		push_error("加载失败: " + a[0])
		quit(1)
		return
	vp.add_child((res as PackedScene).instantiate())
	var cam := Camera3D.new()
	cam.fov = float(a[6]) if a.size() > 6 else 50.0
	cam.far = 2000.0
	vp.add_child(cam)
	cam.look_at_from_position(_v3(a[2]), _v3(a[3]))
	cam.current = true
	for i in 10:
		await RenderingServer.frame_post_draw
	var err := vp.get_texture().get_image().save_png(a[1])
	print("RESULT ", "OK " if err == OK else "ERR ", a[1])
	quit(0 if err == OK else 1)
