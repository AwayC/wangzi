extends SceneTree
## 拼装 v4.1 结构化校园场景：读取 data/map/campus_layout.json，加载 assets/env/campus/*.gltf 各模块，
## 为庭院与图书馆镜面水池挂载真实透明可涉水水体 ShaderMaterial，按 campus_rooms.json 自动布置室内套件家具
##（含高三楼阅览空间沙发/书架/海报、宿舍精简纯床位、宿舍 3F 自习室、萃华楼 1F 天文社与 3F 小机房），
## 并生成门位（doors 组）、关键点（map_points 组）、监控（cctv 组）与评审机位。
## 用法: $G --headless --path . --script res://tools/build_campus.gd

const CFG := "res://data/map/campus_layout.json"
const DOORS := "res://data/map/campus_doors.json"
const ROOMS := "res://data/map/campus_rooms.json"
const OUT := "res://scenes/levels/campus.tscn"
const MOD_DIR := "res://assets/env/campus/"
const KIT := {
	"desk": "res://assets/props/classroom/desk_student.glb", "chair": "res://assets/props/classroom/chair_student.glb",
	"podium": "res://assets/props/classroom/podium.glb", "blackboard": "res://assets/props/classroom/blackboard.glb",
	"clock": "res://assets/props/classroom/wall_clock.glb", "speaker": "res://assets/props/classroom/speaker_box.glb",
	"light": "res://assets/props/classroom/ceiling_light.glb", "fan": "res://assets/props/classroom/ceiling_fan.glb",
	"bookshelf": "res://assets/props/classroom/bookshelf.glb", "locker": "res://assets/props/classroom/locker_steel.glb",
	"platform": "res://assets/env/teaching/podium_platform.glb", "pc": "res://assets/props/office/computer_desk.glb",
	"office": "res://assets/props/office/office_desk.glb", "bunk": "res://assets/props/dorm/bunk_bed.glb",
	"table": "res://assets/props/canteen/canteen_table.glb", "sofa": "res://assets/props/classroom/reading_sofa.glb",
	# 从 assets/library/ 复用的书架与海报/公告栏模型
	"lib_bookrack": "res://assets/library/models/outside_object/prefab/book_rack_01_01.glb",
	"lib_rack": "res://assets/library/models/outside_object/prefab/rack_01_01.glb",
	"lib_board1": "res://assets/library/models/outside_object/prefab/board_01_01.glb",
	"lib_board2": "res://assets/library/models/outside_object/prefab/board_01_02.glb",
	"lib_poster": "res://assets/library/models/content/hot_pot/gong_gao_pai/zhai_bi_hua.glb",
}

const WATER_SHADER := """
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, specular_schlick_ggx;

uniform vec3 shallow_color : source_color = vec3(0.05, 0.44, 0.52);
uniform vec3 deep_color : source_color = vec3(0.02, 0.22, 0.34);
uniform sampler2D depth_tex : hint_depth_texture, filter_linear_mipmap;

float wave_h(vec2 p, float t) {
	return sin(p.x * 2.4 + t * 1.5) * 0.018 + cos(p.y * 3.1 - t * 1.2) * 0.018
		+ sin((p.x - p.y) * 5.2 + t * 2.1) * 0.009;
}

void fragment() {
	vec2 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xz;
	float e = 0.07;
	float h0 = wave_h(wp, TIME);
	float hx = wave_h(wp + vec2(e, 0.0), TIME);
	float hz = wave_h(wp + vec2(0.0, e), TIME);
	vec3 w_norm = normalize(vec3(h0 - hx, e * 1.5, h0 - hz));
	NORMAL = normalize((VIEW_MATRIX * vec4(w_norm, 0.0)).xyz);

	float raw_d = texture(depth_tex, SCREEN_UV).r;
	vec3 ndc = vec3(SCREEN_UV * 2.0 - 1.0, raw_d);
	vec4 view_p = INV_PROJECTION_MATRIX * vec4(ndc, 1.0);
	view_p.xyz /= view_p.w;
	float water_depth = clamp(-view_p.z + VERTEX.z, 0.0, 2.0);
	float depth_f = clamp(water_depth / 0.72, 0.0, 1.0);

	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = mix(shallow_color, deep_color, depth_f);
	METALLIC = 0.08;
	ROUGHNESS = 0.04;
	SPECULAR = 0.92;
	ALPHA = clamp(0.28 + depth_f * 0.30 + fresnel * 0.32, 0.24, 0.82);
}
"""

var _scene: Node3D
var _font: SystemFont
var _packed := {}
var _water_mat: ShaderMaterial
var _n_items := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var cfg = JSON.parse_string(FileAccess.get_file_as_string(CFG))
	var doors = JSON.parse_string(FileAccess.get_file_as_string(DOORS)) if FileAccess.file_exists(DOORS) else {}
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Hiragino Sans GB", "PingFang SC", "STHeiti", "Microsoft YaHei", "Noto Sans CJK SC"])
	var sh := Shader.new()
	sh.code = WATER_SHADER
	_water_mat = ShaderMaterial.new()
	_water_mat.shader = sh

	_scene = Node3D.new()
	_scene.name = "Campus"
	_scene.set_meta("source", CFG)
	_environment()

	var plots := _group(_scene, "Plots")
	var water_root := _group(_scene, "Water")
	var labels := _group(_scene, "Labels")
	var door_root := _group(_scene, "Doors")
	var n_mods := 0
	for mdef in cfg.modules:
		var mod_id: String = mdef.id
		var path: String = MOD_DIR + mod_id + ".gltf"
		var ps := load(path) as PackedScene
		if ps == null:
			push_error("缺模块模型（先跑 build_campus_v4.py）: " + path)
			continue
		var n: Node3D = ps.instantiate()
		n.name = mod_id
		n.set_meta("label", mdef.label)
		plots.add_child(n, true)
		n.owner = _scene
		n_mods += 1
		_setup_water_meshes(n, water_root)
		if mdef.label != "" and mdef.has("label_pos"):
			var lp: Array = mdef.label_pos
			_label(labels, mdef.label, Vector3(lp[0], lp[1], lp[2]), 130, 0.04)
		for d in doors.get(mod_id, []):
			var dm := Marker3D.new()
			dm.position = Vector3(d.pos[0], d.pos[1], d.pos[2])
			dm.set_meta("type", d.type)
			dm.set_meta("facing", d.facing)
			dm.set_meta("lock", d.get("lock", ""))
			_add(door_root, dm, "Door")
			dm.add_to_group("doors", true)

	_furnish()
	_markers(cfg)
	_cameras(cfg)

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT.get_base_dir()))
	var out := PackedScene.new()
	var err := out.pack(_scene)
	if err == OK:
		err = ResourceSaver.save(out, OUT)
	print("模块 %d 个，门 %d 扇，套件家具 %d 件" % [n_mods, door_root.get_child_count(), _n_items])
	print("RESULT ", "OK " if err == OK else "ERR %d " % err, OUT)
	_scene.free()
	quit(0 if err == OK else 1)


func _setup_water_meshes(mod_node: Node3D, water_root: Node3D) -> void:
	var found: Array[MeshInstance3D] = []
	_collect_water(mod_node, found)
	if found.is_empty():
		return
	_scene.set_editable_instance(mod_node, true)
	for mi in found:
		var w := MeshInstance3D.new()
		w.mesh = mi.mesh
		w.transform = mod_node.transform * mi.transform
		w.material_override = _water_mat
		w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_add(water_root, w, mi.name)
		mi.visible = false


func _collect_water(n: Node, out: Array[MeshInstance3D]) -> void:
	if n is MeshInstance3D and n.name.ends_with("_water"):
		out.append(n as MeshInstance3D)
	for c in n.get_children():
		_collect_water(c, out)


func _add(parent: Node, n: Node, n_name: String) -> Node:
	n.name = n_name
	parent.add_child(n, true)
	n.owner = _scene
	return n


func _group(parent: Node, n_name: String) -> Node3D:
	return _add(parent, Node3D.new(), n_name)


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


func _furnish() -> void:
	if not FileAccess.file_exists(ROOMS):
		return
	var rooms = JSON.parse_string(FileAccess.get_file_as_string(ROOMS))
	var root := _group(_scene, "Furniture")
	for mod_id in rooms:
		for r in rooms[mod_id]:
			if r.type == "":
				continue
			var b: Array = r.box
			var x0: float = b[0]
			var z0: float = b[1]
			var x1: float = b[2]
			var z1: float = b[3]
			var g := _group(root, "%s_%dF_%s" % [mod_id, int(r.floor), r.type])
			g.set_meta("room", {"module": mod_id, "floor": r.floor, "type": r.type})
			var along_x := (x1 - x0) > (z1 - z0)
			var rot_deg: float = float(r.rot) if r.has("rot") else (90.0 if along_x else 0.0)
			var span_x := x1 - x0
			var span_z := z1 - z0
			var room_l := span_x if absf(fmod(absf(rot_deg), 180.0) - 90.0) < 1.0 else span_z
			var room_w := span_z if absf(fmod(absf(rot_deg), 180.0) - 90.0) < 1.0 else span_x
			var room := {
				"c": Vector3((x0 + x1) / 2.0, r.y, (z0 + z1) / 2.0),
				"rot": rot_deg,
				"L": room_l - 0.2, "W": room_w - 0.2,
				"ceil": float(r.ceil) - float(r.y),
			}
			match r.type:
				"classroom":
					_classroom(g, room, false)
				"lab":
					_classroom(g, room, true)
				"small_lab":
					_small_lab(g, room)
				"astronomy":
					_astronomy(g, room)
				"reading_lounge":
					_reading_lounge(g, room)
				"study_room":
					_study_room(g, room)
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
	_kit(g, "clock", room, Vector3(0, 2.55, front + 0.1), 180)
	_kit(g, "speaker", room, Vector3(W / 2.0 - 0.6, 2.65, front + 0.1), 180)
	if lab:
		var per := maxi(1, int((W - 1.0) / 1.45))
		var z := front + 2.65
		while z < back - 1.0:
			for i in per:
				var x := (i - (per - 1) / 2.0) * 1.45
				_kit(g, "pc", room, Vector3(x, 0, z), 0)
				for dx in [-0.3, 0.3]:
					_kit(g, "chair", room, Vector3(x + dx, 0, z + 0.55), 0)
			z += 1.55
	else:
		var groups := clampi(int((W - 1.2) / 2.3), 1, 3)
		var z := front + 2.55
		while z < back - 1.15:
			for i in groups:
				var gx := (i - (groups - 1) / 2.0) * 2.25
				for dx in [-0.31, 0.31]:
					_kit(g, "desk", room, Vector3(gx + dx, 0, z), 0)
					_kit(g, "chair", room, Vector3(gx + dx, 0, z + 0.42), 0)
			z += 1.15
	_kit(g, "bookshelf", room, Vector3(-W / 2.0 + 0.9, 0, back - 0.25), 0)
	_kit(g, "locker", room, Vector3(W / 2.0 - 0.9, 0, back - 0.33), 0)


func _reading_lounge(g: Node, room: Dictionary) -> void:
	# 高三楼西端阅览空间（rot=0: +X 为东墙，-X 为西墙）：
	# 东墙摆满 library 书架，西墙贴 library 公告板与海报，中间摆阅读沙发！
	var W: float = room.W
	for z in [-2.0, 0.0, 2.0]:
		_kit(g, "lib_bookrack", room, Vector3(W / 2.0 - 0.28, 0.0, z), -90)
	_kit(g, "lib_board2", room, Vector3(-W / 2.0 + 0.04, 1.45, -1.8), 90)
	_kit(g, "lib_board1", room, Vector3(-W / 2.0 + 0.04, 1.45, 0.3), 90)
	_kit(g, "lib_poster", room, Vector3(-W / 2.0 + 0.05, 1.50, 2.1), 90)
	_kit(g, "sofa", room, Vector3(-W / 2.0 + 0.55, 0.0, -1.3), -90)
	_kit(g, "sofa", room, Vector3(-W / 2.0 + 0.55, 0.0, 1.1), -90)


func _study_room(g: Node, room: Dictionary) -> void:
	# 宿舍 3F 转角玻璃自习室：放自习书桌、椅子与书架！
	var W: float = room.W
	var L: float = room.L
	_kit(g, "lib_bookrack", room, Vector3(W / 2.0 - 0.28, 0.0, 0.0), -90)
	for dx in [-0.45, 0.25]:
		for dz in [-0.55, 0.55]:
			_kit(g, "desk", room, Vector3(dx, 0.0, dz), 0 if dz < 0 else 180)
			_kit(g, "chair", room, Vector3(dx, 0.0, dz - 0.42 if dz < 0 else dz + 0.42), 0 if dz < 0 else 180)
	_kit(g, "bookshelf", room, Vector3(-W / 2.0 + 0.85, 0.0, L / 2.0 - 0.28), 0)


func _small_lab(g: Node, room: Dictionary) -> void:
	# 萃华楼 3F 圆塔中段小机房（rot=0：东西长条，靠北墙并排摆 3 台竞赛电脑桌，南侧留通道直通东门）
	for x in [-1.5, 0.0, 1.5]:
		_kit(g, "pc", room, Vector3(x, 0.0, -0.82), 0)
		_kit(g, "chair", room, Vector3(x - 0.28, 0.0, -0.28), 0)
		_kit(g, "chair", room, Vector3(x + 0.28, 0.0, -0.28), 0)
	_kit(g, "locker", room, Vector3(2.55, 0.0, 0.95), 180)


func _astronomy(g: Node, room: Dictionary) -> void:
	# 萃华楼 1F 圆塔南半整间天文社：中央大桌、两台电脑桌、讲台暗格与书架
	_kit(g, "table", room, Vector3(0.2, 0.0, 0.2), 0)
	_kit(g, "pc", room, Vector3(-0.8, 0.0, -1.6), 0)
	_kit(g, "chair", room, Vector3(-0.8, 0.0, -1.05), 0)
	_kit(g, "pc", room, Vector3(0.9, 0.0, -1.6), 0)
	_kit(g, "chair", room, Vector3(0.9, 0.0, -1.05), 0)
	_kit(g, "podium", room, Vector3(-1.2, 0.0, 1.4), 90)
	_kit(g, "bookshelf", room, Vector3(1.5, 0.0, 1.6), 180)


func _office(g: Node, room: Dictionary) -> void:
	var L: float = room.L
	var W: float = room.W
	var pairs := clampi(int((L - 1.5) / 1.7), 1, 3)
	if W >= 2.8:
		for i in pairs:
			var z := (i - (pairs - 1) / 2.0) * 1.7
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
	# 按标注：寝室去掉书桌，只放两侧上下铺床，中间留紧凑过人走道！
	var L: float = room.L
	var W: float = room.W
	var n := clampi(int((L - 0.3) / 2.05), 1, 2)
	for side in [-1, 1]:
		if W < 2.6 and side > 0:
			continue
		for k in n:
			var z_pos := (k - (n - 1) / 2.0) * 2.05
			_kit(g, "bunk", room, Vector3(side * (W / 2.0 - 0.52), 0, z_pos), 0)


func _canteen(g: Node, room: Dictionary) -> void:
	var L: float = room.L
	var W: float = room.W
	var x := -W / 2.0 + 2.2
	while x < W / 2.0 - 1.8:
		var z := -L / 2.0 + 2.4
		while z < L / 2.0 - 2.0:
			_kit(g, "table", room, Vector3(x, 0, z), 0)
			z += 2.6
		x += 2.7


func _lights(g: Node, room: Dictionary, kind: String) -> void:
	if kind == "astronomy":
		return
	var L: float = room.L
	var W: float = room.W
	var h: float = room.ceil
	var nl := maxi(1, int(L / 3.4))
	var nw := maxi(1, int(W / 3.4))
	for i in nl:
		for j in nw:
			_kit(g, "light", room, Vector3((j - (nw - 1) / 2.0) * W / nw, h, (i - (nl - 1) / 2.0) * L / nl), 90)
	if kind == "classroom" or kind == "lab":
		for z in [-L / 5.5, L / 5.5]:
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
		_label(m, "%s %s" % [k, v[3]], Vector3(0, 2.6, 0), 56, 0.018)
	for k in cfg.get("cameras", {}):
		var v: Array = cfg.cameras[k]
		var m := Marker3D.new()
		m.position = Vector3(v[0], v[1], v[2])
		m.set_meta("label", v[3])
		_add(g, m, "CCTV_" + k)
		m.add_to_group("cctv", true)
		_label(m, "监控 %s" % k, Vector3(0, 0.7, 0), 44, 0.014)


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
	sun.directional_shadow_max_distance = 400.0
	_add(_scene, sun, "Sun")


func _cameras(cfg: Dictionary) -> void:
	var g := _group(_scene, "ReviewCameras")
	for cdef in cfg.get("review_cameras", []):
		var cam := Camera3D.new()
		cam.fov = cdef[3]
		cam.far = 2000.0
		_add(g, cam, cdef[0])
		cam.look_at_from_position(Vector3(cdef[1][0], cdef[1][1], cdef[1][2]), Vector3(cdef[2][0], cdef[2][1], cdef[2][2]))
		cam.current = cdef[0] == "OverviewCamera"
	var tc: Dictionary = cfg.get("top_camera", {"center": [110, 78], "size": 172.0})
	var top := Camera3D.new()
	top.projection = Camera3D.PROJECTION_ORTHOGONAL
	top.size = float(tc.size)
	top.far = 2000.0
	_add(g, top, "TopCamera")
	var cx: float = tc.center[0]
	var cz: float = tc.center[1]
	top.look_at_from_position(Vector3(cx, 350, cz + 0.01), Vector3(cx, 0, cz), Vector3(0, 0, -1))
