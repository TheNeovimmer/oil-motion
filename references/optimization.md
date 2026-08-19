# 强制插帧与图集压缩

AI 动作母版通过内容验收后，必须先插帧，再继续清理、稳定与打包。默认目标为 48 FPS。保留原始色键母版，所有输出写入新目录。

## 插帧门槛

```bash
python3 "$OIL_MOTION/scripts/optimize_motion.py" interpolate \
  source/master.mp4 build/interpolated \
  --fps 48 \
  --key auto
```

输出包含：

- `frames/`：插帧并抠色后的 Alpha 帧。
- `qa/contact-sheet-original.jpg`：原始帧接触表。
- `qa/contact-sheet-interpolated.jpg`：插帧接触表。
- `qa/analysis-interpolated.json`：插帧序列分析。
- `interpolation-report.json`：插帧前后自动对比。

必须同时人工检查两张接触表。出现重影、双轮廓、边缘撕裂、部件穿插、结构扭曲或新增闪帧时停止处理；不得跳过插帧直接交付原始帧。

## 图集压缩

需要控制透明图集体积时继续使用 `scripts/optimize_motion.py`。保留插帧后的 Alpha 母版，压缩结果输出到新文件。

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
按 [delivery-selection.md](delivery-selection.md) 重新预算并遵循其超预算处理，
不要继续缩小单帧。

## 选择原则

- 插帧是生成动作母版后的强制步骤，默认目标为 48 FPS。
- 自动对比通过后仍必须人工查看原始与插帧接触表。
- 先满足参数采样密度，再讨论浏览器刷新率和阻尼。
- 未确认最大实际 CSS 展示尺寸和目标 DPR 时，不执行最终压缩。
- 先满足目标 DPR 下的单帧清晰度，再压质量；不得为了目标体积缩到清晰度下限以下。
- 体积目标必须结合冷缓存、设备内存和纹理上限，不只看网络下载大小。
