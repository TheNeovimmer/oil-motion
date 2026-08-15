# 绿幕视频交互路线

仅当 `motion_budget.py` 返回 `delivery.selected=chroma-video` 时读取本流程。它主要适合一维顺序访问、长时间轴或大尺寸交互，也可作为一维随机访问资源超出图集预算时的降级主方案。

视频仍然是绿幕素材。页面通过 WebGL 实时生成 Alpha，最终背景属于页面，换背景不需要重新生成主体。

## 编译

先保存自动选择报告，再编译已通过内容验收的均匀绿幕母版：

```bash
python3 scripts/motion_budget.py \
  --frames 551 --display 1536x864 --dpr 1 \
  --driver scroll --parameter-space linear \
  --report build/motion-budget.json --strict

python3 scripts/compile_scroll_video.py \
  source/master.mp4 build/chroma-video \
  --budget-report build/motion-budget.json \
  --fps 48 \
  --desktop-width 1920 \
  --mobile-width 1280 \
  --anchor center=240 \
  --poster-source-frame 240
```

`--anchor` 和 `--poster-source-frame` 使用清理前插帧序列的零基索引。编译器会根据
`keptSourceIndices` 映射到最终序列，避免去重或裁尾后中心状态漂移。

脚本会：

1. 强制插帧到 48 FPS，保留绿幕，不在媒体中写入页面背景。
2. 输出原始与插帧接触表和插帧报告。
3. 按需清理闭环接缝或尾部停顿。
4. 从整段代表帧检查源色键颜色与边缘均匀度。
5. 编码桌面端和移动端全关键帧 MP4，移除音轨，并把全关键帧检查作为硬门槛。
6. 从最终 MP4 各抽取最多 48 个代表帧，用与 WebGL 完全相同的 `dominance-v2` 参数重新抠色；检查绿色/洋红残留、半透明大块和边缘去溢色。
7. 生成编码后 Alpha 接触表、白/黑/高饱和背景矩阵、静态 Alpha 降级图和 `compile.json`。任一自动门槛失败时保留诊断帧并停止交付。

成功后默认删除可重新生成的中间 PNG，保留绿幕母版、接触表、分析报告、静态 Alpha 图和最终视频。只有定位插帧或编码问题时才传 `--keep-frames`。

全关键帧会增加文件体积，但让 `currentTime` 的正向、反向和跳转延迟更稳定。不得改回自动播放或用连续播放速度模拟滚动。

## 网页接入

组合两个共享运行时：

- `assets/interactive-motion.ts`：把滚动、拖拽等输入映射为整数目标帧，并处理阻尼与限速。
- `assets/chroma-video-renderer.ts`：把整数帧换算成 `video.currentTime`，等待 seek 完成后由 WebGL 色键着色器绘制到透明 Canvas。

页面必须读取 `compile.json.runtime`，把其中的 `frameCount`、`fps`、`anchors` 和
`keying` 原样交给运行时。不要在业务代码中复制色键颜色、阈值或中心帧：

```ts
const runtime = manifest.runtime;
const renderer = createChromaVideoRenderer({
  video,
  canvas,
  frameCount: runtime.frameCount,
  fps: runtime.fps,
  keying: runtime.keying,
});
```

页面结构保持简单：

```html
<section class="motion-stage">
  <video class="motion-source" muted playsinline preload="auto"></video>
  <canvas class="motion-canvas"></canvas>
</section>
```

```css
.motion-stage { background: var(--page-background); }
.motion-source { display: none; }
.motion-canvas { width: 100%; height: 100%; display: block; }
```

不要给视频元素设置最终背景，也不要把绿幕视频直接显示给用户。

## 加载和降级

- 预加载视频元数据、首段媒体和静态 Alpha 首帧。
- `loadedmetadata` 后才能计算帧时长；每次只提交最新整数目标帧，丢弃过时 seek。
- WebGL、视频解码或资源加载失败时显示静态 Alpha 首帧，页面不能露出绿幕。
- `prefers-reduced-motion` 直接显示最能表达内容的静态 Alpha 状态。
- 视频离屏时停止 seek 和绘制，重新进入视口后跳到最新目标帧。

## 验收

- `qa/post-encode-keying.json` 的总结果、桌面端和移动端结果都必须为 `passed: true`。
- 查看 `desktop/mobile-alpha-contact.jpg` 与 `desktop/mobile-background-matrix.jpg`；自动报告不能替代视觉检查。
- 在白、黑和高饱和背景上检查边缘，确认没有绿边、洋红边和主体内部误删。
- 检查慢速滚动、快速滚动、连续反向、首帧、尾帧和跨章节跳转。
- `compile.json` 中桌面与移动输出的 `allFramesAreKeyframes` 必须为 `true`。
- 记录常规 seek 和快速反向 seek 延迟；若目标设备明显掉帧，先降低输出分辨率到实际 CSS 尺寸乘 DPR，不能降低语义帧密度来掩盖问题。
- 页面换背景只改 CSS 后仍应正确显示；若必须重新生成主体，说明交付管线不合格。
