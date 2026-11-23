# wangzi (Godot 4.7.2 项目)

Godot 路径: `/Applications/Godot.app/Contents/MacOS/Godot`(下文简写 `$G`)。
已装 godot-ai 插件(`addons/godot_ai/`,v4.4.2),MCP 名 `godot-ai`,配置在用户级。

## 分工原则(已实测)

| 任务 | 用什么 |
|---|---|
| 批量/脚本化生成场景、校验脚本、导出 | **Godot CLI(headless)** |
| 在已打开的编辑器里看效果、截图、微调节点/属性 | **godot-ai MCP**(需编辑器开着) |

两者做同一个 3D 小场景(地面+方块+灯+相机),结果等价;CLI 约 0.25 秒一次,MCP 约 10 次调用、2.5 秒。

## CLI 用法

生成场景(脚本继承 `SceneTree`,`PackedScene.pack()` + `ResourceSaver.save()`,模板见 `tools/make_scene.gd`):
```bash
$G --headless --path . --script res://tools/make_scene.gd
```
校验场景能否加载(见 `tools/check_scene.gd`,成功输出 `OK ...`):
```bash
$G --headless --path . --script res://tools/check_scene.gd -- res://scenes/xxx.tscn
```
校验 GDScript 语法(语法错误会输出 `Parse Error`):
```bash
$G --headless --path . --check-only --script res://path/to/file.gd
```
导出: `$G --headless --path . --export-release <预设名> <输出路径>`(需先在项目里配置导出预设;本项目尚未实测)。

注意:
- 脚本里必须给每个子节点设 `owner = root`,否则不会被保存进 `.tscn`。
- 脚本结尾 `root.free()` 再 `quit()`,否则 headless 会打印一堆泄漏警告。
- headless 不渲染,看不到画面;要看效果用 MCP 截图。

## MCP 用法要点

- 先确认编辑器已打开本项目;`session_manage(op="list")` 能看到会话。
- 建场景: `scene_manage(op="create", params={path, root_type, root_name})`。
- 加节点: `node_create(type, name, parent_path)`;设属性: `node_set_property`,向量用 `{"x":..,"y":..,"z":..}`。
- **给节点设 Mesh 等资源不能用 `node_set_property` 传字典**(会报 `WRONG_TYPE`),要用
  `resource_manage(op="create", params={type:"BoxMesh", path:"/Root/Node", property:"mesh", properties:{...}})`。
- 改完调 `scene_save`;看效果用 `editor_screenshot`。
- 节点路径相对场景根,如 `/McpDemo/Cube`,不是运行时 `/root/...`。

## 示例文件

- `scenes/cli_demo.tscn`: CLI 生成
- `scenes/mcp_demo.tscn`: MCP 生成

## 游戏原型（白盒）

策划案: `docs/GDD_策划案.md`。阵营胜负与排名规则见 GDD 6.0:
学生玩家娱乐值总和 ≥ `ENT_GOAL_PER_STUDENT × 学生人数` → 学生阵营胜,否则教导阵营胜;学生之间按高考分排名。

### 目录
| 路径 | 作用 |
|---|---|
| `scripts/game/game_config.gd` | **所有可调数值**(阶段时长、收益速率、门槛、角色被动、称号) |
| `scripts/game/score_rules.gd` | 算分/胜负/排名纯函数 |
| `scripts/game/student_stats.gd` | 单个学生玩家的局内数据 |
| `scripts/game/main.gd` | 主控:时间轴、门禁、生成角色、放榜(`scenes/main.tscn` 的根) |
| `scripts/actors/` | 玩家、AI 学生、老师 AI、占位模型 |
| `scripts/world/` | 关卡脚本、区域 Zone、可交互物(课桌/电脑) |
| `scripts/ui/hud.gd` | HUD 与放榜界面(全部代码搭建) |
| `tools/build_school.gd` | 生成 `scenes/school.tscn`(校园白盒)和 `scenes/main.tscn` |
| `tools/test_score_rules.gd` | 计分规则单测 |

### 常用命令
```bash
# 改了 build_school.gd 后重新生成校园场景
$G --headless --path . --script res://tools/build_school.gd
# 计分单测(应输出 RESULT failures=0)
$G --headless --path . --script res://tools/test_score_rules.gd
# 40 倍速跑完整两天并打印阶段/放榜,检查有无 ERROR
$G --headless --path . --fixed-fps 60 --quit-after 4000 -- --time-scale=40 --log --quit-on-finish
# 正常速度,玩家坐在机房电脑前,每 5 秒打印 AI/老师状态
$G --headless --path . --fixed-fps 60 --quit-after 7200 -- --debug --debug-player=lab
```

### 约定
- **不用 `class_name`**,跨脚本一律 `const X = preload(...)`。原因:CLI headless 运行时编辑器未必已刷新全局类缓存,`class_name` 会解析失败。
- `SceneTree` 脚本(tools/)里不能声明名为 `root` 的成员,会和 `SceneTree.root` 冲突。
- 碰撞层: 1 世界(墙,参与导航烘焙) / 2 玩家 / 3 AI 学生(值 4) / 4 老师(值 8) / 5 交互射线(值 16)。
- 家具(桌椅床)只是外观、不挡人,导航只烘焙第 1 层的 `solid()`;交互靠第 5 层碰撞。
- 宿舍铁门 `DormGate` 故意不放在 `Nav` 下,不参与烘焙,由 `school.gd` 开关碰撞。
- **寻路参数是一起调过的,改一个要连带检查其它**(都踩过坑):
  - 导航烘焙半径 0.5,AI/老师碰撞半径 0.22。碰撞半径必须明显小于烘焙半径,否则 0.25m 体素误差会让路径贴着柱角走、身体被卡住。
  - 室内门宽 `DOOR_W = 1.6`。门宽 − 2×烘焙半径 太小(≤0.4)时,体素取整会把门“封死”,寻路改走楼外,角色卡在墙/铁门前。
  - `NavigationAgent3D` 统一用 `scripts/actors/nav_util.gd::setup_agent()`:`path_height_offset=0.5` 抵消导航面高度差(否则矮障碍物顶上的悬空路点永远到不了,原地抖动);`path_desired_distance=0.4`(太大会提前拐弯蹭门框)。
  - 卡住判定用 `NavUtil.remaining_path_length()`(剩余路径长度),不要用 `distance_to_target()`(直线距离,绕路出门时会变大导致误判)。
- 调试寻路: `-- --debug --start-phase=1` 直接从晚自习开始,打印入座数、卡住累计和每次卡住的位置。
- 学生玩家和 AI 学生必须共用 `PlaceholderModels.make_student()`(GDD 全员同模);换美术时只改 `placeholder_models.gd`。
- 输入映射在 `main.gd::_setup_input()` 里用代码注册,没写进 project.godot。
- 调试键: N 跳过当前阶段;放榜后 R 重开。
