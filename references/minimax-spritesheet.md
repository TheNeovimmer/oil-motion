# MiniMax 视频转交互雪碧图

仅当 Concept Contract 锁定 `background_owner: page`（主体确有透明复用需求），且
`motion_budget.py` 返回 `delivery.selected=alpha-atlas` 时执行本流程。本文档只覆盖
图集路线专属的清理、检测与打包命令；公共步骤各自有唯一事实源：

- 预算与路线选择：[delivery-selection.md](delivery-selection.md)
- 首尾帧模式、提示词与提交命令：[prompting.md](prompting.md)
- 帧策略与图集压缩：[optimization.md](optimization.md)
- 母版验收、抠图验收、Pilot 与帧链硬门：[qa.md](qa.md)
- 运行时映射与验收矩阵：[runtime.md](runtime.md)、[qa.md](qa.md)

`delivery.selected` 不是 `alpha-atlas` 时停止阅读本流程，按结果改走
[chroma-video.md](chroma-video.md) 或 [baked-video.md](baked-video.md)。

## 交付物

```text
motion-name/
├── source/
│   ├── first-frame.png
│   ├── last-frame.png            # 单向转场需要
│   ├── prompt.txt
│   ├── master.mp4
│   └── master.job.json
├── frames/
│   ├── raw/
│   └── final/
├── qa/
│   ├── raw-analysis.json
│   ├── raw-contact.jpg
│   ├── final-analysis.json
│   └── final-contact.jpg
└── final/
    ├── motion.webp
    ├── motion.json
    └── implementation.*
```

## 1. 公共生产步骤

按 SKILL.md 主流程依次执行：预算（[delivery-selection.md](delivery-selection.md)）→
关键帧与提示词（[prompting.md](prompting.md)）→ Pilot 硬门（[qa.md](qa.md)）→ 提交
与母版验收（[prompting.md](prompting.md)、[qa.md](qa.md)）→ 帧准备
（[optimization.md](optimization.md)，需要色键输入时在该阶段离线生成 Alpha 帧）。
任一环节失败即停止，不要进入下面的打包步骤。

## 2. 闭环清理与可选稳定

闭环动画：

```bash
python3 "$OIL_MOTION/scripts/loop_cleanup.py" \
  "$PREPARED_FRAMES" frames/clean \
  --seam-window "$SEAM_WINDOW" \
  --duplicate-threshold "$DUPLICATE_THRESHOLD" \
  --report qa/loop-cleanup.json
```

该工具只做确定性选帧，不生成角色动作，也不对相邻帧做透明叠加。接缝选错时扩大或缩小
`--seam-window`，不要为了减少帧数盲目提高重复阈值。首尾不同的单向转场传入
`--end-reference last-frame.png`，裁掉模型在尾帧上的多余停顿。

固定主体存在轻微漂移时才稳定：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" normalize \
  frames/clean frames/final \
  --anchor bottom \
  --max-scale-change 0.08
```

不需要闭环清理或稳定时，将合格的帧准备结果作为 `frames/final`。自由运动、镜头运动和真实透视变化禁止稳定。

## 3. 最终门槛与图集打包

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" analyze frames/final \
  --output qa/final-analysis.json

python3 "$OIL_MOTION/scripts/motion_pipeline.py" contact frames/final \
  --output qa/final-contact.jpg \
  --columns 8

python3 "$OIL_MOTION/scripts/motion_pipeline.py" atlas frames/final \
  --output final/motion.webp \
  --manifest final/motion.json \
  --cell-width 360 \
  --cell-height 360 \
  --quality 88
```

打包前按 [delivery-selection.md](delivery-selection.md) 重新运行预算检查（传入最终
帧数、单元格尺寸和显示约束）。只有预算仍返回 `alpha-atlas` 且通过时才打包；若自动
选择变成 `chroma-video`，停止图集打包并执行视频路线。需要压到目标体积时按
[optimization.md](optimization.md) 执行，不要手动反复猜 WebP 质量。

## 4. 网页实现与验收

从 `assets/interactive-motion.ts` 复制运行时，映射、阻尼、预加载和降级按
[runtime.md](runtime.md) 执行；验收矩阵和故障定位按 [qa.md](qa.md) 执行。任何闪帧
先按“母版 → 帧 → 图集 → 映射 → 解码”的顺序定位。
