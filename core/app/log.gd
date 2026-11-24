class_name Log
extends RefCounted
## 分级日志：Log.info("Assets", "加载完成")。
## 级别由 DebugArgs 决定：默认 INFO；--debug 时为 DEBUG；--quiet 时只输出 WARN 以上。

enum Level { DEBUG, INFO, WARN, ERROR }

const _NAMES := ["DEBUG", "INFO", "WARN", "ERROR"]

static var level: Level = Level.INFO
static var _configured := false


static func debug(tag: String, msg: String) -> void:
	_write(Level.DEBUG, tag, msg)


static func info(tag: String, msg: String) -> void:
	_write(Level.INFO, tag, msg)


static func warn(tag: String, msg: String) -> void:
	_write(Level.WARN, tag, msg)
	push_warning("[%s] %s" % [tag, msg])


static func error(tag: String, msg: String) -> void:
	_write(Level.ERROR, tag, msg)
	push_error("[%s] %s" % [tag, msg])


static func _write(lv: Level, tag: String, msg: String) -> void:
	if not _configured:
		_configured = true
		if DebugArgs.has("debug"):
			level = Level.DEBUG
		elif DebugArgs.has("quiet"):
			level = Level.WARN
	if lv < level:
		return
	print("[%s][%s] %s" % [_NAMES[lv], tag, msg])
