# 补帧与压缩

需要提高帧率、控制网页资源体积或比较补帧质量时，使用
`scripts/optimize_motion.py`。保留原始母版，输出到新的目录或文件。

## 先检查参数采样密度

帧数不是视频 FPS 的同义词，而是交互参数上可访问的独立姿态数量。先按驱动范围计算，
再决定单帧尺寸和图集布局。

- 滚动序列默认以每个视口高度 20–28 帧估算，24 帧/屏作为基线；4 屏时间轴通常需要约 96 帧。
- 拖拽或横向指针的短距离检查通常从 48–72 帧开始；环形方向通常从 72–120 帧开始。
- 阻尼、限速和高刷新率不会生成新的姿态。采样不足时仍会看到阶梯。
- 单张纹理受限时，在满足实际展示尺寸与目标 DPR 的前提下，重新平衡“单帧像素”和“姿态数量”；不能同时满足就改用分片图集或视频解码。

滚动预算示例：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 96 \
  --display 300x300 \
  --dpr 1.25 \
  --cell 384x384 \
  --scroll-pages 4 \
  --frames-per-page 24 \
  --max-texture 4096 \
  --strict
```

从合格母版增加采样时，优先重新按更高 FPS 抽取原视频；只有源帧本身不足时才做光流
补帧。接触表后半段出现连续近重复警告时，先判断是细微有效动作还是无效停顿；无效
停顿应裁掉或重定时，不要用更多重复帧制造“高帧数”。

## 补帧并比较

```bash
OIL_MOTION="$HOME/.codex/skills/oil-motion"

python3 "$OIL_MOTION/scripts/optimize_motion.py" interpolate source.mp4 build/interpolated \
  --fps 48 \
  --key auto
```

输出包含：

- `frames/`：补帧后的有序序列。
- `qa/contact-sheet-original.jpg`：源帧接触表。
- `qa/contact-sheet-interpolated.jpg`：补帧接触表。
- `qa/analysis-interpolated.json`：逐帧异常。
- `interpolation-report.json`：补帧前后异常率和自动结论。

自动检查不能识别所有重影、肢体扭曲和语义错误。必须同时查看两张接触表；动作本身
不连续时不要靠增加帧率掩盖。

## 图集目标体积

```bash
python3 "$OIL_MOTION/scripts/optimize_motion.py" atlas frames/final \
  --output final/motion.webp \
  --target-mb 2 \
  --display 320x320 \
  --dpr 2 \
  --cell-width 768 \
  --cell-height 768 \
  --columns 16
```

工具先用“最大 CSS 展示尺寸 × DPR”计算最低单帧像素，再保持单帧尺寸并搜索最高
WebP 质量；无法达标时只能缩小到这个清晰度下限。输出同名 manifest 和
`.optimize.json` 报告。`clarityMet` 必须为 `true`；若 `targetMet` 为 `false`，
保留清晰版本并改用分片图集、视频或降低帧数，不要继续缩小。

## 视频目标体积

```bash
python3 "$OIL_MOTION/scripts/optimize_motion.py" video source.mp4 \
  --output final/motion.mp4 \
  --target-mb 3 \
  --display 640x360 \
  --dpr 2 \
  --fps 24
```

MP4 使用 H.264 两遍编码，WebM 使用 VP9 两遍编码。交互动画默认移除音频；确实需要
声音时传 `--keep-audio`。工具最多自动校正三次码率，并输出原始/结果探测信息、压缩
率和是否达到目标体积。视频默认按展示尺寸和 DPR 设置输出分辨率，并通过
`--min-bpp` 保留最低每像素码率；目标体积过小时宁可让 `targetMet` 为 `false`，也
不会突破清晰度底线。

## 选择原则

- 只在源动作连续、原帧率不足时补帧。
- 先满足参数采样密度，再讨论浏览器刷新率和阻尼。
- 需要任意跳帧时优先图集；主要顺序播放时优先压缩视频。
- 未确认最大实际 CSS 展示尺寸和目标 DPR 时，不执行最终压缩。
- 先满足目标 DPR 下的单帧清晰度，再压质量；不得为了目标体积缩到清晰度下限以下。
- 体积目标必须结合冷缓存、设备内存和纹理上限，不只看网络下载大小。
