# MiniMax 视频转交互雪碧图

本流程用于把参考图片通过 ZenMux 的 MiniMax 视频接口生成连续动作母版，再编译成可随机访问的透明帧、WebP 图集和网页交互。不要把生成视频直接当最终网页资产。

## 输入与交付

开始前必须具备：

- 一张已经在目标页面验证过尺寸和构图的首帧。
- 明确的 `driver`、`parameter_space`、动作方向、静止状态和是否闭环。
- 最终 CSS 显示尺寸、目标 DPR、帧数或时长预算。
- 需要锁定身份时，先把身份信息生成进首尾关键帧；首尾帧模式不能再附加参考图。

完成后必须交付：

```text
motion-name/
├── source/
│   ├── first-frame.png
│   ├── last-frame.png            # 单向转场需要
│   ├── identity.png              # 生图阶段或仅参考模式使用
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

## 参数选择

| 目标 | 首帧 | 尾帧 | 参考图 | 建议 |
|---|---|---|---|---|
| 无缝闭环 | 必须 | 与首帧相同，用 `--loop-frame` | 禁止 | 只生成一圈，不停顿、不折返 |
| 单向转场 | 必须 | 必须且不同 | 禁止 | 到达尾帧后不返回 |
| 方向跟随 | 必须 | 闭环时同首帧 | 禁止 | 生成完整方向环，运行时映射角度 |
| 滚动叙事 | 必须 | 建议提供 | 禁止 | 每一帧都应是可停留状态 |
| 仅参考生成 | 禁止 | 禁止 | 可传一张或多张 | 不锁定精确首尾状态 |
| 已有合格视频 | 不需要 | 不需要 | 不需要 | 跳过生成，从探测与切帧开始 |

默认模型使用 `minimax/minimax-h3`，分辨率先用 `768p` 验证动作，最终清晰度不足再使用 `2K`。单变量动作默认 3–6 秒。

- 默认不写 `--model`，脚本固定使用 `minimax/minimax-h3`。
- 不写 `--ratio` 时，脚本会按首帧或第一张参考图推断最接近的常用画幅；没有图片时
  默认 `1:1`。需要特殊画幅时显式传入。
- `reference_image` 与 `first_frame` / `last_frame` / `loop_frame` 互斥。混用会触发
  MiniMax 接口错误 `2013`，`video_job.py` 会在联网前阻止提交。
- 首尾帧转场需要身份一致时，必须在生图阶段让两张关键帧共享同一参考与构图；视频
  请求中不再重复附加 `reference_image`。
- 默认传 5 秒 `duration`。不要为了追求帧数同时传 `--frames`；只传 `--frames`
  时脚本不会再发送 `duration`。
- 只有当前接口明确支持帧数控制时才使用 `--frames`；若接口拒绝参数，必须保存错误并报告，不得静默删除首帧、尾帧或参考图。
- `seed` 只在模型支持时用于复现；它不能替代参考图和首尾帧。
- 一条视频只承担一个连续参数。二维输入使用二维采样或多片段，不要硬塞进单条往返视频。

## 标准执行流程

先设置 Skill 路径和密钥。密钥只放环境变量，不写入文件、命令历史示例或任务元数据：

```bash
OIL_MOTION="$HOME/.codex/skills/oil-motion"
export ZENMUX_API_KEY="..."
```

### 1. 预算门槛

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 120 \
  --display 180x180 \
  --dpr 2 \
  --max-texture 4096 \
  --access random \
  --strict
```

停止条件：

- 最低单帧像素高于计划的图集单元格。
- 单张图集超过纹理上限且没有改为分片图集、序列帧或视频解码。
- 静态首帧放到目标页面后存在裁切、模糊、比例或锚点问题。

### 2. 编写并验收提示词

读取 [prompting.md](prompting.md)，按顺序组合：

1. 身份与风格锁定。
2. 固定镜头和固定锚点。
3. 唯一动作变量、方向、起点和终点。
4. 绿幕要求。
5. 针对当前失败风险的负面约束。

提示词不要要求模型输出透明通道、帧编号、图集或精确压缩；这些由程序完成。

### 3. 提交 MiniMax

闭环：

```bash
python3 "$OIL_MOTION/scripts/video_job.py" \
  --prompt-file source/prompt.txt \
  --first-frame source/first-frame.png \
  --loop-frame \
  --resolution 768p \
  --ratio 1:1 \
  --duration 5 \
  --seed 42 \
  --output source/master.mp4 \
  --metadata source/master.job.json
```

单向转场：

```bash
python3 "$OIL_MOTION/scripts/video_job.py" \
  --prompt-file source/prompt.txt \
  --first-frame source/first-frame.png \
  --last-frame source/last-frame.png \
  --resolution 768p \
  --ratio 1:1 \
  --duration 5 \
  --output source/master.mp4 \
  --metadata source/master.job.json
```

模型或接口拒绝参数时停止并报告具体响应。只有用户同意降级后，才能移除约束或更换模型。

接口即使收到 `generate_audio=false`，返回文件仍可能包含 AAC 音轨；交互资产打包必须
显式使用 `-an`。请求 5 秒也可能得到略长的成片和尾部停顿，因此必须读取实际探测
结果，不能用请求参数代替真实帧数。

### 4. 母版门槛

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" probe source/master.mp4
```

完整观看视频，不能只看首尾帧。出现以下问题时重新生成，不进入媒体处理：

- 身份、结构、Logo、肢体或道具发生语义错误。
- 动作方向错误、中途折返、停顿、硬切或最后一刻跳回首帧。
- 镜头、透视、主体比例、光线或色键背景明显漂移。
- 主体碰到画面边缘，无法安全抠图。

程序只能修复轻微位置、尺寸、颜色和重复帧问题，不能修复错误的动作语义。

### 5. 抠图、切帧与原始检查

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" extract \
  source/master.mp4 frames/raw \
  --fps 24 \
  --key auto

python3 "$OIL_MOTION/scripts/motion_pipeline.py" analyze frames/raw \
  --output qa/raw-analysis.json

python3 "$OIL_MOTION/scripts/motion_pipeline.py" contact frames/raw \
  --output qa/raw-contact.jpg \
  --columns 8
```

检查 `raw-contact.jpg` 和分析报告：

- 四角透明，主体内部没有误删，边缘没有明显绿边或洋红边。
- 帧顺序与动作方向一致。
- 没有空帧、亮度闪帧、大小突变、中心突变或异常重复段。

背景不均匀或主体被严重误删时重新生成母版，不要无限扩大抠色阈值。

### 6. 闭环清理与可选稳定

闭环动画：

```bash
python3 "$OIL_MOTION/scripts/loop_cleanup.py" \
  frames/raw frames/clean \
  --seam-window 24 \
  --duplicate-threshold 0.003 \
  --report qa/loop-cleanup.json
```

固定主体存在轻微漂移时才稳定：

```bash
python3 "$OIL_MOTION/scripts/motion_pipeline.py" normalize \
  frames/clean frames/final \
  --anchor bottom \
  --max-scale-change 0.08
```

不需要闭环清理或稳定时，将合格帧复制到 `frames/final`。自由运动、镜头运动和真实透视变化禁止稳定。

### 7. 最终门槛与图集

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

打包前再次运行预算检查：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 120 \
  --display 180x180 \
  --dpr 2 \
  --cell 360x360 \
  --max-texture 4096 \
  --access random \
  --strict
```

预算要求分片时不得通过缩小单帧强塞进一张图集。
以上数字只是一个能放入 4096 纹理的完整示例；实际项目必须使用 Motion Brief
中的显示尺寸、DPR 和最终帧数重新计算。若结果推荐分片图集，而当前运行时尚未支持
分片清单，就停止打包并改用序列帧或视频解码，不得假装单图集已经交付。

### 8. 网页实现与验收

从 `assets/interactive-motion.ts` 复制运行时：

- 先解码静止帧和关键图集，再显示交互层。
- 输入只更新目标参数；每个 `requestAnimationFrame` 最多写一次整数帧。
- 环形动作使用最短环形距离。
- 使用带速度状态和最大速度的 `smoothDamp`，不要叠加多个 `lerp`。
- 滚动、缩放和设备旋转后重新计算输入相对主体的位置。
- 提供 `prefers-reduced-motion` 静态帧与资源失败降级。

至少验证冷缓存、慢速输入、快速反向、绕主体完整一圈、页面滚动后鼠标不动、窗口缩放、移动端和低性能设备。任何闪帧先按“母版 → 帧 → 图集 → 映射 → 解码”的顺序定位。

## 不得省略的报告

交付时明确列出：

- Motion Brief 和参数模型。
- 最终提示词以及首帧、尾帧、参考图。
- MiniMax 模型、分辨率、时长、seed 和任务元数据路径。
- 实际处理命令、原始帧数、清理后帧数和异常报告。
- 最终图集尺寸、单元格尺寸、解码内存估算和运行时格式。
- 网页映射、预加载、阻尼、限速和降级策略。
