---
name: oil-motion
description: "Design, implement, optimize, and explain interactive web animations driven by scroll, pointer, drag, touch, device orientation, audio, data, or component state. Use when a webpage needs responsive visual motion for products, interfaces, diagrams, characters, or scene transitions."
---

# Oil Motion

从目标出发构思交互动画，先生图锁定首尾状态，再用 AI 视频补全连续动作，最后编译成由连续参数控制的网页动画。生成模型负责主要画面和动作，程序只负责可重复、可测量的媒体处理与运行时控制。

确定性媒体流水线需要 Python 3、Pillow、ffmpeg 和 ffprobe。

默认视频模型固定为 ZenMux 的 `minimax/minimax-h3`。只有用户明确要求更换，或
MiniMax 无法完成目标时，才讨论其他模型；不要让用户在没有必要时承担模型选择。

## 首次配置 API Key

生成视频前先运行：

```bash
python3 "$OIL_MOTION/scripts/oil_motion_config.py" status
```

已经配置时直接继续，不要再次询问。尚未配置时，告诉用户只需配置一次，并引导用户在
终端运行：

```bash
python3 "$OIL_MOTION/scripts/oil_motion_config.py" set
```

脚本会隐藏输入内容，并把密钥保存在本机的
`~/.config/oil-motion/config.json`。配置文件不在项目目录内，权限限制为当前用户读写。
不要让用户把密钥写进项目、提示词、命令参数、日志或任务元数据。`ZENMUX_API_KEY`
环境变量仍然可用，并且优先于配置文件。

## 核心原则

1. 先定义交互参数和关键状态，再生图、再生视频。没有参数模型和首尾关键帧，就不提交视频。
2. 唯一视觉生产主线是：参考图 → 生成并验收首尾关键帧 → AI 视频补全连续变化。多阶段动画拆成多组相邻关键帧，逐段生成并串联。
3. 把 AI 视频视为动作母版；只有自动选择结果为 `chroma-video` 时，才把编译后的绿幕视频作为网页资产，并由 WebGL 实时生成 Alpha。
4. 程序只处理确定性工作：探测、插帧、切帧、离线或实时抠色、去溢色、稳定、查重、检测闪帧、编码、图集打包、清单生成、预加载、文字覆盖和交互映射。
5. 让生成模型处理主要视觉内容和连续性：角色身份、产品形态、结构变化、姿态、镜头内动作和风格。
6. 先保留高分辨率母版，检查通过后再压缩。不要从压缩后的网页资源继续加工。
7. 默认使用单图层离散换帧，不通过相邻帧透明叠加伪造流畅度；叠加会产生虚影。
8. 动画创意必须同时说明输入、视觉回应和表达目的；不要只罗列效果名称。
9. 压缩前必须确认最大实际 CSS 展示尺寸和目标 DPR。清晰度是硬门槛，目标体积是第二约束；无法同时满足时更换资产格式，不得继续缩小。
10. 先分析对象能如何变化，再设计首尾关键帧。绿幕、雪碧图和视频编码只是交付手段，不是创意入口。
11. 所有生成关键帧和动作母版都必须使用均匀色键背景：默认纯绿，主体含大量绿色时改用洋红。图集在构建时抠成 Alpha，视频在 WebGL 运行时抠成 Alpha；页面独立提供最终背景。
12. AI 动作母版通过内容验收后必须程序插帧，默认目标为 48 FPS；插帧结果与原始帧接触表都通过后，才能继续清理、稳定和打包。

### 不要混淆语义运动与几何运动

- **语义运动**包含产品拆解、部件组装、壳体开启、材质变化、液体流动、肢体形变以及前后遮挡关系。用已验收的首尾关键帧锁定结果，再让 AI 视频生成中间连续变化；不要用整张图片的 CSS 变换冒充。
- **几何运动**是整组素材的位移、缩放、旋转、裁切、时间映射、层级切换和惯性。这些变化由程序完成，因为它们需要精确响应交互参数。
- 一个方案可以同时使用两者：例如先制作“完整手机变成爆炸图”的结构动画，再由程序根据滚动控制镜头推进、部件间距、文字显隐和正反播放。
- 判断边界时先问：“如果只移动整张图片，关节、接触点和遮挡是否仍然自然？”如果答案是否定的，就必须生成完整动作，而不是继续增加程序补丁。

## 0. 构思 Motion Concept

当用户只有目标、对象或模糊的“想做得更有趣”，但没有明确动作方案时，先阅读 [references/concepts.md](references/concepts.md) 并完成创意发散。用户已经明确驱动方式、动作和视觉结果时跳过本阶段，直接建立 Motion Brief。

先从对象的结构、功能、材质、空间、状态和信息关系中寻找可变化属性。再用一句话写清动画需要完成的作用，并给出最多三个真正不同的方向。每个方向必须包含：

```yaml
name: 简短概念名
driver: 用户或系统输入
response: 画面如何连续回应
meaning: 动画表达的进度、关系、状态、反馈或情绪
semantic_motion: 需要生成模型处理的动作
geometric_motion: 由程序精确控制的运动
rest_state: 没有输入时的状态
keyframes: 需要生成的起点、中间点和终点图片
clip_chain: 相邻关键帧如何组成连续视频片段
delivery_format: auto
cost_and_risk: 主要性能成本与失败风险
```

按以下标准比较并推荐一个方向：

- 输入与动作之间是否自然，用户能否理解自己触发了什么。
- 动画是否表达内容或状态，而不只是持续播放装饰。
- 参数空间是否匹配；不要把二维输入硬压成一维时间轴。
- 技术路线能否在目标尺寸、设备和资源预算内清晰运行。
- 静止、首次输入、快速反向和失去输入时是否仍然成立。

用户要求直接实现时，选择最合适的方向并说明关键假设后继续；否则先展示方向供用户选择。不要把某个项目的品牌、角色或布局偏好写成通用动画规则。

## 1. 建立 Motion Brief

从上下文读取已有约束。只有缺少会改变生产路线的信息时才询问用户。

```yaml
subject: 需要运动的角色、产品、图表或场景
reference: 身份和风格基准图
driver: pointer | scroll | drag | touch | orientation | audio | data | state
parameter_space: linear | circular | 2d | discrete
motion: 参数变化时画面如何变化
storyboard: 按顺序排列的视觉阶段
keyframes: first | intermediate[] | last
clip_chain: 每段视频使用哪两个相邻关键帧
rest_state: 初始和失去输入时的状态
loop: open | closed | none
background: chroma
key_color: "#00FF00" | "#FF00FF"
background_owner: page
matte_delivery: required
delivery: alpha-atlas | chroma-video  # 由预算脚本填写，不询问用户
anchor: fixed-body | center | bottom | free
destination: 页面位置、显示尺寸和设备
quality_target: 分辨率、参数采样密度、文件预算
interpolation_fps: 48
reduced_motion: 静态替代状态
```

### 固定绿幕管线（硬门槛）

1. 所有由图片或视频模型生成的关键帧、相邻转场和动作母版，都使用完全均匀的色键背景，不存在“直接生成最终场景背景”的分支。
2. 默认色键是 `#00FF00`；主体含大量绿色时只能切换为 `#FF00FF`，不能切换成真实场景、渐变、黑色或白色背景。
3. 背景始终属于页面层。图集路线在构建时生成 Alpha；视频路线保留绿幕像素，在 WebGL 中实时生成 Alpha。两条路线都不能把最终页面背景烧进媒体。
4. 必须保留原始色键图片/视频。图集路线同时保留 Alpha 帧；视频路线保留可复现的色键参数和静态 Alpha 降级图。带背景预览只能是派生产物。
5. 在生成前写清色键颜色、Alpha/遮罩生成步骤和最终页面叠层方式。任意一项缺失都不得提交生成任务。
6. 用户要求更换背景时，只修改页面背景或重新合成；禁止重新生成主体。若现有产物无法这样处理，说明此前管线不合格并回到色键源修复。

### 参数模型

| 模型 | 常见输入 | 素材结构 |
|---|---|---|
| linear | 滚动、拖拽、进度、音量 | 一条有起止点的时间轴 |
| circular | 指针方向、旋钮、360° 展示 | 首尾连续的环形时间轴 |
| 2d | 指针 X/Y、陀螺仪二维倾斜 | 二维采样网格或可组合的两条轴 |
| discrete | hover、点击、成功、失败 | 多个独立片段和状态机 |

不要把真正的二维交互强行压成一条往返视频。若视觉只需要“看向某个方向”，通常用环形角度已经足够；若距离也会改变姿态，才制作二维采样。

## 2. 设计关键帧与视频片段

### A. 单段变化

适合一个主体从明确起点连续到达明确终点。

1. 收集主体身份、产品外观、Logo、比例和风格参考图。
2. 先分别生成起始图和终止图，在最终展示尺寸下验收构图、身份和细节。
3. 把验收后的图片作为 `first_frame` 与 `last_frame`，让 AI 视频只补全中间连续变化。
4. 对视频做程序化切帧、抠图、稳定、检测和打包。
5. 用参数控制帧，而不是让视频自行播放。

### B. 多阶段变化

适合“完整产品 → 爆炸图 → 核心部件特写 → 重新组装”等一镜到底叙事。

1. 先生成为 `K0…Kn` 的完整关键帧组，每张图只描述一个清晰阶段。
2. 第 `i` 段视频固定使用 `Ki` 为首帧、`Ki+1` 为尾帧。
3. 每段只承担一个主要语义变化，避免长视频同时拆解、穿越、变材质和换镜头。
4. 所有关键帧复用同一组身份参考、比例、风格、画幅和锚点。
5. 分段验收后再按时间轴拼接；用户反向滚动时直接反向取帧。

涉及提示词时阅读 [references/prompting.md](references/prompting.md)。

使用 MiniMax 生成动作母版时，先完成自动交付选择。结果为 `alpha-atlas` 才阅读并执行
[references/minimax-spritesheet.md](references/minimax-spritesheet.md)；结果为 `chroma-video` 则阅读
[references/chroma-video.md](references/chroma-video.md)。两条路线共享相同的关键帧、母版、插帧和验收门槛。

### C. 已有视频 → 交互资产

跳过生成，只做媒体分析与编译。先运行 `probe`，确认分辨率、帧率、帧数、时长和颜色格式。

### D. 已有序列帧 → 交互资产

直接从 `analyze` 开始。保留原始帧，修复输出写入新的目录。

### MiniMax 动作母版快速路径

只要路线包含“MiniMax 生成视频并拆成可交互帧”，就按以下顺序执行：

1. 用 Motion Brief 固定输入参数、动作方向、起止状态、锚点和静止帧。
2. 运行 `motion_budget.py --strict`，把 `delivery.selected` 写入 Motion Brief；不得让用户选择图集或视频。
3. 先生图并验收首帧、尾帧和参考图；静态构图未通过时不得提交视频。
4. 用 `video_job.py` 提交 MiniMax，保存母版视频、返回尾帧和脱敏任务元数据。
5. 完整观看母版并制作接触表；身份、肢体、动作方向或镜头错误时重新生成。
6. 强制插帧到 Motion Brief 指定帧率，默认 48 FPS：图集路线用 `optimize_motion.py interpolate --key auto`；视频路线由 `compile_scroll_video.py` 用 `--key none` 插帧并保留绿幕。
7. 检查原始帧、插帧接触表和对比报告；出现重影、轮廓撕裂、结构扭曲或新增闪帧时不得继续打包。
8. 对合格插帧序列完成必要的闭环清理、可选稳定、分析和最终接触表。
9. 最终分析通过后，严格按自动选择结果打包：`alpha-atlas` 生成单张 Alpha 图集；`chroma-video` 生成全关键帧绿幕 MP4。不要同时交付两套主实现。
10. 两条路线都用 `interactive-motion.ts` 控制整数帧；视频路线另外使用 `chroma-video-renderer.ts` 实时抠色。
11. 在目标 CSS 尺寸、DPR、冷缓存、快速反向和移动端条件下验收。

后续命令和停止条件按 `delivery` 分别见
[references/minimax-spritesheet.md](references/minimax-spritesheet.md) 与
[references/chroma-video.md](references/chroma-video.md)。

## 3. 先生图，再生成动作母版

1. 先按最终 CSS 尺寸、目标 DPR、帧数和纹理上限运行资源预算检查；预算不通过时不要生成完整视频。
2. 根据参考图生成首尾关键帧；多阶段动画同时生成所有中间关键帧。
3. 在最终展示尺寸下逐张检查身份、Logo、结构、比例、画幅、锚点和风格。关键帧未通过时不得提交视频。
4. 关键帧分辨率至少覆盖最终显示尺寸乘以目标 DPR，不要把“源视频分辨率较高”等同于“图集单帧足够清晰”。
5. 固定镜头、画幅、主体大小和锚点，除非镜头运动本身就是交互内容。
6. 一条视频只承担一个连续变量；复杂状态拆成多个首尾帧片段。
7. 闭环动画明确规定运动方向、首尾姿态和“不中途停顿、不折返”。
8. 所有生成素材必须使用均匀色键背景。背景均匀比严格命中某个十六进制颜色更重要，因为脚本会从边缘采样真实色键。
9. 若主体含大量绿色，用 `#FF00FF`；否则默认 `#00FF00`。
10. 避免运动模糊、景深、阴影落地、半透明粒子和接触边缘的道具，这些会破坏抠图和帧稳定性。
11. 无论最终页面使用什么颜色，都要保留原始色键视频、Alpha 帧或独立遮罩；不得只保留已经合成背景的素材。

生成后先看完整视频和编号接触表，不要只看首帧。

### 在生成前检查资源预算

使用 `scripts/motion_budget.py` 把最终显示约束转换成最低单帧像素，并自动选择交付方式：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 123 \
  --display 268x468 \
  --dpr 2 \
  --driver scroll \
  --parameter-space linear \
  --scroll-pages 4 \
  --max-texture 4096 \
  --report build/motion-budget.json \
  --strict
```

已有源视频或图集时，同时传入尺寸进行阻断检查：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 123 \
  --display 268x468 \
  --dpr 2 \
  --driver scroll \
  --parameter-space linear \
  --source 768x1344 \
  --report build/motion-budget.json \
  --strict
```

- `delivery.selected` 是唯一交付决策：`alpha-atlas` 或 `chroma-video`。Agent 直接执行，不向用户抛技术选项。
- `requiredCell` 是每个可交互画面的最低像素；图集用作单元格尺寸，视频用作输出分辨率下限。
- 滚动驱动必须传 `--scroll-pages`；默认按每屏 24 个独立姿态检查采样密度。阻尼只能平滑输入，不能补出不存在的姿态。
- `--strict` 存在上采样、源素材不足、时间采样不足，或必须使用图集的二维参数超预算时返回非零退出码。
- 资源格式、阈值和超预算处理全部采用预算报告，不在这里重复判断。
- 二维参数不能压成一条视频。若二维图集超预算，自动降低采样密度、拆状态或调整显示尺寸，并重新预算。
- 正式生成前先把静态参考帧按最终 CSS 尺寸放入目标页面，检查构图、裁切和边缘质量；静态预览未通过时停止生产。

完整规则、阈值和示例见 [references/delivery-selection.md](references/delivery-selection.md)。

### 用生成接口锁定首尾帧

Skill 自带 `scripts/video_job.py`，用于提交、轮询和下载 ZenMux / MiniMax 原生视频任务。它不是动作生成器的替代品，而是把重复的接口调用、图片编码、状态轮询和结果保存程序化。

- 闭环动作：同一张构图同时传为 `first_frame` 和 `last_frame`。这能明显加强接缝约束，但仍需检查首尾差异和运动方向。
- 单向转场：首帧和尾帧传不同图片，动作提示词只描述中间如何连续变化。
- MiniMax H3 的 `reference_image` 与 `first_frame` / `last_frame` 属于两个互斥模式。
  首尾帧转场需要锁定身份时，先把身份和风格生成进验收后的首尾关键帧，不能再附加
  `reference_image`。
- 可复现：模型支持时固定 `seed`，并保存返回的任务元数据和尾帧。
- 默认传 5 秒 `duration`。使用 `frames` 时不传 `duration`；二者不能同时出现。
- `generate_audio=false` 不能作为最终无音轨保证；网页编译阶段始终显式使用 `-an`。
- 模型实际输出时长和帧数可能略高于请求，并可能在尾帧产生停顿。必须先 `probe`，
  再按目标尾帧清理，不能假设请求值就是成片值。
- 模型拒绝某个参数时必须明确报告，再选择降级方案；不要静默删掉首尾帧。

`video_job.py` 会优先读取 `ZENMUX_API_KEY`，没有环境变量时自动读取已经保存的本地
配置。提交前按“首次配置 API Key”检查一次即可。

闭环示例：

```bash
python3 "$OIL_MOTION/scripts/video_job.py" \
  --prompt-file motion-prompt.txt \
  --first-frame reference-green.png \
  --loop-frame \
  --resolution 768p \
  --ratio 1:1 \
  --duration 5 \
  --seed 42 \
  --output source/motion-loop.mp4
```

## 4. 使用确定性媒体流水线

所有命令都使用 Skill 自身绝对路径：

```bash
OIL_MOTION="$HOME/.codex/skills/oil-motion"
```

安装依赖：

```bash
python3 -m pip install -r "$OIL_MOTION/scripts/requirements.txt"
ffmpeg -version
ffprobe -version
```

检查视频：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" probe source.mp4
```

插帧和打包严格执行 `delivery` 对应的参考流程：图集读取
[references/minimax-spritesheet.md](references/minimax-spritesheet.md)，视频读取
[references/chroma-video.md](references/chroma-video.md)。不要混用两条路线的抠色命令。

需要按目标体积自动压缩时，阅读
[references/optimization.md](references/optimization.md)，再使用
`scripts/optimize_motion.py`。不要手动反复猜 WebP 质量。

`alpha-atlas` 的固定身体动画若存在轻微大小和位置漂移，可选用稳定化。自由运动和镜头运动不要使用：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" normalize frames frames-stable \
  --anchor bottom --max-scale-change 0.08
```

`alpha-atlas` 单独检查和打包：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" analyze frames \
  --output build/analysis.json
python3 "$OIL_MOTION/scripts/motion_pipeline.py" contact frames \
  --output build/contact-sheet.jpg --columns 8
python3 "$OIL_MOTION/scripts/motion_pipeline.py" atlas frames \
  --output build/motion.webp \
  --manifest build/motion.json \
  --cell-width 240 --cell-height 240 --quality 88
```

闭环视频若为了贴合尾帧而产生尾部停顿，先选择最接近首帧的接缝并删除近重复帧：

```bash
python3 "$OIL_MOTION/scripts/loop_cleanup.py" frames frames-clean \
  --seam-window 24 \
  --duplicate-threshold 0.003 \
  --report build/loop-cleanup.json
```

该工具只做确定性选帧，不生成角色动作，也不对相邻帧做透明叠加。接缝选错时扩大或缩小 `--seam-window`，不要为了减少帧数盲目提高重复阈值。

首尾不同的单向转场传入目标尾帧，工具会裁掉模型在尾帧上的多余停顿：

```bash
python3 "$OIL_MOTION/scripts/loop_cleanup.py" frames frames-clean \
  --end-reference last-frame.png \
  --seam-window 24 \
  --duplicate-threshold 0.003
```

需要同一主体从轨道一端精确移动到另一端时，先准备透明主体层，再用程序生成身份和尺寸完全一致的首尾帧：

```bash
python3 "$OIL_MOTION/scripts/compose_travel_frames.py" subject.png \
  --first-output first-green.png \
  --last-output last-green.png \
  --size 864x1536 \
  --subject-height 0.36 \
  --subject-anchor-x 0.535
```

该工具只负责扁平轨道、缩放和精确位移。中间的结构形变、接触关系和前后遮挡仍由首尾帧约束下的视频模型完成。

脚本默认拒绝覆盖非空目录。只有确认目标是本次构建产物时才使用 `--force`。

## 5. 选择网页资产格式

阅读 [references/delivery-selection.md](references/delivery-selection.md) 和
[references/runtime.md](references/runtime.md)，运行 `motion_budget.py` 后直接采用
`delivery.selected`，不向用户询问格式偏好：

- `alpha-atlas`：随机访问、环形或小型资源，且单张图集满足纹理与解码内存预算。构建时离线抠成 Alpha。
- `chroma-video`：一维长线性控制、大尺寸，或一维随机访问的 Alpha 图集超预算。保留绿幕视频，由 WebGL 实时抠成 Alpha；随机访问场景必须额外验收 seek 延迟。
- `2d`：保持离散帧语义，只能走 Alpha 图集；超预算时自动降低采样或拆状态，不能压成线性视频。
- `discrete`：预算内使用 Alpha 图集；超预算时拆成独立状态或转场并分别预算，不能把无序状态拼成一条视频。

两条路线都是由参数控制整数帧，不使用 `<video autoplay>`。页面背景始终独立，换背景不重新生成主体。

## 6. 实现交互控制

从 [assets/interactive-motion.ts](assets/interactive-motion.ts) 复制通用帧控制运行时，再按项目框架封装。若自动选择 `chroma-video`，同时使用
[assets/chroma-video-renderer.ts](assets/chroma-video-renderer.ts)。

### 连续控制的默认策略

1. 将输入转换成归一化参数。
2. 参数映射为目标帧，不直接写当前帧。
3. 用有最大速度限制的 `smoothDamp` 追踪目标帧。
4. 环形序列使用最短环形距离，避免跨越首尾时倒转一整圈。
5. 每个 `requestAnimationFrame` 最多写一次 DOM，而且只有整数帧改变时才更新画面。
6. 页面滚动和布局变化时，重新计算指针相对主体的位置；鼠标不动不代表相对位置没变。
7. 首帧和关键资源完成解码后再显示动画，避免初次交互时闪帧。

### 初始和失去输入

- 初始显示 `rest_state`，不要从透明度交叉渐变到目标帧。
- 第一次输入从当前帧平滑追踪，不要瞬间跳到目标。
- 输入停止时可以保持当前位置、缓慢回到静止帧，或执行单独的待机片段；由 Motion Brief 决定。
- `prefers-reduced-motion` 下使用静态帧或低频切换。

### 移动端

- 优先使用触摸位置；需要陀螺仪时显式请求权限。
- 校准初始姿态，处理屏幕旋转方向，并限制输入范围。
- 陀螺仪不可用或被拒绝时保留静态或触摸方案。

## 7. 验收

涉及异常时阅读 [references/qa.md](references/qa.md)。

至少检查：

- 主体身份、比例、锚点和光线在全序列一致。
- 没有多余肢体、瞬时变形、亮度闪烁、重复帧堆积或首尾断层。
- 已完成目标帧率插帧；原始与插帧接触表均已检查，未出现重影、轮廓撕裂或结构扭曲。
- 色键完全透明，边缘没有绿色/洋红溢色，细线和半透明细节仍完整。
- 构建报告包含自动选择结果、选择依据和阈值；实现与 `delivery.selected` 一致，没有要求用户做格式决策。
- 快速反复移动输入时不粘滞、不抽动、不越界。
- 低速跟随自然，高速转向受限但不明显落后。
- 滚动、缩放、设备旋转后输入仍相对正确。
- 首屏资源预加载，弱网有静态替代，不阻塞整页超过合理时间。
- 在目标 DPR 的实际 CSS 尺寸下清晰；不得放大图集单帧，也不要用低分辨率源制作高分辨率图集。
- 用 `motion_budget.py --strict` 验证像素和纹理预算，并在浏览器中以 100% 页面缩放检查真实渲染，不以原视频或接触表代替。

## 8. 生成动画原理展示页

需要向用户展示“母版视频 → 雪碧图 → 输入映射 → 当前帧”时，阅读
[references/explainer.md](references/explainer.md)，再运行
`scripts/create_explainer.py` 生成独立 HTML。模板支持指针方向、横向指针、拖拽、
滚动和自动播放；不要复制项目私有角色或文案来冒充通用模板。

## 输出结构

```text
motion-name/
├── source/                 # 参考图和原始视频
├── frames/raw/             # 原始切帧
├── frames/interpolated/    # 图集路线保留的 Alpha 插帧母版
├── frames/final/           # 图集路线清理后的最终帧
├── qa/
│   ├── analysis.json
│   └── contact-sheet.jpg
└── final/
    ├── motion.webp         # alpha-atlas；与下方视频二选一
    ├── motion.json         # alpha-atlas 清单
    ├── motion-chroma-desktop.mp4  # chroma-video；与上方图集二选一
    ├── motion-chroma-mobile.mp4
    ├── poster-alpha.png    # chroma-video 静态降级图
    ├── compile.json        # chroma-video 清单与自动选择证据
    └── implementation.*    # 项目运行时代码
```

每次只交付自动选中的一种主资源，另一种不重复实现。交付时说明：交互参数模型、自动选择结果与依据、最终提示词、色键源、处理命令、关键参数、分析报告、最终资产、页面背景归属、Alpha 生成位置、运行时实现和静态降级方案。
