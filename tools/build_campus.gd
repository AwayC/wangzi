extends SceneTree
## 拼校园场景：把按 MC 布局重建的地块（assets/env/campus/*.gltf，由 tools/blender/build_mc_campus.py 生成）
## 按 data/map/campus_plots.json 的位置摆好，再放新做的部件（extras.gltf：地面、围墙、校门、小卖部），加上门位、关键点、监控和评审机位。
## 用法: $G --headless --path . --script res://tools/build_campus.gd
## 输出: res://scenes/levels/campus.tscn（每次覆盖重建，不要手改）
##
## 坐标：游戏坐标 = MC 坐标 + 地块 offset - origin_mc；高度 = MC y - 4（草地顶面是 0，铺装地面是 1）。
## 关键点 points、监控 cameras 在配置里直接写游戏坐标。
## glb 里的几何体是 MC 绝对坐标，所以每个地块节点只需平移 offset - origin_mc。

const CFG := "res://data/map/campus_plots.json"
const DOORS := "res://data/map/campus_doors.json"
const OUT := "res://scenes/levels/campus.tscn"
const PLOT_DIR := "res://assets/env/campus/"
const ROOMS := "res://data/map/campus_rooms.json"
const KIT := {
	"desk": "res://assets/props/classroom/desk_student.glb", "chair": "res://assets/props/classroom/chair_student.glb",
	"podium": "res://assets/props/classroom/podium.glb", "blackboard": "res://assets/props/classroom/blackboard.glb",
	"clock": "res://assets/props/classroom/wall_clock.glb", "speaker": "res://assets/props/classroom/speaker_box.glb",
	"light": "res://assets/props/classroom/ceiling_light.glb", "fan": "res://assets/props/classroom/ceiling_fan.glb",
	"bookshelf": "res://assets/props/classroom/bookshelf.glb", "locker": "res://assets/props/classroom/locker_steel.glb",
	"platform": "res://assets/env/teaching/podium_platform.glb", "pc": "res://assets/props/office/computer_desk.glb",
	"office": "res://assets/props/office/office_desk.glb", "bunk": "res://assets/props/dorm/bunk_bed.glb",
	"table": "res://assets/props/canteen/canteen_table.glb",
}

var _scene: Node3D
var _font: SystemFont
var _origin := Vector2.ZERO
var _packed := {}
var _n_items := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var cfg = JSON.parse_string(FileAccess.get_file_as_string(CFG))
	var doors = JSON.parse_string(FileAccess.get_file_as_string(DOORS)) if FileAccess.file_exists(DOORS) else {}
	_origin = Vector2(cfg.origin_mc[0], cfg.origin_mc[1])
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Hiragino Sans GB", "PingFang SC", "STHeiti", "Microsoft YaHei", "Noto Sans CJK SC"])
	_scene = Node3D.new()
	_scene.name = "Campus"
	_scene.set_meta("source", CFG)
	_environment()

	var plots := _group(_scene, "Plots")
	var labels := _group(_scene, "Labels")
	var door_root := _group(_scene, "Doors")
	var n_plots := 0
	for p in cfg.plots:
		var path: String = PLOT_DIR + p.id + ".gltf"
		var ps := load(path) as PackedScene
		if ps == null:
			push_error("缺地块模型（先跑 build_mc_campus.py）: " + path)
			continue
		var n: Node3D = ps.instantiate()
		n.name = p.id
		n.position = Vector3(p.offset[0] - _origin.x, 0, p.offset[1] - _origin.y)
		n.set_meta("label", p.label)
		plots.add_child(n, true)
		n.owner = _scene
		n_plots += 1
		var b: Array = p.box
		var c := Vector3((b[0] + b[2]) / 2.0 + p.offset[0] - _origin.x, 0, (b[1] + b[3]) / 2.0 + p.offset[1] - _origin.y)
		_label(labels, p.label, c + Vector3(0, 45, 0), 160, 0.05)
		for d in doors.get(p.id, []):
			var m := Marker3D.new()
			m.position = Vector3(d.pos[0] + p.offset[0] - _origin.x, d.pos[1], d.pos[2] + p.offset[1] - _origin.y)
			m.set_meta("type", d.type)
			m.set_meta("facing", d.facing)
			m.set_meta("lock", "")
			_add(door_root, m, "Door")
			m.add_to_group("doors", true)

	var extras := load(PLOT_DIR + "extras.gltf") as PackedScene
	if extras:
		var ex: Node3D = extras.instantiate()
		ex.name = "extras"
		plots.add_child(ex, true)
		ex.owner = _scene
	else:
		push_error("缺 extras.gltf（先跑 build_mc_campus.py）")
	_furnish(cfg)
	_markers(cfg)
	_cameras(cfg)

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT.get_base_dir()))
	var out := PackedScene.new()
	var err := out.pack(_scene)
	if err == OK:
		err = ResourceSaver.save(out, OUT)
	print("地块 %d 个，门 %d 扇，套件家具 %d 件" % [n_plots, door_root.get_child_count(), _n_items])
	print("RESULT ", "OK " if err == OK else "ERR %d " % err, OUT)
	_scene.free()
	quit(0 if err == OK else 1)


func _g(mc: Array) -> Vector2:
	return Vector2(mc[0], mc[1]) - _origin


func _add(parent: Node, n: Node, n_name: String) -> Node:
	n.name = n_name
	parent.add_child(n, true)
	n.owner = _scene
	return n


func _group(parent: Node, n_name: String) -> Node3D:
	return _add(parent, Node3D.new(), n_name)


func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.95
	return m


func _box(parent: Node, n_name: String, center: Vector3, size: Vector3, mat: Material, basis := Basis()) -> void:
	var body := StaticBody3D.new()
	body.transform = Transform3D(basis, center)
	_add(parent, body, n_name)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	bm.material = mat
	mi.mesh = bm
	_add(body, mi, "Mesh")
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	_add(body, cs, "Shape")


func _label(parent: Node, text: String, pos: Vector3, size := 48, px := 0.02) -> void:
	var l := Label3D.new()
	l.text = text
	l.font = _font
	l.font_size = size
	l.outline_size = size / 5
	l.pixel_size = px
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.position = pos
	_add(parent, l, "Label")


## 按 campus_rooms.json 给分了类型的房间摆教室套件家具（Blender 重建时已清掉这些房间里的 MC 方块家具）。
## 房间局部坐标：z 沿长边，前墙（黑板）在 -z 端；x 沿短边。
func _furnish(cfg: Dictionary) -> void:
	if not FileAccess.file_exists(ROOMS):
		return
	var rooms = JSON.parse_string(FileAccess.get_file_as_string(ROOMS))
	var offs := {}
	for p in cfg.plots:
		offs[p.id] = Vector2(p.offset[0], p.offset[1])
	var root := _group(_scene, "Furniture")
	for plot_id in rooms:
		for r in rooms[plot_id]:
			if r.type == "":
				continue
			var off: Vector2 = offs.get(plot_id, Vector2.ZERO)
			var b: Array = r.get("rect", r.box)
			var x0: float = b[0] + off.x - _origin.x
			var z0: float = b[1] + off.y - _origin.y
			var x1: float = b[2] + off.x - _origin.x
			var z1: float = b[3] + off.y - _origin.y
			var g := _group(root, "%s_%dF_%s" % [plot_id, int(r.floor), r.type])
			g.set_meta("room", {"plot": plot_id, "floor": r.floor, "type": r.type})
			var along_x := (x1 - x0) > (z1 - z0)
			var room := {
				"c": Vector3((x0 + x1) / 2.0, r.y, (z0 + z1) / 2.0),
				"rot": 90.0 if along_x else 0.0,
				"L": maxf(x1 - x0, z1 - z0) - 0.2, "W": minf(x1 - x0, z1 - z0) - 0.2,
				"ceil": float(r.ceil) - float(r.y),
			}
			match r.type:
				"classroom":
					_classroom(g, room, false)
				"lab":
					_classroom(g, room, true)
				"office":
					_office(g, room)
				"dorm":
					_dorm(g, room)
				"canteen":
					_canteen(g, room)
			_lights(g, room, r.type)


func _kit(parent: Node, key: String, room: Dictionary, local: Vector3, rot := 0.0) -> void:
	if not _packed.has(key):
		_packed[key] = load(KIT[key])
	var n: Node3D = (_packed[key] as PackedScene).instantiate()
	var basis := Basis(Vector3.UP, deg_to_rad(room.rot))
	n.position = room.c + basis * local
	n.rotation_degrees.y = room.rot + rot
	parent.add_child(n, true)
	n.owner = _scene
	_n_items += 1


func _classroom(g: Node, room: Dictionary, lab: bool) -> void:
	var L: float = room.L
	var W: float = room.W
	var front := -L / 2.0
	var back := L / 2.0
	_kit(g, "platform", room, Vector3(0, 0, front + 0.85), 180)
	_kit(g, "podium", room, Vector3(0, 0.2, front + 1.0), 180)
	_kit(g, "blackboard", room, Vector3(0, 1.05, front + 0.12), 180)
	_kit(g, "clock", room, Vector3(0, 2.75, front + 0.1), 180)
	_kit(g, "speaker", room, Vector3(W / 2.0 - 0.6, 2.85, front + 0.1), 180)
	if lab:  # 机房：电脑桌一排排，每张两个座位
		var per := maxi(1, int((W - 1.0) / 1.45))
		var z := front + 2.8
		while z < back - 1.0:
			for i in per:
				var x := (i - (per - 1) / 2.0) * 1.45
				_kit(g, "pc", room, Vector3(x, 0, z), 0)
				for dx in [-0.3, 0.3]:
					_kit(g, "chair", room, Vector3(x + dx, 0, z + 0.55), 0)
			z += 1.6
	else:  # 教室：两两一组，组间留走道
		var groups := clampi(int((W - 1.2) / 2.4), 1, 4)
		var z := front + 2.6
		while z < back - 1.4:
			for i in groups:
				var gx := (i - (groups - 1) / 2.0) * 2.4
				for dx in [-0.31, 0.31]:
					_kit(g, "desk", room, Vector3(gx + dx, 0, z), 0)
					_kit(g, "chair", room, Vector3(gx + dx, 0, z + 0.42), 0)
			z += 1.15
	_kit(g, "bookshelf", room, Vector3(-W / 2.0 + 1.0, 0, back - 0.25), 0)
	_kit(g, "locker", room, Vector3(W / 2.0 - 1.0, 0, back - 0.33), 0)


func _office(g: Node, room: Dictionary) -> void:
	var L: float = room.L
	var W: float = room.W
	var pairs := clampi(int((L - 1.5) / 1.6), 1, 4)
	if W >= 2.8:
		for i in pairs:
			var z := (i - (pairs - 1) / 2.0) * 1.6
			_kit(g, "office", room, Vector3(-0.38, 0, z), 90)
			_kit(g, "office", room, Vector3(0.38, 0, z), -90)
			_kit(g, "chair", room, Vector3(-1.0, 0, z), 90)
			_kit(g, "chair", room, Vector3(1.0, 0, z), -90)
	else:
		_kit(g, "office", room, Vector3(0, 0, 0), 0)
	if L > 3.5:
		_kit(g, "locker", room, Vector3(-W / 2.0 + 0.5, 0, -L / 2.0 + 0.4), 180)
		_kit(g, "bookshelf", room, Vector3(W / 2.0 - 0.7, 0, -L / 2.0 + 0.3), 180)


func _dorm(g: Node, room: Dictionary) -> void:
	var L: float = room.L
	var W: float = room.W
	var n := clampi(int((L - 1.2) / 2.1), 1, 3)
	for side in [-1, 1]:
		if W < 3.0 and side > 0:
			continue
		for k in n:
			_kit(g, "bunk", room, Vector3(side * (W / 2.0 - 0.52), 0, -L / 2.0 + 1.15 + k * 2.1), 0)
	_kit(g, "desk", room, Vector3(-0.35, 0, L / 2.0 - 0.6), 180)
	_kit(g, "desk", room, Vector3(0.35, 0, L / 2.0 - 0.6), 180)
	_kit(g, "locker", room, Vector3(0, 0, -L / 2.0 + 0.33), 180)


func _canteen(g: Node, room: Dictionary) -> void:
	var L: float = room.L
	var W: float = room.W
	var x := -W / 2.0 + 2.5
	while x < W / 2.0 - 2.0:
		var z := -L / 2.0 + 3.0
		while z < L / 2.0 - 2.5:
			_kit(g, "table", room, Vector3(x, 0, z), 0)
			z += 2.6
		x += 2.6


## 吸顶日光灯：大约每 3 m 一盏；教室再加两台吊扇。
func _lights(g: Node, room: Dictionary, kind: String) -> void:
	var L: float = room.L
	var W: float = room.W
	var h: float = room.ceil
	var nl := maxi(1, int(L / 3.2))
	var nw := maxi(1, int(W / 3.2))
	for i in nl:
		for j in nw:
			_kit(g, "light", room, Vector3((j - (nw - 1) / 2.0) * W / nw, h, (i - (nl - 1) / 2.0) * L / nl), 90)
	if kind == "classroom" or kind == "lab":
		for z in [-L / 6.0, L / 6.0]:
			_kit(g, "fan", room, Vector3(0, h, z), 0)


func _markers(cfg: Dictionary) -> void:
	var g := _group(_scene, "Markers")
	for k in cfg.get("points", {}):
		var v: Array = cfg.points[k]
		var m := Marker3D.new()
		m.position = Vector3(v[0], v[1], v[2])
		m.set_meta("label", v[3])
		_add(g, m, "Point_" + k)
		m.add_to_group("map_points", true)
		_label(m, "%s %s" % [k, v[3]], Vector3(0, 3, 0), 64, 0.02)
	for k in cfg.get("cameras", {}):
		var v: Array = cfg.cameras[k]
		var m := Marker3D.new()
		m.position = Vector3(v[0], v[1], v[2])
		m.set_meta("label", v[3])
		_add(g, m, "CCTV_" + k)
		m.add_to_group("cctv", true)
		_label(m, "监控 %s" % k, Vector3(0, 0.8, 0), 48, 0.015)


func _environment() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.42, 0.60, 0.86)
	sm.sky_horizon_color = Color(0.80, 0.86, 0.92)
	sm.ground_horizon_color = Color(0.80, 0.86, 0.92)
	sm.ground_bottom_color = Color(0.55, 0.58, 0.60)
	sky.sky_material = sm
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.ambient_light_energy = 0.9
	e.ssao_enabled = true
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_white = 6.0
	env.environment = e
	_add(_scene, env, "WorldEnvironment")
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -40, 0)
	sun.light_energy = 1.4
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 500.0
	_add(_scene, sun, "Sun")


## 评审机位：OverviewCamera 是默认机位，其余在 campus_plots.json 的 review_cameras 里（游戏坐标）。
func _cameras(cfg: Dictionary) -> void:
	var g := _group(_scene, "ReviewCameras")
	for cdef in cfg.get("review_cameras", []):
		var cam := Camera3D.new()
		cam.fov = cdef[3]
		cam.far = 3000.0
		_add(g, cam, cdef[0])
		cam.look_at_from_position(Vector3(cdef[1][0], cdef[1][1], cdef[1][2]), Vector3(cdef[2][0], cdef[2][1], cdef[2][2]))
		cam.current = cdef[0] == "OverviewCamera"
	var top := Camera3D.new()
	top.projection = Camera3D.PROJECTION_ORTHOGONAL
	top.size = 260.0
	top.far = 3000.0
	_add(g, top, "TopCamera")
	top.look_at_from_position(Vector3(205, 400, 116.01), Vector3(205, 0, 116), Vector3(0, 0, -1))
