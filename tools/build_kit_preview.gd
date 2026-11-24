extends SceneTree
## 用教室套件（tools/blender/build_classroom_kit.py 的产物）拼一间 8 × 12 m 的预览教室，供美术评审与截图。
## 用法: $G --headless --path . --script res://tools/build_kit_preview.gd
## 输出: res://scenes/dev/kit_classroom.tscn（每次覆盖重建，不要手改）
##
## 套件朝向约定：模型正面朝 -Z。墙模块正面 = 室内一侧；rotation_degrees.y：
##   0 → 室内朝 -Z（放在 +Z 一侧的墙），180 → 室内朝 +Z，-90 → 室内朝 +X，90 → 室内朝 -X。

const OUT := "res://scenes/dev/kit_classroom.tscn"
const P := "res://assets/props/classroom/"
const E := "res://assets/env/teaching/"
const H := 3.4  # 层高

var _scene: Node3D


func _init() -> void:
	call_deferred("_run")


func _group(name: String) -> Node3D:
	var g := Node3D.new()
	g.name = name
	_scene.add_child(g)
	g.owner = _scene
	return g


func _put(parent: Node3D, path: String, pos: Vector3, rot_y := 0.0) -> Node3D:
	var ps: PackedScene = load(path)
	var n: Node3D = ps.instantiate()
	n.position = pos
	n.rotation_degrees.y = rot_y
	parent.add_child(n, true)
	n.owner = _scene
	return n


func _run() -> void:
	_scene = Node3D.new()
	_scene.name = "KitClassroom"

	# ---- 环境与灯光
	var env := WorldEnvironment.new()
	env.name = "WorldEnvironment"
	var e := Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.45, 0.62, 0.85)
	sm.sky_horizon_color = Color(0.80, 0.86, 0.92)
	sky.sky_material = sm
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.86, 0.88, 0.92)
	e.ambient_light_energy = 0.75
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_white = 6.0
	env.environment = e
	_scene.add_child(env)
	env.owner = _scene

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-38, -70, 0)  # 从左侧窗户斜照进来
	sun.light_energy = 1.4
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.shadow_enabled = true
	_scene.add_child(sun)
	sun.owner = _scene

	var fill := OmniLight3D.new()
	fill.name = "RoomFill"
	fill.position = Vector3(0, 2.8, 0)
	fill.omni_range = 9.0
	fill.light_energy = 0.6
	_scene.add_child(fill)
	fill.owner = _scene

	# ---- 地面、墙、天花
	var shell := _group("Shell")
	for x in [-2.0, 2.0]:
		for z in [-4.0, 0.0, 4.0]:
			_put(shell, E + "floor_tile_4m.glb", Vector3(x, 0, z))
		_put(shell, E + "wall_plain_4m.glb", Vector3(x, 0, -6), 180)  # 前墙（黑板）
		_put(shell, E + "wall_plain_4m.glb", Vector3(x, 0, 6), 0)  # 后墙
	for z in [-4.0, 0.0, 4.0]:
		_put(shell, E + "wall_window_4m.glb", Vector3(-4, 0, z), -90)  # 左侧外窗
	_put(shell, E + "wall_door_4m.glb", Vector3(4, 0, -4), 90)  # 右侧走廊：前门
	_put(shell, E + "wall_window_4m.glb", Vector3(4, 0, 0), 90)
	_put(shell, E + "wall_door_4m.glb", Vector3(4, 0, 4), 90)  # 后门
	_put(shell, E + "door_classroom.glb", Vector3(4, 0, -4), 90)
	_put(shell, E + "door_classroom.glb", Vector3(4, 0, 4), 90)
	var ceil := MeshInstance3D.new()
	ceil.name = "Ceiling"
	var pm := PlaneMesh.new()
	pm.size = Vector2(8, 12)
	pm.flip_faces = true
	var cm := StandardMaterial3D.new()
	cm.albedo_color = Color(0.95, 0.95, 0.93)
	cm.roughness = 1.0
	pm.material = cm
	ceil.mesh = pm
	ceil.position = Vector3(0, H, 0)
	shell.add_child(ceil)
	ceil.owner = _scene

	# ---- 讲台区
	var front := _group("Front")
	_put(front, E + "podium_platform.glb", Vector3(0, 0, -5.15), 180)
	_put(front, P + "podium.glb", Vector3(0, 0.2, -5.0), 180)
	_put(front, P + "blackboard.glb", Vector3(0, 1.05, -5.885), 180)
	_put(front, P + "wall_clock.glb", Vector3(0, 2.75, -5.9), 180)
	_put(front, P + "speaker_box.glb", Vector3(3.4, 2.85, -5.9), 180)

	# ---- 课桌椅：3 组 × 2 列 × 6 排
	var seats := _group("Seats")
	for gx in [-2.4, 0.0, 2.4]:
		for dx in [-0.31, 0.31]:
			for row in 6:
				var z := -3.4 + row * 1.15
				_put(seats, P + "desk_student.glb", Vector3(gx + dx, 0, z))
				_put(seats, P + "chair_student.glb", Vector3(gx + dx, 0, z + 0.42))

	# ---- 后排与天花
	var back := _group("Back")
	_put(back, P + "bookshelf.glb", Vector3(-2.6, 0, 5.75))
	_put(back, P + "bookshelf.glb", Vector3(-1.35, 0, 5.75))
	_put(back, P + "locker_steel.glb", Vector3(0.6, 0, 5.67))
	_put(back, P + "locker_steel.glb", Vector3(1.55, 0, 5.67))
	var top := _group("Ceiling")
	for x in [-1.0, 1.0]:
		for z in [-3.5, 0.0, 3.5]:
			_put(top, P + "ceiling_light.glb", Vector3(x, H, z), 90)
	for z in [-1.75, 1.75]:
		_put(top, P + "ceiling_fan.glb", Vector3(0, H, z))

	var cam := Camera3D.new()
	cam.name = "ReviewCamera"
	cam.fov = 62
	cam.position = Vector3(3.3, 2.5, 5.5)
	_scene.add_child(cam)
	cam.owner = _scene
	cam.look_at_from_position(cam.position, Vector3(-0.8, 0.9, -3.0))
	cam.current = true

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT.get_base_dir()))
	var ps := PackedScene.new()
	var err := ps.pack(_scene)
	if err == OK:
		err = ResourceSaver.save(ps, OUT)
	print("RESULT ", "OK " if err == OK else "ERR %d " % err, OUT)
	_scene.free()
	quit(0 if err == OK else 1)
