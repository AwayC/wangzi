class_name AssetProvider
extends RefCounted
## 资源加载底层（对应 KiHan 的 IAssetProvider）。
## 默认实现：主线程同步加载，由 AssetManager 每帧加载一项来分摊（加载界面的进度照常更新）。
##
## 为什么默认不用后台线程：场景里的碰撞形状会在加载线程里创建物理服务器 RID，
## 而游戏运行时主线程的物理服务器同时在用 RID 分配器，两边竞争会报
## "Attempting to initialize the wrong RID" 并加载失败（2026-11 实测 school.tscn 必现）。
## 纹理 / 音频这类不建物理对象的资源可以换 ThreadedAssetProvider 并行加载。
##
## 以后接 DLC / Mod（ProjectSettings.load_resource_pack）或远程资源时写新的子类，再 Assets.set_provider(...)。

enum State { LOADING, LOADED, FAILED }


## 是否支持后台并行加载（request / poll / take）。
func supports_threads() -> bool:
	return false


func load_now(path: String) -> Resource:
	return ResourceLoader.load(path)


## 以下三个只在 supports_threads() 为 true 时使用。
func request(_path: String) -> void:
	pass


## 查询后台加载状态：{state: State, progress: 0~1}
func poll(_path: String) -> Dictionary:
	return {"state": State.FAILED, "progress": 1.0}


func take(_path: String) -> Resource:
	return null
