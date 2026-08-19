# 运行时选择与交互映射

本文档是输入映射、阻尼、预加载和性能的唯一事实源。路线选择规则与预算命令见
[delivery-selection.md](delivery-selection.md)；路线专属的编译和接入见
[chroma-video.md](chroma-video.md)、[baked-video.md](baked-video.md) 与
[minimax-spritesheet.md](minimax-spritesheet.md)。

## 先执行自动选择

先按 Concept Contract 的 `background_owner` 运行 `motion_budget.py`（见
[delivery-selection.md](delivery-selection.md)），实现 `delivery.selected` 返回的
路线。格式由 Agent 自动决定，不询问用户；三条路线都不能退回 `<video autoplay>`。

图集文件体积小不代表解码内存小。RGBA 解码内存约为 `宽 × 高 × 4`。3840×3600 图集约需
52.7 MiB，因此必须按真实显示尺寸和目标设备预算。

## 图集约束

- 单元格尺寸统一，所有帧使用同一主体锚点。
- 单元格宽高至少为最终 CSS 宽高乘以目标 DPR；禁止依赖浏览器把低分辨率单帧放大。
- 默认单张图集宽高不超过 4096；超出时让自动选择切换到视频。二维参数不能切成线性
  视频，必须降低采样或拆状态后重新预算。
- 使用清单保存帧数、列数、行数、单元格尺寸、静止帧和参数映射。
- CSS `background-size` 为 `columns × 100%` 和 `rows × 100%`。
- 切换帧只更新 `background-position`，不要创建多个透明图片层。

```css
.motion-sprite {
  width: 240px;
  aspect-ratio: 1;
  background-image: url("./motion.webp");
  background-repeat: no-repeat;
  background-size: 1600% 1500%;
  will-change: background-position;
}
```

## 视频路线约束

- 只用于一维时间参数。chroma 路线优先用于 `linear` 顺序访问；环形或一维随机访问
  只有在图集超预算时才使用，并增加 seek 延迟验收；二维输入不使用视频。baked 路线
  遇到二维或离散输入时拆成多条独立片段分别预算。
- 使用全关键帧 MP4，让整数帧 `currentTime` seek 的正反向延迟更稳定。
- 视频尺寸至少覆盖最大实际 CSS 尺寸乘目标 DPR，同时不得超过母版分辨率。
- chroma 路线保留均匀绿幕，由 `chroma-video-renderer.ts` 绘制为透明 Canvas，页面
  背景、文字和其他视觉层位于 Canvas 外部；baked 路线直接绘制完整画面，不做任何
  抠色、色键着色器或阈值调参。
- WebGL 或视频失败时回退静态 Alpha 首帧，不得显示原始绿幕。
- 运行时从 `compile.json.runtime` 读取帧数、帧率、语义锚点和完整 `keying` 参数；不得在页面中维护第二份常量。
- `chroma-video-renderer.ts` 的 `dominance-v2` 必须与编译器编码后 QA 同步更新。只改 Shader 或只改 Python 都视为契约破坏。

完整编译和验收规则见 [chroma-video.md](chroma-video.md)。

## 一维时间参数

```text
progress = clamp((scrollY - start) / (end - start), 0, 1)
targetFrame = progress * (frameCount - 1)
```

滚动监听只记录目标值，在 `requestAnimationFrame` 中更新。页面布局变化时重新计算起止位置。

## 环形方向参数

```text
angle = atan2(pointerY - anchorY, pointerX - anchorX)
normalized = mod(angle - startAngle, 2π) / 2π
targetFrame = normalized * frameCount
```

当前帧追踪目标帧时使用最短环形距离：

```text
delta = wrap(target) - wrap(current)
if delta > frameCount / 2: delta -= frameCount
if delta < -frameCount / 2: delta += frameCount
```

闭环素材必须检查最后一帧到第一帧的连接。若生成视频本身不是闭环，不要在运行时强行 wrap。

## 二维参数

二维网格的离散索引：

```text
column = round(clamp(x, 0, 1) * (columns - 1))
row = round(clamp(y, 0, 1) * (rows - 1))
frame = row * columns + column
```

二维输入默认选择最近邻帧并用输入阻尼降低抖动。不要透明叠加相邻图片，避免产生虚影。

## 阻尼与速度

`lerp` 在帧率变化和频繁反向时容易出现粘滞。优先使用带速度状态和最大速度的 `smoothDamp`：

- `smoothTime` 控制追踪延迟。
- `maxSpeed` 限制不自然的快速扭动。
- 每次反向保留速度状态，避免机械停顿。
- `deltaTime` 设置上限，标签页恢复时避免巨幅跳帧。

默认从下面范围开始，再按动作尺度调整：

```text
smoothTime: 0.08–0.16 秒
maxSpeed: 每秒总帧数的 1.5–2.5 倍
deltaTime cap: 1/30 秒
```

## 初始和失去输入

- 初始显示 `rest_state`，不要从透明度交叉渐变到目标帧。
- 第一次输入从当前帧平滑追踪，不要瞬间跳到目标。
- 输入停止时可以保持当前位置、缓慢回到静止帧，或执行单独的待机片段；由 Motion
  Brief 决定。

## 指针、滚动和布局

- `pointermove` 记录最近屏幕坐标。
- `scroll`、`resize` 和容器尺寸变化后，用相同屏幕坐标重新计算相对主体的位置。
- 主体锚点来自当前 `getBoundingClientRect()`，不要永久缓存。
- 主体不在视口时暂停循环和昂贵计算。
- 使用 `IntersectionObserver` 控制活动状态，`ResizeObserver` 更新布局。

## 手机陀螺仪

1. 由用户手势请求权限。
2. 记录首次 `beta/gamma` 作为中性姿态。
3. 根据屏幕方向旋转输入轴。
4. 限制异常值并轻微平滑。
5. 不默认设置大死区；传感器噪声用阻尼和小阈值处理。
6. 权限拒绝时使用触摸或静态帧。

## 预加载与 seek 策略

- 图集路线使用 `<link rel="preload" as="image">`，预加载清单、静态首帧和图集，并用
  `Image.decode()` 确认可绘制。
- 视频路线预加载静态降级首帧、视频元数据和首段媒体；`loadedmetadata` 后才能计算帧
  时长并允许 seek。
- 每次只提交最新整数目标帧，丢弃过时 seek；视频离屏时停止 seek 和绘制，重新进入
  视口后跳到最新目标帧。
- 加载完成前显示静态首帧或简洁加载层，不显示多个叠加帧。
- 资源失败时解除页面锁定并回退静态降级图（chroma 为静态 Alpha 图，baked 为
  `poster.png`），不能露出绿幕或半成品画面。
- 不让次要动画阻塞整个页面。

## 性能

- 事件监听器使用 `passive: true`，只更新内存中的目标。
- 每个 `requestAnimationFrame` 最多写一次 DOM，整数帧未改变时不更新样式。
- 元素离屏且参数稳定时停止 `requestAnimationFrame`。
- 避免为“流畅”同时渲染两张大透明图。
- 测试冷缓存、弱网、低端手机、页面滚动和快速反向输入。
