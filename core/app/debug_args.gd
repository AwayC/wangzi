class_name DebugArgs
extends RefCounted
## 统一解析命令行用户参数（`--` 之后的部分）：
##   --key=value  → 字符串值
##   --flag       → true
## 用法: DebugArgs.get_float("time-scale", 1.0)、DebugArgs.has("debug")。
## 已用到的参数见 CLAUDE.md「调试参数」。

static var _cache: Variant = null


static func parse(args: PackedStringArray) -> Dictionary:
	var out := {}
	for a in args:
		if not a.begins_with("--"):
			continue
		var body := a.substr(2)
		var eq := body.find("=")
		if eq < 0:
			out[body] = true
		else:
			out[body.substr(0, eq)] = body.substr(eq + 1)
	return out


static func all() -> Dictionary:
	if _cache == null:
		_cache = parse(OS.get_cmdline_user_args())
	return _cache


## 测试用：替换当前参数。
static func override(args: Dictionary) -> void:
	_cache = args


static func has(key: String) -> bool:
	return all().has(key)


static func get_str(key: String, default := "") -> String:
	var v = all().get(key, default)
	return default if v is bool else str(v)


static func get_float(key: String, default := 0.0) -> float:
	var s := get_str(key, "")
	return float(s) if s.is_valid_float() else default


static func get_int(key: String, default := 0) -> int:
	var s := get_str(key, "")
	return int(s) if s.is_valid_int() else default
