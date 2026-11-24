# wangzi（《王子历险记》，Godot 4.7.2）

> 本文件是所有 AI 编程助手（Claude Code、Codex、Cursor、Gemini CLI、Copilot 等）共用的项目说明，也适合新加入的开发者阅读。
> 各工具的专属配置文件（如 `CLAUDE.md`）只引用本文件，不另写内容；项目约定有变化时只改这里。

Godot 路径（macOS）: `/Applications/Godot.app/Contents/MacOS/Godot`（下文简写 `$G`，其他系统换成本机路径）。
已装 godot-ai 编辑器插件（`addons/godot_ai/`），对外提供 MCP 服务（服务名 `godot-ai`），各 AI 工具需在自己的 MCP 配置里接入；必须开着 Godot 编辑器才能用。

## 项目现状

**只有基础框架，没有玩法代码。** 早期白盒原型已从仓库移除。

| 文档 | 内容 |
| :--- | :--- |
| `docs/GDD_策划案.md` + `docs/systems/` | 策划案（v3.1，PvE：玩家扮演学生，教导阵营全部是 AI） |
| `docs/production/01_开发任务拆分.md` | 全部开发任务（编号、依赖、规模、角色、里程碑），分工按编号认领 |
| `docs/production/02_美术资源清单.md` | 美术 / 音频资源清单与交付规范 |
| `docs/production/03_玩法原型拆分.md` | 小游戏与交互原型拆分、统一接口契约 |
| `docs/production/04_地图场景编辑计划.md` | 地图决策：按 MC 原样重建的地块、总平面、故事设定、门锁、监控点、步行时间（MC 解析在 `tools/mc/`，重建在 `tools/blender/build_mc_campus.py`，拼场景 `tools/build_campus.gd`） |

## 目录

| 路径 | 作用 |
| :--- | :--- |
| `core/app/` | `App` 服务启动（依赖排序）、`Log`、`DebugArgs`、`ServiceGraph` |
| `core/event/` | `Events` 全局事件总线（强类型信号） |
| `core/asset/` | `Assets` 资源寻址加载、`Pool` 对象池、清单、加载组、Provider |
| `core/ui/` | `UI` 管理器、`UIPanel` / `UIView`、层级、显示动画、按压回弹 |
| `core/testing/` | 测试基类 `TestCase` |
| `ui/panels/common/` | 通用面板：Toast / Confirm / Loading |
| `ui/theme/` | 主题 |
| `data/` | 配置数据；`asset_manifest.tres` 由工具生成，不要手改 |
| `scenes/main.tscn` | 主场景（目前是空壳） |
| `scenes/dev/` | 开发 / 评审用场景（如 `kit_classroom.tscn` 教室套件预览，由工具生成） |
| `scenes/levels/` | 关卡场景；`campus.tscn` 是校园场景，由 `tools/build_campus.gd` 拼装，不要手改 |
| `assets/` | 美术资源（按地址组织，规范见 `docs/production/02_美术资源清单.md`）；当前是 Blender 脚本生成的教室样例套件，和按 MC 布局重建的校园地块 `env/campus/`（.gltf + 共用贴图 `textures/`） |
| `tools/` | 构建与校验工具（见下） |
| `tests/` | 测试（`tests/**/test_*.gd`）与测试夹具 |
| 以后新增 | `game/` 业务代码、`prototypes/` 玩法原型（规范见 production 文档） |

## 常用命令

```bash
# 一键测试：刷新类缓存 → 全部测试 → 资源校验（提交前必须通过）
tools/test.sh
# 只跑名字包含关键字的测试
tools/test.sh ui
# 新增 / 移动 / 删除资源后重新生成资源清单
$G --headless --path . --script res://tools/build_manifest.gd
# 生成主题与通用面板（已存在的文件不覆盖，加 -- --force 覆盖）
$G --headless --path . --script res://tools/build_ui.gd
# 校验某个场景能否加载
$G --headless --path . --script res://tools/check_scene.gd -- res://scenes/main.tscn
# Blender 生成教室样例套件和室内家具（电脑桌、办公桌、上下铺、食堂餐桌）（全部重建；后面跟资源名只重建这几件），之后要 --import 和重建清单
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/build_classroom_kit.py -- [desk_student ...]
# 重建预览教室，并截图（截图需要图形环境，不加 --headless）
$G --headless --path . --script res://tools/build_kit_preview.gd
$G --path . --script res://tools/screenshot_scene.gd -- res://scenes/dev/kit_classroom.tscn /绝对路径/out.png
# 校园地图（流程见 docs/production/04_地图场景编辑计划.md 第五节）：MC 扫描 → 贴图 → Blender 按 MC 布局重建地块和新部件 → 拼场景 → 截图
python3 -I tools/mc/mc_scan.py ~/Downloads/world <扫描输出目录>
python3 -I tools/blender/make_textures.py
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/build_mc_campus.py -- <扫描输出目录> [地块 id ... | extras]
$G --headless --path . --import && $G --headless --path . --script res://tools/build_campus.gd
$G --path . --script res://tools/screenshot_scene.gd -- res://scenes/levels/campus.tscn /绝对路径/out.png 1600 1000 OverviewCamera
# 单个模型在标准灯光下截图
$G --path . --script res://tools/preview_model.gd -- res://assets/env/campus/cuihua.gltf /绝对路径/out.png 515,30,540 500,12,475
```

Blender 建模约定（`tools/blender/kit_lib.py`）：
- 模型正面朝 Blender +Y，导出后就是 Godot 的 -Z；单位米。
- 每件资源烘一张底色图、一张 AO 图，合成一个材质（AO 走 glTF occlusion 通道）。
- 名字带 `-convcolonly` 的对象，导入 Godot 后会变成凸包碰撞体。
- 会动的部件（门扇、柜门、扇叶）做成单独的子对象，枢轴放在合页 / 转轴处。
- glb 里的贴图由 Godot 解出到同目录，命名为 `<资源>_albedo.png` / `<资源>_ao.png`，不要手改。

## 框架用法速查

- **服务**：一个 autoload = 一个服务，脚本里写 `const SERVICE_DEPS: Array[StringName] = [...]` 和 `func setup()`（可 await）。`App` 自动按依赖排序初始化；用到服务前 `await App.wait_ready()`。新服务要加到 `project.godot` 的 `[autoload]`，且排在 `App` 之后。存在名为 `Flow` 且有 `boot()` 的服务时，游戏启动后会调用它（业务流程入口，尚未实现，见任务 FW-01/FW-02）。
- **资源**：业务代码只用地址：`Assets.load("props/desk")`、`Assets.instantiate(...)`、`await Assets.load_group("data/load_groups/xxx")`。地址 = 资源根目录前缀 + 相对路径去扩展名（规则在 `ManifestBuilder.ROOTS`）。`validate_assets` 会拦截 `game/`、`ui/` 里直接 `load("res://assets/...")` 的代码。
- **对象池**：`Pool.prewarm / spawn / recycle / clear_category`；池化节点可实现 `_on_spawn()` / `_on_recycle()`，或挂 `AutoRecycle`。
- **UI**：面板脚本 `extends UIPanel` 并声明 `const PANEL := {"address": "ui/<模块>/<文件名>", "layer": UILayer.POPUP, "cache": true}`；场景放 `ui/panels/<模块>/<文件名>.tscn`；节点用唯一名称 `%Name` + `@onready` 绑定（校验工具会检查）。打开 `UI.open(XxxPanel, 参数)`，关闭 `close()`；快捷 `UI.toast()` / `UI.confirm()`。
- **事件**：跨系统事件在 `core/event/event_bus.gd` 声明成信号并写清参数含义。
- **调试参数**：`-- --debug`（DEBUG 日志）、`-- --quiet`；业务参数用 `DebugArgs.get_*` 读取。

## 约定与踩过的坑

- **二进制资源走 Git LFS**（规则在 `.gitattributes`：`*.glb`、`assets/` 下的贴图、`.gltf` / `.bin`、音频、字体等）。克隆前先装 `git lfs`（macOS：`brew install git-lfs && git lfs install`），否则拿到的只是指针文件；新增二进制类型时先补 `.gitattributes` 再提交。文档配图不走 LFS。

- **`class_name` 可以用**，但新增或改名后要先跑 `$G --headless --path . --import` 刷新类缓存（`tools/test.sh` 已自动做）。autoload 脚本本身不要写 `class_name`。
- **工具脚本（`extends SceneTree`）在 `_init` 阶段不能引用 autoload**（`App`、`UI` 等，也包括会间接引用它们的类型如 `UIPanel`），否则编译失败；需要时把逻辑放进 `call_deferred`，或用 `root.get_node("App")`。工具脚本里不要声明名为 `root` 的成员。
- **资源加载默认在主线程逐帧进行**。含碰撞形状的场景用后台线程加载会和物理服务器抢 RID（报 `Attempting to initialize the wrong RID`）；`ThreadedAssetProvider` 只用于纹理、音频等不建物理对象的资源。
- 大场景模型导出成 `.gltf` + `.bin` + 外部贴图（`export_keep_originals`），不要用内嵌 JPEG 的 glb：headless 导入时内嵌 JPEG 解不出来，材质会全白。
- `StringName` 的 `<` 不是字典序，排序要转成 `String`。
- 生成场景的脚本必须给每个子节点设 `owner`，否则不会被保存。
- 缓存面板（`cache: true`）跨测试保留，测试里按增量断言。
- **删除 / 移动文件前先确认已提交到 git**：未跟踪的文件误删无法恢复。批量移动不要用 `git mv -k`（对未跟踪文件会静默跳过，后续删除命令会把没移走的文件一起删掉）。
- Godot 编辑器开着时不要直接改 `project.godot`（编辑器保存时会覆盖）：autoload、主场景等用 godot-ai MCP 的 `autoload_manage` / `project_manage` 改，或先关编辑器再改。

## 分工原则（Godot CLI 与 godot-ai MCP）

| 任务 | 用什么 |
|---|---|
| 批量 / 脚本化生成场景、校验、测试、导出 | Godot CLI（headless） |
| 在开着的编辑器里看效果、截图、微调节点 | godot-ai MCP |

MCP 要点：给节点设 Mesh 等资源不能用 `node_set_property` 传字典（会报 `WRONG_TYPE`），要用 `resource_manage(op="create", ...)`；改完 `scene_save`；节点路径相对场景根。
