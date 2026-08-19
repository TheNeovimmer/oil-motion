# 绿幕视频交互路线

仅当 Concept Contract 锁定 `background_owner: page`（主体确有透明复用需求），且
`motion_budget.py` 返回 `delivery.selected=chroma-video` 时读取本流程。它主要适合
一维顺序访问、长时间轴或大尺寸交互，也可作为一维随机访问资源超出图集预算时的降级
主方案。场景叙事、镜头运动、环境光、地面接触、景深或背景连续性重要的需求不属于本
路线，应回到 Concept Contract 改走 [baked-video.md](baked-video.md)。

视频仍然是绿幕素材。页面通过 WebGL 实时生成 Alpha，最终背景属于页面，换背景不需要
重新生成主体。

## 编译

先按 [delivery-selection.md](delivery-selection.md) 运行预算并保存
`--background-owner page` 的报告，再编译已通过内容验收的均匀绿幕母版：

```bash
python3 "$OIL_MOTION/scripts/compile_scroll_video.py" \
  source/master.mp4 build/chroma-video \
  --background-owner page \
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
6. 从最终 MP4 各抽取最多 48 个代表帧，逐帧模拟运行时抠色；使用与 WebGL 完全
   相同的 `dominance-v2` 参数检查绿色/洋红残留、半透明大块和边缘去溢色。
7. 生成编码后 Alpha 接触表、白/黑/高饱和背景矩阵、静态 Alpha 降级图和 `compile.json`。任一自动门槛失败时保留诊断帧并停止交付。

成功后默认删除可重新生成的中间 PNG，保留绿幕母版、接触表、分析报告、多底色验收图、
静态 Alpha 图和最终视频。只有定位插帧或编码问题时才传 `--keep-frames`。

## 抠色硬门（拒收优先）

chroma 路线的质量必须在母版和构建期解决，不允许推给运行时：

1. 编译时逐帧模拟 WebGL 后仍有可见色键残留，或人工在多底色验收图上发现绿边、
   洋红边、主体内部误删、半透明残留或运动模糊脏边时，**拒收母版重新生成**，或改用
   带 Alpha 的离线 matte（构建期离线抠色后按 `alpha-atlas` 路线交付）。
2. 禁止靠调大 WebGL 抠色阈值、扩腐蚀范围或模糊边缘来掩盖母版缺陷。阈值只能复现
   已验收母版的已知色键，不能把坏素材“调”成好素材。
3. 背景不均匀时，重新生成母版通常比扩大抠色阈值更安全。
4. 半透明、发丝和运动模糊本来就是 chroma 路线的高风险区；Concept Contract 阶段
   发现主体大量依赖这些效果时，应重新评估背景归属，考虑改走 baked-video。

## 网页接入

组合两个共享运行时：

- `assets/interactive-motion.ts`：把滚动、拖拽等输入映射为整数目标帧，并处理阻尼与限速（用法见 [runtime.md](runtime.md)）。
- `assets/chroma-video-renderer.ts`：把整数帧换算成 `video.currentTime`，等待 seek 完成后由 WebGL 色键着色器绘制到透明 Canvas。
- 初始化 renderer 时必须从 `compile.json.runtime.keying` 传入全部抠色参数。编译 QA
  与运行时参数不一致即拒收，禁止使用 renderer 默认值猜测。

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

共享的预加载、seek 和离屏策略按 [runtime.md](runtime.md) 执行。chroma 路线专属：

- 预加载静态 Alpha 首帧；WebGL、视频解码或资源加载失败时显示它，页面不能露出绿幕。
- `prefers-reduced-motion` 直接显示最能表达内容的静态 Alpha 状态。

## 验收

- `qa/post-encode-keying.json` 的总结果、桌面端和移动端结果都必须为 `passed: true`。
- 查看 `desktop/mobile-alpha-contact.jpg` 与 `desktop/mobile-background-matrix.jpg`；自动报告不能替代视觉检查。
- 在白、黑和高饱和测试底色上检查边缘，确认没有绿边、洋红边和主体内部误删；
  再在实际页面背景上复核一次。
- 检查慢速滚动、快速滚动、连续反向、首帧、尾帧和跨章节跳转。
- `compile.json` 中桌面与移动输出的 `allFramesAreKeyframes` 必须为 `true`，
  `compile.postEncodeKeyingPassed` 必须为 `true`；桌面端与移动端报告的 `checkedFrames`
  都必须等于 `compile.alphaQaFrameCount`。
- 记录常规 seek 和快速反向 seek 延迟；若目标设备明显掉帧，先降低输出分辨率到实际
  CSS 尺寸乘 DPR，不能降低语义帧密度来掩盖问题。
- 页面换背景只改 CSS 后仍应正确显示；若必须重新生成主体，说明交付管线不合格。
