# 烘焙场景视频交互路线

仅当 Concept Contract 锁定 `background_owner: video` 且 `motion_budget.py` 返回
`delivery.selected=baked-video` 时读取本流程。它是默认的场景路线：镜头运动、环境光、
地面接触、景深、背景连续性重要，或主体不需要脱离背景复用时使用。

视频本身就是最终画面：背景与主体在同一视频中烘焙生成，不做任何抠色，不使用 WebGL
色键着色器，页面只提供容器。换背景意味着重新生成视频，不要试图从烘焙视频里抠主体。

## 编译

先按 [delivery-selection.md](delivery-selection.md) 运行预算并保存
`--background-owner video` 的报告，再编译已通过内容验收的场景母版：

```bash
python3 "$OIL_MOTION/scripts/compile_scroll_video.py" \
  source/master.mp4 build/baked-video \
  --background-owner video \
  --budget-report build/motion-budget.json \
  --fps 48 \
  --desktop-width 1920 \
  --mobile-width 1280
```

脚本会：

1. 强制插帧到 48 FPS，保留完整场景画面。
2. 输出原始与插帧接触表和插帧报告。
3. 按需清理闭环接缝或尾部停顿。
4. 编码桌面端和移动端全关键帧 MP4，移除音轨。
5. 生成静态降级图 `poster.png`（普通首帧，不带 Alpha）和 `compile.json`。

成功后默认删除可重新生成的中间 PNG。只有定位插帧或编码问题时才传 `--keep-frames`。

## 多段场景连续

多段叙事按 [qa.md](qa.md) 的“连续帧链”执行实际尾帧接力、SHA-256 校验和误差累积
处理。此外，场景设定（地点、时间、光向、地面材质、景深）写进 Concept Contract 的
`scene` 锚点，每段提示词原样复用（见 [prompting.md](prompting.md) 的场景背景段）。

## 网页接入

- `assets/interactive-motion.ts`：把滚动、拖拽等输入映射为整数目标帧，并处理阻尼
  与限速（用法见 [runtime.md](runtime.md)）。
- 渲染侧把整数帧换算成 `video.currentTime`，等待 seek 完成后直接把视频绘制到
  Canvas 或让视频元素本身显示。没有色键、没有 Alpha、没有背景合成层。

```html
<section class="motion-stage">
  <video class="motion-video" muted playsinline preload="auto"></video>
</section>
```

```css
.motion-stage { overflow: hidden; }
.motion-video { width: 100%; height: 100%; object-fit: cover; display: block; }
```

视频就是完整画面，不需要页面背景兜底；容器之外的页面背景与视频无关。

## 加载和降级

共享的预加载、seek 和离屏策略按 [runtime.md](runtime.md) 执行。baked 路线专属：

- 预加载静态降级图 `poster.png`，视频解码或资源加载失败时显示它。
- `prefers-reduced-motion` 直接显示最能表达内容的静态帧。

## 验收

- 完整观看桌面与移动输出：场景、环境光、地面接触、景深和背景连续性在全序列一致。
- 多段拼接处没有背景跳变、光线突变或身份漂移。
- `compile.json` 中桌面与移动输出的 `allFramesAreKeyframes` 必须为 `true`。
- 记录常规 seek 和快速反向 seek 延迟；若目标设备明显掉帧，先降低输出分辨率到实际
  CSS 尺寸乘 DPR，不能降低语义帧密度来掩盖问题。
- 确认运行时不存在任何抠色、色键着色器或阈值调参；出现绿边或内部绿块说明素材混入
  了 chroma 母版，回到 Concept Contract 检查背景归属。
