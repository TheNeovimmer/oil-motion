<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="Oil Motion 把首尾关键帧和 MiniMax 视频编译成由滚动、指针或拖拽控制的网页交互动画">
</p>

Oil Motion 是一个 Agent 通用的交互动画 Skill，也可以脱离 Agent 直接运行脚本。它先用关键帧锁定正确结果，再让
MiniMax H3 生成连续动作母版，最后通过确定性脚本完成切帧、质检、压缩、打包和网页
输入映射。

生成模型负责画面和动作，程序负责清晰度、性能与交互稳定性。

## 演示

https://github.com/user-attachments/assets/08e26ad6-ca23-4f31-ac53-44c7692ba99d


## 安装

```bash
git clone https://github.com/oil-oil/oil-motion.git
cd oil-motion
python3 -m pip install -r scripts/requirements.txt
```

同时需要本机安装 `ffmpeg` 和 `ffprobe`。生成 MiniMax 动作母版时，再设置
`ZENMUX_API_KEY`；只处理已有视频或序列帧时不需要密钥。需要作为 Skill 使用时，
将仓库目录放进所用 Agent 的 Skills 目录即可。

## 它解决什么

- **结果不可控**：先验收首尾关键帧，不让视频模型临时发明终点。
- **视频不能交互**：把连续动作编译成图集、序列帧或可精确定位的视频。
- **动画容易卡顿**：根据访问模式、展示尺寸和 DPR 选择资源，而不是盲目堆帧。
- **生成结果难复用**：保留提示词、任务元数据、母版、质检报告和运行时参数。

## 工作方式

```text
参考图
  ↓
生成并验收 K0、K1…Kn
  ↓
MiniMax H3 生成相邻关键帧之间的动作母版
  ↓
探测 → 切帧 → 裁停顿 → 查重 → 质检
  ↓
图集 / 全关键帧 MP4 / WebCodecs
  ↓
scroll / pointer / drag / touch / orientation
```

Oil Motion 会先区分两类变化：

- **语义运动**：产品拆解、肢体形变、材质变化、前后遮挡，由关键帧和 AI 视频完成。
- **几何运动**：位移、缩放、裁切、时间映射、阻尼和限速，由程序完成。

如果只移动整张图片无法保持关节、接触点或遮挡自然，就不应该继续写 CSS 补丁。

## 快速开始

在支持 Skills 的 Agent 中直接说明目标、素材和交互方式：

```text
使用 $oil-motion，把这两张已经验收的首尾图做成由滚动控制的产品爆炸动画。
最大展示宽度 960px，桌面 DPR 2；移动端最大展示宽度 640px，DPR 2。
```

如果还没有动作方案，也可以只给出对象和目的：

```text
使用 $oil-motion，为这个产品首页设计一个随滚动变化的连续动画。
先给出最多三个有明确表达目的的方向，再选择最适合实现的方案。
```

## 默认生产规则

| 项目 | 默认值 |
| --- | --- |
| 视频模型 | `minimax/minimax-h3` |
| 动作验证 | `768p`、5 秒 |
| 大尺寸终稿 | 关键帧通过后使用 `2K` |
| 画幅 | 按首帧或参考图自动推断常用比例 |
| 音频 | 交互资产最终显式移除 |
| 首尾帧模式 | `first_frame + last_frame` |
| 参考图模式 | 只传 `reference_image` |

MiniMax H3 的参考图模式和首尾帧模式互斥。`video_job.py` 会在联网前阻止混用，避免
接口错误 `2013`。使用 `frames` 时也不能同时传 `duration`。

## 两条交付路线

| 需求 | 推荐资产 | 适用原因 |
| --- | --- | --- |
| 透明背景、短序列、任意跳帧 | WebP 图集 | 一次请求，随机访问稳定 |
| 高分辨率、不透明、一维滚动 | 全关键帧 MP4 | seek 稳定，内存远低于巨型图集 |
| 图集超过纹理限制 | 分片图集或 WebCodecs | 保持单帧清晰度 |
| 少量 hover / 点击状态 | 多段短资源 | 状态边界清楚 |

压缩宽度必须来自“最大实际 CSS 展示宽度 × 目标 DPR”。体积不达标时优先更换格式，
不能继续缩小到清晰度门槛以下。

## MiniMax 动作母版

密钥只从环境变量读取：

```bash
export ZENMUX_API_KEY="..."
export OIL_MOTION="/absolute/path/to/oil-motion"
```

单向转场：

```bash
python3 "$OIL_MOTION/scripts/video_job.py" \
  --prompt-file source/prompt.txt \
  --first-frame source/first-frame.png \
  --last-frame source/last-frame.png \
  --resolution 2K \
  --output source/master.mp4
```

闭环动作：

```bash
python3 "$OIL_MOTION/scripts/video_job.py" \
  --prompt-file source/prompt.txt \
  --first-frame source/first-frame.png \
  --loop-frame \
  --resolution 768p \
  --output source/master.mp4
```

身份、产品结构、Logo、构图和风格需要在关键帧生图阶段解决。首尾帧请求中不要再次
附加 `reference_image`。

## 一键编译滚动动画

高分辨率的一维滚动动画可以直接编译成桌面与移动端版本：

```bash
python3 "$OIL_MOTION/scripts/compile_scroll_video.py" \
  source/master.mp4 build/scroll \
  --end-reference source/last-frame.png \
  --desktop-width 1920 \
  --mobile-width 1280
```

脚本会自动：

1. 读取真实分辨率、帧率、时长和音轨。
2. 切出 24 FPS 母版帧。
3. 按目标尾帧裁掉停顿并删除近重复帧。
4. 生成分析报告与编号接触表。
5. 输出桌面、移动端全关键帧 H.264 MP4。
6. 强制移除音轨并生成 `compile.json`。

闭环动画使用 `--loop`。默认禁止上采样；目标宽度超过母版时会自动限制为母版宽度。

## 图集与透明动画

透明角色、视线跟随和需要随机访问的短序列使用媒体流水线：

```bash
python3 "$OIL_MOTION/scripts/motion_budget.py" \
  --frames 120 \
  --display 240x240 \
  --dpr 2 \
  --max-texture 4096 \
  --access random \
  --strict

python3 "$OIL_MOTION/scripts/motion_pipeline.py" extract \
  source/master.mp4 frames/raw \
  --fps 24 \
  --key auto

python3 "$OIL_MOTION/scripts/motion_pipeline.py" analyze frames/raw \
  --output qa/analysis.json

python3 "$OIL_MOTION/scripts/motion_pipeline.py" contact frames/raw \
  --output qa/contact-sheet.jpg
```

查看接触表并通过验收后，再运行 `atlas`。不要用一键 `build` 跳过中间检查。

## 工具箱

| 脚本 | 作用 |
| --- | --- |
| `video_job.py` | 提交、轮询并下载 MiniMax H3 动作母版 |
| `motion_budget.py` | 计算单帧清晰度、采样密度和纹理预算 |
| `motion_pipeline.py` | 探测、切帧、抠色、稳定、分析、接触表和图集 |
| `loop_cleanup.py` | 选择接缝、裁尾部停顿并删除近重复帧 |
| `optimize_motion.py` | 补帧对比与按清晰度门槛压缩 |
| `compile_scroll_video.py` | 编译桌面与移动端全关键帧滚动视频 |
| `create_explainer.py` | 生成“母版 → 帧 → 输入映射”的原理展示页 |

## 支持的输入

- `scroll`：产品拆解、章节变化、图表展开、场景转场。
- `pointer`：角色朝向、产品方向、视线跟随。
- `drag`：时间轴、结构拆装、进度预览。
- `touch`：移动端直接控制。
- `orientation`：经过授权与校准的陀螺仪输入。
- `audio / data / state`：音量、实时数据或离散组件状态。

二维输入不能强行压进一条左右往返视频。距离和方向都会改变姿态时，需要二维采样。

## 质量门槛

交付前至少检查：

- 身份、结构、比例、锚点和光线在全序列一致。
- 没有多余肢体、部件复制、硬切、闪帧和异常停顿。
- 透明素材没有色键残留，细线和内部白色区域完整。
- 快速反向时不粘滞、不抽动、不越界。
- 滚动、缩放和设备旋转后，输入位置仍然正确。
- 冷缓存有首帧或 poster，资源失败时能回退静态画面。
- 最终资源在真实 CSS 尺寸和目标 DPR 下清晰。
- `prefers-reduced-motion` 有静态替代。

程序可以修复轻微漂移、颜色、重复帧和编码问题，不能修复错误的动作语义。

## 运行环境

- Python 3
- Pillow
- ffmpeg
- ffprobe
- ZenMux API Key

```bash
python3 -m pip install -r scripts/requirements.txt
ffmpeg -version
ffprobe -version
```

## 输出结构

```text
motion-name/
├── source/
│   ├── first-frame.png
│   ├── last-frame.png
│   ├── prompt.txt
│   ├── master.mp4
│   └── master.job.json
├── frames/
│   ├── raw/
│   └── final/
├── qa/
│   ├── analysis.json
│   └── contact-sheet.jpg
└── final/
    ├── motion.webp
    ├── motion-scrub-desktop.mp4
    ├── motion-scrub-mobile.mp4
    ├── motion.json
    └── implementation.*
```

详细原则、提示词、运行时选择和 QA 规则见 [`SKILL.md`](./SKILL.md) 与
[`references/`](./references/)。

## License

[MIT](./LICENSE)
