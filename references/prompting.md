# AI 视频动作提示词

## 固定工作流：先生图，再生视频

不要直接用一段文字生成完整动作。先完成：

1. 用原始参考图生成并验收起始关键帧。
2. 用同一组参考图生成并验收结束关键帧。
3. 复杂叙事先生成全部中间关键帧 `K1…Kn`。
4. 每次把两张相邻关键帧作为首尾帧提交给 MiniMax。
5. 验收每段视频后，再由程序切帧、拼接、压缩和映射交互。

视频提示词只描述两张已确定图片之间如何连续变化，不再承担终点设计。主体身份、产品结构、
Logo、构图和风格必须先在关键帧图片中解决。

## 写提示词前先决定

先写清楚：

1. 哪个连续参数控制动画。
2. 参数的起点、终点和方向。
3. 主体哪些部分允许变化，哪些必须固定。
4. 是否闭环。
5. 使用绿色还是洋红色键，以及如何保证四角与时间维度均匀。
6. 抠色后如何以 Alpha 主体叠加到页面背景。
7. 最终会按时间、角度、二维位置还是状态取帧。

生成模型负责动作语义和画面连续性，不负责精确切帧、透明通道、帧编号、压缩或图集。

## 正确选择首尾帧模式或参考图模式

MiniMax H3 的两种图片输入模式互斥，不能混用：

- `first_frame` 决定起始构图、角色位置、比例、镜头和背景。
- `last_frame` 决定动作最终必须到达的画面。
- `reference_image` 只用于不传首尾帧的参考生成模式。
- `seed` 用于重跑和局部修复时减少无关变化。
- `return_last_frame` 用于自动比较首尾差异。

精确交互动画默认使用首尾帧模式。需要锁定身份、面部、服装、产品细节或插画风格时，
先在生图阶段生成并验收一致的关键帧，不能在视频请求中再附加 `reference_image`。
混用会触发接口错误 `2013`。

闭环动作优先把**同一张已验收构图**同时作为首帧和尾帧，再在提示词里描述完整一圈的方向、速度和遮挡变化。不同首尾帧适合单向转场，不适合要求无缝循环。

首尾帧约束不是免检条件：模型仍可能中途折返、停顿、生成多余肢体，或在最后几帧硬贴回首帧。必须检查完整视频、接触表、重复帧分布和首尾差异。

## 通用身份锁定段

将下面内容放在动作描述前，并替换尖括号：

```text
Use the supplied first and last frames as the exact identity and design
references for <SUBJECT>. Preserve the same silhouette, anatomy, face, clothing or product
geometry, colors, line work, texture, and proportions in every frame. The
subject remains the same size and at the same anchored position throughout the
shot. Do not add, remove, duplicate, or redesign any body part, accessory,
feature, logo, control, or prop.
```

如果主体是插画，补充：

```text
Preserve the original illustration style exactly. Keep line thickness,
halftone texture, flat color regions, and edge sharpness consistent. Do not
turn the subject into volumetric CGI, photorealistic, painterly, or glossy imagery.
```

## 固定镜头段

```text
Locked camera and locked framing. No camera pan, tilt, zoom, orbit, shake,
reframing, perspective change, lens change, depth of field, or lighting change.
The body and contact point remain fixed. Only <ALLOWED_PARTS> may move.
```

只有镜头运动本身需要被滚动控制时才删除这段，并明确描述镜头轨迹。

## 绿幕段

默认使用 `#00FF00`。主体含绿色时改用 `#FF00FF`。

```text
The entire background is one perfectly uniform flat chroma-key <KEY_COLOR>
rectangle in every frame. No gradient, texture, noise, floor plane, horizon,
shadow, reflection, glow, particles, color variation, or lighting falloff on
the background. Keep the subject fully separated from all image borders with
generous padding. No cast shadow. No green/magenta object or reflected spill on
the subject. No text, subtitle, watermark, border, or UI.
```

模型未必严格生成指定色值，所以最重要的是四周和时间维度保持均匀。后续脚本会从边缘采样真实背景色。

## 环形方向动画

适合视线、转头、产品方向、旋钮和 360° 展示：

```text
Create one continuous clockwise directional cycle. Start with <SUBJECT> looking
oriented toward <START_DIRECTION>. An invisible target moves at a constant
angular speed around the subject through a complete 360-degree circle, and
<SUBJECT> follows it smoothly with <ALLOWED_PARTS>. Pass through every
intermediate direction without pausing, snapping, reversing, returning to the
front early, or holding any direction. End at the same pose and direction as
the first frame so the cycle joins cleanly. Keep <FIXED_PARTS> completely still.
Use natural anatomical deformation, but no secondary idle motion, blinking,
breathing, tail movement, or unrelated action.
```

若运行时不需要闭环，改为：

```text
Move once continuously from <START_DIRECTION> to <END_DIRECTION>. Do not return
to the start and do not pause at intermediate directions.
```

## 产品拆解与爆炸图

先根据真实产品参考图分别生成完整态和爆炸态图片。两张图都通过人工验收后，再作为精确首尾帧；
不要让视频模型凭文字发明最终结构。

```text
Use the supplied first and last frames as exact geometry, identity, material,
logo, component-count, alignment, camera, lighting, and composition references.
Create one continuous transformation from the fully assembled <PRODUCT> to the
approved exploded view. Separate the existing shell, display, battery, boards,
connectors, cameras, and fasteners only along their physically plausible axes.
Preserve every component's exact shape, scale, orientation, color, and relative
order. Keep all parts readable and non-overlapping at the final state. No new,
missing, duplicated, melted, or redesigned components. No cuts, camera changes,
scale breathing, motion blur, labels, or unrelated motion. Every intermediate
frame must be a stable reversible assembly state suitable for scroll scrubbing.
```

爆炸方向、间距、部件数量和最终构图必须先在尾帧图片中确定。视频负责从完整态连续过渡到
该尾帧；文字标注、数字和部件高亮在生成后由程序覆盖，避免 AI 视频生成不稳定文字。

## 镜头穿越

镜头运动本身是交互内容时，不使用固定镜头段，改为明确一条可逆轨迹：

```text
Create one continuous forward camera move from <START_VIEW> to <END_VIEW>.
Follow the supplied path through <ORDERED_LANDMARKS> without cuts, orbiting,
sideways drift, speed jumps, focus pumping, or lens changes. Keep product
geometry, lighting, scale relationships, and landmark positions consistent.
Every frame must remain sharp and readable when scroll playback stops. The
reverse frame order must also form a natural backward move.
```

长距离穿越不要只给起点和终点。先生成路径上的中间关键帧，保证主体、空间地标、比例和风格
一致，再把相邻关键帧分别生成短视频。

## 多段关键帧串联

先建立 `K0 → K1 → K2…Kn`：

- `Ki` 和 `Ki+1` 是第 `i` 段视频的精确首尾帧。
- 所有关键帧复用同一组参考图、画幅、风格约束和主体比例。
- 每段只写一个主要变化，时长通常为 3–6 秒。
- 模型返回的尾帧只有与已验收的 `Ki+1` 一致时才能继续作为下一段输入；否则仍使用原始
  `Ki+1`，不要让误差逐段累积。
- 拼接后逐帧检查接缝；若接缝不稳，重做对应短片，不重做整条时间轴。

## 指针二维动画

二维输入不能只靠一条左右转头视频准确表达。优先选择以下方案：

### 方案 A：角度足够

让视频生成完整方向环，运行时用 `atan2(y, x)` 映射角度。距离只影响平滑速度或回正强度，不改变姿态。

### 方案 B：二维采样

生成固定网格中的多个短片或关键姿态，例如：

```text
Generate the same subject and framing for target position <X_POSITION>,
<Y_POSITION>. Keep the exact body anchor, subject scale, lighting, style, and
background used in every other grid sample. Move only <ALLOWED_PARTS> toward
that target and settle naturally. No entrance or exit motion.
```

二维网格至少覆盖左上、上、右上、左、中、右、左下、下、右下。用程序统一锚点和尺寸，再做双线性邻域选择或插值。不要要求模型在一条视频中遍历网格后直接随机访问。

## 滚动时间轴动画

适合产品拆解、页面叙事、图表展开和场景变换：

```text
Create a single continuous transformation designed for frame-by-frame scroll
scrubbing. At frame 0, <START_STATE>. Over the shot, <ORDERED_CHANGES>. At the
last frame, <END_STATE>. Every intermediate frame must be a meaningful stable
progress state. Use constant visual continuity with no cuts, dissolves, sudden
jumps, duplicated holds, camera shake, motion blur, or unrelated motion. Keep
the composition readable when playback is stopped on any frame.
```

把多个变化写成相对进度阶段，例如 `0–35%` 完成第一阶段、`35–80%` 推进主要关系、
`80–100%` 到达最终状态。要求每个阶段持续变化，并明确禁止模型在前段快速完成主要
动作、后段只保留近重复帧。百分比用于约束节奏，不要求模型输出精确帧编号；实际节奏
仍需通过接触表检查，必要时裁剪或重定时。

滚动序列不一定需要 24–60 FPS。优先生成清晰的语义关键阶段，再由程序决定抽帧密度。

## 离散状态动画

每个状态单独生成，不让一个长视频同时包含 hover、点击、成功和失败：

```text
Create a short transition from the exact neutral pose to the exact <STATE>
pose. The first frame must match the shared neutral reference exactly. Hold the
final pose only briefly. No camera movement, no unrelated idle motion, and no
return transition.
```

反向状态优先用程序倒放；只有倒放不符合物理规律时再单独生成。

## 产品 360° 提示词

```text
Use the provided product image as the exact geometry, material, color, logo,
control, and proportion reference. Rotate the product once clockwise around its
vertical center at a constant angular speed. Locked orthographic-like camera,
fixed scale, fixed center, fixed lighting, no perspective breathing, no added
details, no deformation, no text changes, no logo changes. The first and last
frames join exactly.
```

## 失败修复提示词

一次只修一个问题，同时重申所有不变量：

```text
Keep the subject identity, design, style, camera, framing, scale, anchor,
background, lighting, and correct motion unchanged. Fix only this issue:
<ONE_PRECISE_ISSUE>. Do not add any new motion or detail.
```

常见修复：

- `Keep every approved component unchanged; remove the duplicated connector.`
- `Keep the body fixed; eliminate scale pulsing and center drift.`
- `Remove the one-frame brightness flash; lighting is identical in every frame.`
- `Continue through the angle without pausing or snapping.`
- `Make the last frame match the first frame exactly for a seamless loop.`

## 负面约束

按需要加入，不必机械复制全部：

```text
No cuts, morphing, identity drift, scale breathing, position drift, duplicated
limbs, missing limbs, extra objects, blinking, idle sway, motion blur, ghosting,
frame blending, lighting flicker, shadows on the background, camera movement,
text, watermark, border, or style change.
```

## 分辨率和时长

- 先生成 3–6 秒的单变量动作，长序列更容易漂移。
- 以最终显示尺寸的 2 倍为最低母版分辨率。
- 生成模型只负责连续动作母版；母版通过内容验收后统一程序插帧，默认目标为 48 FPS。提示词不要要求模型自行提高帧率。
