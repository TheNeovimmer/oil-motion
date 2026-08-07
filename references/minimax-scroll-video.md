# MiniMax 滚动视频

适用于高分辨率、不透明、一维顺序变化，例如完整产品随滚动拆成爆炸图。流程仍是
“先生图验收首尾帧 → MiniMax H3 补全动作 → 程序编译”，只是最终资产选择全关键帧
MP4，而不是巨型雪碧图。

## 什么时候使用

- 动画由滚动或拖拽控制，参数是一维时间轴。
- 最大展示尺寸较大，按 DPR 计算后单帧接近 1280–1920 像素宽。
- 图集预算需要很多 4096 纹理切片，或解码内存明显过高。
- 不需要透明背景。

需要透明、环形方向或真正任意跳帧时，继续使用图集或 WebCodecs。

## MiniMax 固定规则

1. 默认模型是 `minimax/minimax-h3`。
2. 精确转场使用已验收的 `first_frame + last_frame`。
3. `reference_image` 与首尾帧模式互斥；身份和风格必须已经体现在关键帧里。
4. 默认用 `duration=5` 验证单段动作；使用 `frames` 时不能再传 `duration`。
5. 先用 `768p` 验证动作语义，最终大尺寸展示使用 `2K` 重新生成。
6. 返回视频可能比请求略长、包含尾帧停顿，并且即使关闭音频仍可能带音轨。

## 一键编译

```bash
OIL_MOTION="$HOME/.codex/skills/oil-motion"

python3 "$OIL_MOTION/scripts/compile_scroll_video.py" \
  source/master.mp4 build/scroll \
  --end-reference source/last-frame.png \
  --desktop-width 1920 \
  --mobile-width 1280
```

`desktop-width` 与 `mobile-width` 应取对应设备“最大实际 CSS 展示宽度 × 目标 DPR”。
脚本保持源画幅；默认不会上采样，目标宽度超过母版时自动限制为母版宽度。

脚本会：

1. 探测真实分辨率、帧率、帧数、时长和音轨。
2. 以 24 FPS 切出无色键 PNG 母版帧。
3. 按目标尾帧裁掉末尾停顿，并删除视觉近重复帧。
4. 输出分析报告和编号接触表。
5. 编译桌面与移动端 H.264 全关键帧 MP4。
6. 强制 `-an` 移除音轨，写入 `compile.json`。

闭环动画把 `--end-reference` 换成 `--loop`。没有这两个参数时脚本保留全部帧，适合
已经手工剪好的母版。

## 为什么使用全关键帧 MP4

普通长 GOP 视频更小，但频繁设置 `currentTime` 时浏览器需要从前一个关键帧解码，
容易迟滞。全关键帧 MP4 文件略大，却能让滚动 seek 更稳定；同时只需一个网络请求，
解码内存也远低于十几张高分辨率图集。

默认输出：

```text
build/scroll/
├── frames/raw/
├── frames/final/
├── qa/analysis.json
├── qa/contact-sheet.jpg
├── final/motion-scrub-desktop.mp4
├── final/motion-scrub-mobile.mp4
└── compile.json
```

## 网页映射

- 用滚动进度计算整数目标帧：`round(progress × (frameCount - 1))`。
- 目标时间为 `frame / fps`，只在整数帧变化时更新 `video.currentTime`。
- 输入端可使用短 `smoothDamp`，但不能透明叠加两帧。
- 首帧作为 poster；视频 `loadeddata` 后再移除加载层。
- `prefers-reduced-motion` 下固定展示首帧或尾帧。
