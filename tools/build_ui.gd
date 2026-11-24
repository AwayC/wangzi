extends SceneTree
## 一次性引导：生成主题 ui/theme/main_theme.tres 和通用面板场景（Toast / Confirm / Loading）。
## 生成后在编辑器里直接改这些场景；已存在的文件默认不覆盖，加 -- --force 才覆盖。
##   Godot --headless --path . --script res://tools/build_ui.gd [-- --force]
## 注意：面板脚本引用了 autoload（UI 等），所以构建放在 call_deferred 里，等 autoload 就绪后再加载脚本。

const THEME_PATH := "res://ui/theme/main_theme.tres"
const PANEL_DIR := "res://ui/panels/common/"
## 中文字体：先用系统字体（各平台自带的中文黑体），以后可以换成项目内置的思源黑体
const CJK_FONTS := ["PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC",
	"Source Han Sans SC", "WenQuanYi Micro Hei"]

var force := false
var written := 0
var skipped := 0


func _init() -> void:
	force = OS.get_cmdline_user_args().has("--force")
	_build.call_deferred()


func _build() -> void:
	DirAccess.make_dir_recursive_absolute("res://ui/theme")
	DirAccess.make_dir_recursive_absolute(PANEL_DIR)
	_save(_theme(), THEME_PATH)
	_save_scene(_toast(), PANEL_DIR + "toast_panel.tscn")
	_save_scene(_confirm(), PANEL_DIR + "confirm_popup.tscn")
	_save_scene(_loading(), PANEL_DIR + "loading_panel.tscn")
	print("build_ui: 写入 %d 个，跳过已存在 %d 个%s" % [written, skipped, "" if force else "（加 -- --force 覆盖）"])
	quit()


func _save(res: Resource, path: String) -> void:
	if FileAccess.file_exists(path) and not force:
		skipped += 1
		return
	var err := ResourceSaver.save(res, path)
	if err == OK:
		written += 1
	else:
		push_error("保存失败 %s: %s" % [path, error_string(err)])


func _save_scene(root: Node, path: String) -> void:
	_own(root, root)
	var ps := PackedScene.new()
	ps.pack(root)
	root.free()
	_save(ps, path)


func _own(n: Node, owner_node: Node) -> void:
	for c in n.get_children():
		c.owner = owner_node
		_own(c, owner_node)


# ---------------- 主题 ----------------

func _box(bg: Color, radius := 10, border := Color.TRANSPARENT, pad := 12) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	if border.a > 0.0:
		s.border_color = border
		s.set_border_width_all(2)
	s.content_margin_left = pad * 1.5
	s.content_margin_right = pad * 1.5
	s.content_margin_top = pad
	s.content_margin_bottom = pad
	return s


func _theme() -> Theme:
	var t := Theme.new()
	var font := SystemFont.new()
	font.font_names = PackedStringArray(CJK_FONTS)
	t.default_font = font
	t.default_font_size = 22
	var accent := Color(0.85, 0.2, 0.17)
	t.set_stylebox("normal", "Button", _box(Color(0.17, 0.19, 0.25)))
	t.set_stylebox("hover", "Button", _box(Color(0.24, 0.27, 0.35)))
	t.set_stylebox("pressed", "Button", _box(accent.darkened(0.2)))
	t.set_stylebox("focus", "Button", _box(Color(0, 0, 0, 0), 10, Color(1, 0.86, 0.3)))
	t.set_stylebox("disabled", "Button", _box(Color(0.15, 0.15, 0.17, 0.6)))
	t.set_color("font_color", "Button", Color(0.95, 0.95, 0.95))
	t.set_color("font_disabled_color", "Button", Color(0.5, 0.5, 0.5))
	t.set_stylebox("panel", "PanelContainer", _box(Color(0.09, 0.1, 0.14, 0.96), 16, Color(1, 1, 1, 0.08), 20))
	t.set_stylebox("background", "ProgressBar", _box(Color(0.15, 0.16, 0.2), 6, Color.TRANSPARENT, 0))
	t.set_stylebox("fill", "ProgressBar", _box(Color(1.0, 0.82, 0.25), 6, Color.TRANSPARENT, 0))
	t.set_color("font_color", "Label", Color(0.95, 0.95, 0.95))
	return t


# ---------------- 面板 ----------------

func _panel_root(script_path: String, name: String) -> Control:
	var root := Control.new()
	root.name = name
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.set_script(load(script_path))
	return root


func _unique(n: Node, unique_name: String) -> Node:
	n.name = unique_name
	n.unique_name_in_owner = true
	return n


func _transition(root: Node, kind: int) -> void:
	var tr := UITransition.new()
	tr.name = "UITransition"
	tr.kind = kind
	root.add_child(tr)


func _toast() -> Control:
	var root := _panel_root(PANEL_DIR + "toast_panel.gd", "ToastPanel")
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var box: PanelContainer = _unique(PanelContainer.new(), "Box")
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM, Control.PRESET_MODE_MINSIZE)
	box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	box.grow_vertical = Control.GROW_DIRECTION_BEGIN
	box.offset_bottom = -160
	root.add_child(box)
	var label: Label = _unique(Label.new(), "Message")
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.text = "提示"
	box.add_child(label)
	return root


func _confirm() -> Control:
	var root := _panel_root(PANEL_DIR + "confirm_popup.gd", "ConfirmPopup")
	_transition(root, UITransition.Kind.SCALE)
	var center := CenterContainer.new()
	center.name = "Center"
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.custom_minimum_size = Vector2(620, 0)
	center.add_child(panel)
	var vbox := VBoxContainer.new()
	vbox.name = "VBox"
	vbox.add_theme_constant_override("separation", 28)
	panel.add_child(vbox)
	var text: Label = _unique(Label.new(), "Text")
	text.text = "确定吗？"
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	text.custom_minimum_size = Vector2(560, 90)
	text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	text.add_theme_font_size_override("font_size", 26)
	vbox.add_child(text)
	var row := HBoxContainer.new()
	row.name = "Buttons"
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 32)
	vbox.add_child(row)
	for n in ["CancelBtn", "ConfirmBtn"]:
		var b: Button = _unique(Button.new(), n)
		b.text = "取消" if n == "CancelBtn" else "确定"
		b.custom_minimum_size = Vector2(180, 56)
		row.add_child(b)
	return root


func _loading() -> Control:
	var root := _panel_root(PANEL_DIR + "loading_panel.gd", "LoadingPanel")
	_transition(root, UITransition.Kind.FADE)
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = Color(0.06, 0.07, 0.1)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var vbox := VBoxContainer.new()
	vbox.name = "VBox"
	vbox.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM, Control.PRESET_MODE_MINSIZE)
	vbox.grow_horizontal = Control.GROW_DIRECTION_BOTH
	vbox.grow_vertical = Control.GROW_DIRECTION_BEGIN
	vbox.offset_bottom = -120
	vbox.custom_minimum_size = Vector2(960, 0)
	vbox.add_theme_constant_override("separation", 20)
	root.add_child(vbox)
	var title: Label = _unique(Label.new(), "Title")
	title.text = "加载中……"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 40)
	vbox.add_child(title)
	var bar: ProgressBar = _unique(ProgressBar.new(), "Bar")
	bar.custom_minimum_size = Vector2(960, 18)
	bar.show_percentage = false
	vbox.add_child(bar)
	var tip: Label = _unique(Label.new(), "Tip")
	tip.text = "小贴士"
	tip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tip.modulate = Color(0.75, 0.78, 0.85)
	vbox.add_child(tip)
	return root

