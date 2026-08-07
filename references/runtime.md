# 运行时选择与交互映射

## 先看访问模式

| 需求 | 推荐格式 | 原因 |
|---|---|---|
| 透明背景、少于约 300 帧、任意跳转 | WebP 图集 | 一次请求，随机访问稳定 |
| 图集超过 4096×4096 或设备纹理限制 | 分片图集 | 控制内存和纹理尺寸 |
| 很长的顺序滚动时间轴 | 视频 + 解码控制 | 压缩率远高于独立帧 |
| 高分辨率一维滚动且频繁 seek | 全关键帧 MP4 | 一个请求、定位稳定、解码内存低于巨型图集 |
| 高频随机定位且浏览器目标明确 | WebCodecs | 更精确地访问解码帧 |
| 少量 hover/点击状态 | 多段短资源 | 状态边界清楚 |

图集文件体积小不代表解码内存小。RGBA 解码内存约为 `宽 × 高 × 4`。3840×3600 图集约需 52.7 MiB，因此应在真实移动设备上测试。

全关键帧 MP4 比普通视频大，但每帧都能直接解码，适合滚动时反复设置
`currentTime`。它仍然不是随机二维参数的替代品；二维方向继续使用图集或 WebCodecs。

## 图集约束

- 单元格尺寸统一。
- 所有帧使用同一主体锚点。
- 单元格宽高至少为最终 CSS 宽高乘以目标 DPR；禁止依赖浏览器把低分辨率单帧放大。
- 图集宽高尽量不超过 4096；需要更大时分片。
- 使用清单保存帧数、列数、行数、单元格尺寸、静止帧和参数映射。
- CSS `background-size` 为 `columns × 100%` 和 `rows × 100%`。
- 切换帧只更新 `background-position`，不要创建多个透明图片层。

先运行资源预算检查：

```bash
python3 scripts/motion_budget.py \
  --frames 180 --display 240x240 --dpr 2 --max-texture 4096
```

如果单帧像素满足要求后图集超出纹理上限，优先分片或改用视频解码，不要缩小单元格强行装入单张图集。

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

## 一维时间参数

```text
progress = clamp((scrollY - start) / (end - start), 0, 1)
targetFrame = progress * (frameCount - 1)
```

滚动监听只记录目标值，在 `requestAnimationFrame` 中更新。页面布局变化时重新计算起止位置。

使用全关键帧视频时：

```text
targetFrame = round(progress * (frameCount - 1))
targetTime = targetFrame / fps
```

只有整数目标帧改变时才写 `video.currentTime`。桌面与移动端分别提供按实际展示尺寸和
DPR 编译的版本，避免移动端下载过大的桌面资源。使用
`scripts/compile_scroll_video.py` 生成两个版本，并显式移除音轨。

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

## 预加载

- 首屏图集使用 `<link rel="preload" as="image">` 或框架等价能力。
- 首屏滚动视频使用 `<link rel="preload" as="video">` 或
  `video.preload = "auto"`；同时保留首帧 poster。
- 用 `Image.decode()` 确认资源可绘制。
- 加载完成前显示静态首帧或简洁加载层，不显示多个叠加帧。
- 资源失败时解除页面锁定并回退静态图。
- 不让次要动画阻塞整个页面。

## 性能

- 事件监听器使用 `passive: true`，只更新内存中的目标。
- 每帧最多一次 DOM 写入。
- 整数帧未改变时不更新样式。
- 元素离屏且参数稳定时停止 `requestAnimationFrame`。
- 避免为“流畅”同时渲染两张大透明图。
- 测试冷缓存、弱网、低端手机、页面滚动和快速反向输入。
