---
name: oil-motion
description: "Design, implement, optimize, and explain interactive web animations driven by scroll, pointer, drag, touch, device orientation, audio, data, or component state. Use when a webpage needs responsive visual motion for products, interfaces, diagrams, characters, or scene transitions."
---

# Oil Motion

从目标出发构思交互动画，先生图锁定首尾状态，再用 AI 视频补全连续动作，最后编译成由连续参数控制的网页动画。生成模型负责主要画面和动作，程序只负责可重复、可测量的媒体处理与运行时控制。

确定性媒体流水线需要 Python 3、Pillow、ffmpeg 和 ffprobe（用
`python3 -m pip install -r "$OIL_MOTION/scripts/requirements.txt"` 安装）；所有命令
使用 Skill 自身绝对路径（`OIL_MOTION="$HOME/.codex/skills/oil-motion"`）。默认视频
模型固定为 ZenMux 的 `minimax/minimax-h3`；只有用户明确要求更换，或 MiniMax 无法
完成目标时才讨论其他模型，不要让用户在没有必要时承担模型选择。

## 首次配置 API Key

生成视频前先检查一次；已经配置时直接继续，不要再次询问：

```bash
python3 "$OIL_MOTION/scripts/oil_motion_config.py" status   # 已配置则继续
python3 "$OIL_MOTION/scripts/oil_motion_config.py" set      # 未配置时引导用户运行一次
```

脚本会隐藏输入内容，并把密钥保存在本机的
`~/.config/oil-motion/config.json`（不在项目目录内，限当前用户读写）。不要让用户把
密钥写进项目、提示词、命令参数、日志或任务元数据；`ZENMUX_API_KEY` 环境变量仍然
可用，并且优先于配置文件。

## 职责边界

- **语义运动**包含产品拆解、部件组装、壳体开启、材质变化、液体流动、肢体形变以及前后遮挡关系。用已验收的首尾关键帧锁定结果，再让 AI 视频生成中间连续变化；不要用整张图片的 CSS 变换冒充。
- **几何运动**是整组素材的位移、缩放、旋转、裁切、时间映射、层级切换和惯性。这些变化由程序完成，因为它们需要精确响应交互参数。
- 判断边界时先问：“如果只移动整张图片，关节、接触点和遮挡是否仍然自然？”如果答案是否定的，就必须生成完整动作，而不是继续增加程序补丁。

## 主流程

### 0. 构思 Motion Concept（按需）

用户只有目标、对象或模糊的“想做得更有趣”时，先阅读
[references/concepts.md](references/concepts.md) 完成创意发散，给出最多三个真正不同
的方向；用户已明确驱动方式、动作和视觉结果时直接锁定 Concept Contract。不要把某个
项目的品牌、角色或布局偏好写成通用动画规则。

### 1. 锁定 Concept Contract（执行前硬门）

任何生成之前，先把用户需求逐项锁定为 Concept Contract。合同只保存用户意图，每一项
都必须有来源：用户原话、参考图，或用户的明确确认。

```yaml
subject_count: 1                # 画面中的主体数量，逐个数清
subjects:                       # 每个主体的身份锚点
  - name: 主角
    identity: 面孔、发型、服装、标志性配饰
style: 动漫                      # 用户指定的风格原词，不替换
mood: 胜利的克制与张力            # 情绪与张力
narrative: 单人胜利演武           # 叙事形式
background_owner: video | page  # 背景与主体同视频烘焙，或页面独立拥有
scene: 演武厅、环境光、地面接触    # 背景归属为 video 时的场景锚点
driver: scroll | pointer | drag | touch | orientation | audio | data | state
continuity:                     # 硬性连续性要求
  - 每段同脸
  - 首尾帧连续
  - 背景连续
clip_continuity: chain | independent  # 多段首尾接力，或合同明确的独立状态
destination: 页面位置、显示尺寸和设备
```

规则：

1. 用户说“单人”就是一个主体，说“动漫”就保持动漫风格。**禁止擅自扩写或改向**：不得把“单人动漫格斗胜利演武”扩写成“双人写实拆招”，不得加人、换风格、换情绪、换叙事形式。任何扩写都属于变更需求，必须先向用户确认。
2. 缺项且会改变生产路线时（主体数量、风格、背景归属、连续性要求），先问用户，不得自行假设。`clip_continuity` 没有默认值，必须显式锁定。
3. 背景归属的默认判定：镜头运动、环境光、地面接触或阴影、景深、背景连续性中任意一项重要，或主体不需要脱离背景复用时，`background_owner: video`。只有主体必须以透明形式叠加到页面自有、可更换的背景上时，才用 `page`。
4. 合同锁定后写入 `source/concept-contract.yaml`，之后的关键帧、提示词、母版验收和最终验收都逐项对照合同。发现产出偏离合同即返工，不得将错就错。

### 2. 建立 Motion Brief（派生执行计划）

Motion Brief 只保存从合同、参考图和上下文中派生的执行计划。用户意图字段
（`background_owner`、`clip_continuity`、`driver`、`destination` 等）以 Concept
Contract 为唯一事实源，Brief 不再复制；执行时从合同读取。

```yaml
concept_contract: source/concept-contract.yaml  # 必须先锁定
reference: 身份和风格基准图
identity_bible: source/identity-bible.md        # 有角色时必填
parameter_space: linear | circular | 2d | discrete
motion: 参数变化时画面如何变化
storyboard: 按顺序排列的视觉阶段
keyframes: first | intermediate[] | last
clip_chain: 每段视频使用哪两个相邻关键帧
rest_state: 初始和失去输入时的状态
loop: open | closed | none
key_color: "#00FF00" | "#FF00FF"                # 仅 background_owner=page
scene_continuity: 环境光、地面接触、背景连续性的锁定说明  # 仅 background_owner=video
delivery: baked-video | alpha-atlas | chroma-video  # 由预算脚本填写，不询问用户
anchor: fixed-body | center | bottom | free
quality_target: 分辨率、参数采样密度、文件预算
interpolation_fps: 48
reduced_motion: 静态替代状态
```

参数模型：

| 模型 | 常见输入 | 素材结构 |
|---|---|---|
| linear | 滚动、拖拽、进度、音量 | 一条有起止点的时间轴 |
| circular | 指针方向、旋钮、360° 展示 | 首尾连续的环形时间轴 |
| 2d | 指针 X/Y、陀螺仪二维倾斜 | 二维采样网格或可组合的两条轴 |
| discrete | hover、点击、成功、失败 | 多个独立片段和状态机 |

不要把二维或离散输入压成一条线性视频；二维采样、多条独立片段分别预算，细节见
[references/delivery-selection.md](references/delivery-selection.md)。

### 3. 设计关键帧与 Identity Bible

1. 先分别生成并验收首尾关键帧；多阶段叙事先生成完整关键帧组 `K0…Kn`，每张图只描述
   一个清晰阶段，第 `i` 段视频固定使用 `Ki` 为首帧、`Ki+1` 为尾帧，每段只承担一个
   主要语义变化。
2. 每张关键帧在最终展示尺寸下验收构图、身份和细节，逐项对照 Concept Contract；
   分辨率至少覆盖最终显示尺寸乘以目标 DPR；未通过不得提交视频。
3. 有角色时，生成任何关键帧之前先写 `source/identity-bible.md` 锁定身份锚点；
   验收标准见 [references/qa.md](references/qa.md)。
4. 提示词写法、首尾帧模式与提交命令见
   [references/prompting.md](references/prompting.md)。已有视频或序列帧作为输入时
   跳过生成，直接从 `probe` / `analyze` 开始，保留原始素材。

### 4. 首屏 Pilot 硬门（批量生成前强制）

量产前按 [references/qa.md](references/qa.md) 的“Pilot 硬门”完成第一段真实页面验收；
未通过就停在 Pilot 返工。批准命令和 production 阶段要求均以该文档为准。

### 5. 预算与路线选择（脚本执行）

正式生成前先运行 `motion_budget.py --strict`，显式传入合同锁定的
`--background-owner`（滚动驱动同时传 `--scroll-pages`），保存 `--report`。
`delivery.selected` 是唯一交付决策：Agent 直接执行，不向用户抛技术选项；`--strict`
失败即停止，不要生成完整视频。决策顺序、阈值、超预算处理和全部命令示例见
[references/delivery-selection.md](references/delivery-selection.md)。

按选择结果路由到唯一对应流程，不要混用 chroma 与 baked 路线的命令：

- `alpha-atlas`：[references/minimax-spritesheet.md](references/minimax-spritesheet.md)
- `chroma-video`：[references/chroma-video.md](references/chroma-video.md)
- `baked-video`：[references/baked-video.md](references/baked-video.md)

### 6. 生成动作母版

按 [references/prompting.md](references/prompting.md) 提交视频任务；母版验收与多段
连续性按 [references/qa.md](references/qa.md) 执行。任一硬门失败即停止。

### 7. 插帧、清理与编译

1. 母版通过内容验收后按 [references/optimization.md](references/optimization.md)
   插帧并检查接触表，失败即停止。
2. 按 `delivery.selected` 阅读对应路线参考，执行该路线的清理、稳定、检测、编译和
   打包；路线参考中的任何检查失败都不得绕过。

### 8. 实现交互控制

从 [assets/interactive-motion.ts](assets/interactive-motion.ts) 开始，按自动选中的路线
参考接入对应渲染器；输入映射、阻尼、预加载、降级和移动端细节统一见
[references/runtime.md](references/runtime.md)。

### 9. 验收

逐项对照 Concept Contract 与 Identity Bible，按路线完成各自验收，并在目标 CSS 尺寸、
DPR、冷缓存、快速反向和移动端条件下复核；完整清单、硬门命令和故障定位见
[references/qa.md](references/qa.md)。

### 10. 生成动画原理展示页（按需）

需要向用户展示“母版视频 → 图集 → 输入映射 → 当前帧”时，阅读
[references/explainer.md](references/explainer.md) 并运行 `create_explainer.py`
生成独立 HTML；不要复制项目私有角色或文案冒充通用模板。

## 交付

保留 `source/` 母版、`pilot/` 批准证据、`qa/` 报告和 `final/` 成品。`final/` 只交付
`delivery.selected` 对应的一种主资源及静态降级，不重复实现其他路线；同时说明合同、
提示词、处理命令、自动选择依据、最终资产和运行时入口。
