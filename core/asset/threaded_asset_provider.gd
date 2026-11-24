class_name ThreadedAssetProvider
extends AssetProvider
## 后台线程加载（ResourceLoader.load_threaded_request）。
## 只用于不创建物理对象的资源（纹理、音频、字体、纯数据），含碰撞形状的场景请用默认的 AssetProvider，
## 原因见 AssetProvider 的说明。


func supports_threads() -> bool:
	return true


func request(path: String) -> void:
	if ResourceLoader.load_threaded_request(path) != OK:
		push_error("后台加载请求失败: " + path)


func poll(path: String) -> Dictionary:
	var progress := []
	var s := ResourceLoader.load_threaded_get_status(path, progress)
	match s:
		ResourceLoader.THREAD_LOAD_LOADED:
			return {"state": State.LOADED, "progress": 1.0}
		ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			return {"state": State.LOADING, "progress": float(progress[0]) if progress.size() > 0 else 0.0}
	return {"state": State.FAILED, "progress": 1.0}


func take(path: String) -> Resource:
	return ResourceLoader.load_threaded_get(path)
