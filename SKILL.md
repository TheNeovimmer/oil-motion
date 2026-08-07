---
name: oil-motion
description: "Ideate, generate, process, optimize, implement, and explain high-performance interactive web motion made from AI image-to-video. Use for product reveals, exploded views, assembly or disassembly, cutaways, material transformations, camera fly-throughs, chapter transitions, diagrams, interfaces, characters, mascots, or other continuous visual changes driven by pointer position, scroll progress, dragging, touch, device orientation, audio, data, or component state. The core workflow is reference images → generated and approved first/last keyframes → MiniMax H3 video between keyframes → deterministic frame extraction, QA, interpolation, compression, atlas/video packaging, runtime mapping, and reusable explainers. Do not use for ordinary one-off CSS transitions or conventional linear video editing with no interactive control."
---

# Oil Motion

从目标出发构思交互动画，先生图锁定首尾状态，再用 AI 视频补全连续动作，最后编译成由连续参数控制的网页动画。生成模型负责主要画面和动作，程序只负责可重复、可测量的媒体处理与运行时控制。

确定性媒体流水线需要 Python 3、Pillow、ffmpeg 和 ffprobe。

默认视频模型固定为 ZenMux 的 `minimax/minimax-h3`。只有用户明确要求更换，或
MiniMax 无法完成目标时，才讨论其他模型；不要让用户在没有必要时承担模型选择。

## 核心原则

1. 先定义交互参数和关键状态，再生图、再生视频。没有参数模型和首尾关键帧，就不提交视频。
2. 唯一视觉生产主线是：参考图 → 生成并验收首尾关键帧 → AI 视频补全连续变化。多阶段动画拆成多组相邻关键帧，逐段生成并串联。
3. 把 AI 视频视为动作母版，不把它直接当最终实现。
4. 程序只处理确定性工作：探测、切帧、抠色、去溢色、稳定、查重、检测闪帧、缩放、图集打包、清单生成、预加载、文字覆盖和交互映射。
5. 让生成模型处理主要视觉内容和连续性：角色身份、产品形态、结构变化、姿态、镜头内动作和风格。
6. 先保留高分辨率母版，检查通过后再压缩。不要从压缩后的网页资源继续加工。
7. 默认使用单图层离散换帧，不通过相邻帧透明叠加伪造流畅度；叠加会产生虚影。
8. 动画创意必须同时说明输入、视觉回应和表达目的；不要只罗列效果名称。
9. 压缩前必须确认最大实际 CSS 展示尺寸和目标 DPR。清晰度是硬门槛，目标体积是第二约束；无法同时满足时更换资产格式，不得继续缩小。
10. 先分析对象能如何变化，再设计首尾关键帧。绿幕、雪碧图和视频编码只是交付手段，不是创意入口。

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
delivery_format: 视频、图集或序列帧
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
background: transparent | chroma | opaque
anchor: fixed-body | center | bottom | free
destination: 页面位置、显示尺寸和设备
quality_target: 分辨率、参数采样密度、文件预算
reduced_motion: 静态替代状态
```

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

使用 MiniMax 生成动作母版并交付雪碧图时，必须同时阅读并按顺序执行
[references/minimax-spritesheet.md](references/minimax-spritesheet.md)。该流程是默认主路径，
不得跳过阶段门槛或直接从生成视频打包最终图集。

高分辨率、不透明、由滚动控制的一维长时间轴，优先阅读
[references/minimax-scroll-video.md](references/minimax-scroll-video.md)，编译成桌面与
移动端全关键帧 MP4，不要把十几张巨型图集切片交给浏览器。

### C. 已有视频 → 交互资产

跳过生成，只做媒体分析与编译。先运行 `probe`，确认分辨率、帧率、帧数、时长和颜色格式。

### D. 已有序列帧 → 交互资产

直接从 `analyze` 开始。保留原始帧，修复输出写入新的目录。

### MiniMax 动作母版快速路径

只要路线包含“MiniMax 生成视频并拆成可交互帧”，就按以下顺序执行：

1. 用 Motion Brief 固定输入参数、动作方向、起止状态、锚点和静止帧。
2. 运行 `motion_budget.py --strict`，预算不通过就先改尺寸、帧数或资产格式。
3. 先生图并验收首帧、尾帧和参考图；静态构图未通过时不得提交视频。
4. 用 `video_job.py` 提交 MiniMax，保存母版视频、返回尾帧和脱敏任务元数据。
5. 完整观看母版并制作接触表；身份、肢体、动作方向或镜头错误时重新生成。
6. 依次完成抠图切帧、必要的闭环清理、可选稳定、分析和最终接触表。
7. 最终分析通过后按访问模式选择 `atlas` 或 `compile_scroll_video.py`；不要用
   `build` 隐藏中间验收。
8. 用 `interactive-motion.ts` 实现图集映射；滚动视频按
   [references/minimax-scroll-video.md](references/minimax-scroll-video.md) 实现
   `currentTime` 映射、预加载、阻尼、限速和静态降级。
9. 在目标 CSS 尺寸、DPR、冷缓存、快速反向和移动端条件下验收。

每一步的参数矩阵、命令和停止条件见
[references/minimax-spritesheet.md](references/minimax-spritesheet.md)。

## 3. 先生图，再生成动作母版

1. 先按最终 CSS 尺寸、目标 DPR、帧数和纹理上限运行资源预算检查；预算不通过时不要生成完整视频。
2. 根据参考图生成首尾关键帧；多阶段动画同时生成所有中间关键帧。
3. 在最终展示尺寸下逐张检查身份、Logo、结构、比例、画幅、锚点和风格。关键帧未通过时不得提交视频。
4. 关键帧分辨率至少覆盖最终显示尺寸乘以目标 DPR，不要把“源视频分辨率较高”等同于“图集单帧足够清晰”。
5. 固定镜头、画幅、主体大小和锚点，除非镜头运动本身就是交互内容。
6. 一条视频只承担一个连续变量；复杂状态拆成多个首尾帧片段。
7. 闭环动画明确规定运动方向、首尾姿态和“不中途停顿、不折返”。
8. 抠图素材优先使用均匀色键背景。背景均匀比严格命中某个十六进制颜色更重要，因为脚本会从边缘采样真实色键。
9. 若主体含大量绿色，用 `#FF00FF`；否则默认 `#00FF00`。
10. 避免运动模糊、景深、阴影落地、半透明粒子和接触边缘的道具，这些会破坏抠图和帧稳定性。

生成后先看完整视频和编号接触表，不要只看首帧。

### 在生成前检查资源预算

使用 `scripts/motion_budget.py` 把最终显示约束转换成最低单帧像素和图集分片数：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 123 \
  --display 268x468 \
  --dpr 2 \
  --scroll-pages 4 \
  --max-texture 4096 \
  --access random
```

已有源视频或图集时，同时传入尺寸进行阻断检查：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 123 \
  --display 268x468 \
  --dpr 2 \
  --source 768x1344 \
  --cell 192x336 \
  --strict
```

- `requiredCell` 是交付图集每一帧的最低像素，不是源视频画幅。
- 滚动驱动必须传 `--scroll-pages`；默认按每屏 24 个独立姿态检查采样密度。阻尼只能平滑输入，不能补出不存在的姿态。
- `--strict` 存在上采样、源素材不足或纹理越界时返回非零退出码。
- 单图集放不下时按访问模式选择分片图集、视频或 WebCodecs，不要为了塞进一张图集降低单帧清晰度。
- 正式生成前先把静态参考帧按最终 CSS 尺寸放入目标页面，检查构图、裁切和边缘质量；静态预览未通过时停止生产。

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

密钥只从环境变量读取：

```bash
export ZENMUX_API_KEY="..."
```

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

一键生成透明帧、报告、接触表、WebP 图集和清单：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" build source.mp4 build/motion \
  --fps 24 \
  --key auto \
  --cell-width 240 \
  --cell-height 240 \
  --quality 88
```

背景不需要透明时：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" build source.mp4 build/motion \
  --fps 24 --key none --cell-width 320 --cell-height 180
```

仅切帧：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" extract source.mp4 frames \
  --fps 24 --key auto
```

只有源视频帧率不足且相邻动作已经连续时，才尝试运动估计插帧：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" extract source.mp4 frames-48 \
  --fps 48 --interpolate --key auto
```

需要补帧前后对比或按目标体积自动压缩时，阅读
[references/optimization.md](references/optimization.md)，再使用
`scripts/optimize_motion.py`。不要只凭“生成成功”判断补帧质量，也不要手动反复猜
WebP 质量和视频码率。

固定身体的朝向动画若存在轻微大小和位置漂移，可选用稳定化。自由运动和镜头运动不要使用：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" normalize frames frames-stable \
  --anchor bottom --max-scale-change 0.08
```

单独检查和打包：

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

高分辨率、不透明的滚动转场可一键编译成桌面与移动端全关键帧 MP4：

```bash
python3 "$OIL_MOTION/scripts/compile_scroll_video.py" \
  source/master.mp4 build/scroll \
  --end-reference source/last-frame.png \
  --desktop-width 1920 \
  --mobile-width 1280
```

两个宽度都应按“最大实际 CSS 展示宽度 × 目标 DPR”填写。脚本保持源画幅、禁止默认
上采样、裁尾、查重、生成接触表与分析报告，并使用 `-an` 移除音轨。详细规则见
[references/minimax-scroll-video.md](references/minimax-scroll-video.md)。

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

阅读 [references/runtime.md](references/runtime.md)，再根据访问方式选择：

- 透明、短时长、需要任意跳帧：WebP/PNG 图集。
- 帧数很多、图集超过纹理限制：分片图集或序列帧。
- 长时间轴、高分辨率、主要顺序播放：视频解码或 WebCodecs。
- 一维滚动需要频繁定位且不透明：全关键帧 MP4，换取更稳定的 seek。
- 少量离散状态：多个短视频或多条图集。

不要因为已经生成了视频就默认 `<video autoplay>`。随机定位和交互响应才决定运行时格式。

## 6. 实现交互控制

从 [assets/interactive-motion.ts](assets/interactive-motion.ts) 复制通用运行时，再按项目框架封装。

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
- 色键完全透明，边缘没有绿色/洋红溢色，细线和半透明细节仍完整。
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
├── frames/final/           # 抠图、稳定后的母版帧
├── qa/
│   ├── analysis.json
│   └── contact-sheet.jpg
└── final/
    ├── motion.webp         # 随机访问图集路线
    ├── motion-scrub-*.mp4  # 高分辨率一维滚动路线
    ├── motion.json         # 或 compile.json，保存帧数、尺寸和映射信息
    └── implementation.*    # 项目运行时代码
```

交付时说明：交互参数模型、最终提示词、源视频、处理命令、关键参数、分析报告、最终资产、运行时实现和降级方案。
