# 自动选择交付方式

Oil Motion 始终使用同一套绿幕生产链，只在网页交付阶段二选一：

- `alpha-atlas`：构建时离线抠色，网页读取 Alpha 图集。
- `chroma-video`：保留绿幕视频，网页用 WebGL 实时抠色。

这是 Agent 的构建决策，不是用户选项。不要询问用户“要视频还是雪碧图”，也不要为了方便同时实现两套主方案。

## 必须执行预算脚本

把 Motion Brief 的真实参数传给脚本：

```bash
python3 scripts/motion_budget.py \
  --frames 551 \
  --display 1536x864 \
  --dpr 1 \
  --driver scroll \
  --parameter-space linear \
  --scroll-pages 8 \
  --report build/motion-budget.json \
  --strict \
  --json
```

读取 `delivery.selected`、`delivery.reasonCodes` 和 `delivery.thresholds`。`--report` 保存的文件是后续编译的强制输入，运行时实现必须与选择结果一致。

## 固定决策顺序

1. `parameter_space=2d`：选择 `alpha-atlas`。二维输入需要网格随机访问，不能压成一条线性视频。
2. `parameter_space=discrete`：预算内选择 `alpha-atlas`；超预算时拆成独立状态或转场并分别预算，不能把无序状态拼成一条视频。
3. 随机访问且单张图集、解码内存都在预算内：选择 `alpha-atlas`。
4. 一维顺序访问且不少于 180 帧：选择 `chroma-video`。
5. 一维资源的理论 Alpha 图集超过单张 4096 纹理或 192 MiB 解码内存：选择 `chroma-video`；若是随机访问，增加快速跳转和反向 seek 验收。
6. 其余小型资源：选择 `alpha-atlas`。

默认阈值来自 `motion_budget.py`，可根据明确的目标设备约束通过命令参数调整，但不能根据用户是否懂技术来调整。

## 两种典型结果

小型鼠标方向环：

```bash
python3 scripts/motion_budget.py \
  --frames 96 --display 240x240 --dpr 1 \
  --driver pointer --parameter-space circular --strict
```

应选择 `alpha-atlas`，因为需要快速随机反向，且单张图集可承受。

全屏长滚动：

```bash
python3 scripts/motion_budget.py \
  --frames 551 --display 1536x864 --dpr 1 \
  --driver scroll --parameter-space linear --strict
```

应选择 `chroma-video`，因为线性时间轴很长，图集的理论解码内存和纹理数量远高于视频路线。

## 超预算处理

- `alpha-atlas` 被选中但报告不通过：二维输入降低采样密度或调整已确认的显示尺寸；离散输入拆成独立状态或转场。之后重新预算，不得偷偷压低单帧清晰度。
- `chroma-video` 被选中：不得再生成全量 Alpha PNG 或大型图集作为主资源；只保留 QA 所需帧和静态 Alpha 降级图。
- 两条路线都保留原始绿幕母版，页面背景始终由 CSS 或页面合成层提供。

## 路由到后续流程

- `alpha-atlas`：阅读 [minimax-spritesheet.md](minimax-spritesheet.md)。
- `chroma-video`：阅读 [chroma-video.md](chroma-video.md)。
