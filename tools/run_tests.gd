extends SceneTree
## headless 测试运行器：扫描 res://tests/**/test_*.gd，运行其中 test_ 开头的方法。
## 用法: Godot --headless --path . --script res://tools/run_tests.gd [-- --filter=关键字]
## 推荐用 tools/test.sh（会先 --import 刷新 class_name 缓存）。
## 输出每个测试的 PASS/FAIL，最后一行 RESULT passed=N failed=M；有失败时退出码为 1。

var _filter := ""


func _init() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--filter="):
			_filter = a.get_slice("=", 1)
	_run.call_deferred()


func _run() -> void:
	var files := _find_tests("res://tests")
	files.sort()
	var passed := 0
	var failed := 0
	for path in files:
		var script: GDScript = load(path)
		if script == null or not script.can_instantiate():
			print("FAIL %s（脚本无法加载）" % path)
			failed += 1
			continue
		var methods: Array[String] = []
		for m in script.get_script_method_list():
			var n: String = m["name"]
			if n.begins_with("test_") and not methods.has(n):
				methods.append(n)
		for method in methods:
			var label := "%s::%s" % [path.get_file().get_basename(), method]
			if _filter != "" and not label.contains(_filter):
				continue
			var tc = script.new()
			if not (tc is TestCase):
				print("FAIL %s（没有继承 TestCase）" % path)
				failed += 1
				break
			tc.tree = self
			await tc.before_each()
			await tc.call(method)
			await tc.after_each()
			tc._cleanup()
			await process_frame
			if tc._failures.is_empty():
				passed += 1
				print("PASS %s（%d 项断言）" % [label, tc._checks])
			else:
				failed += 1
				print("FAIL %s" % label)
				for f in tc._failures:
					print("     - " + f)
	print("RESULT passed=%d failed=%d" % [passed, failed])
	quit(1 if failed > 0 else 0)


func _find_tests(dir_path: String) -> Array[String]:
	var out: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return out
	for sub in dir.get_directories():
		out.append_array(_find_tests(dir_path.path_join(sub)))
	for f in dir.get_files():
		if f.begins_with("test_") and f.ends_with(".gd"):
			out.append(dir_path.path_join(f))
	return out
