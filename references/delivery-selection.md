# 自动选择交付方式

Oil Motion 的交付选择分两级，都不是用户选项：

1. **背景归属**：由 Concept Contract 锁定 `background_owner`，来自用户需求本身，不由
   Agent 的工具偏好决定。
2. **预算与访问方式**：由 `motion_budget.py` 自动计算，Agent 直接执行
   `delivery.selected`，不要询问用户“要视频还是雪碧图”，也不要为了方便同时实现
   两套主方案。

`--background-owner` 是强制参数，没有默认值。合同尚未锁定时脚本必须阻断，绝不能
因为漏传参数而静默选择 `page` 或绿幕路线。
多段生成同样必须在合同中写明 `clip_continuity: chain | independent`；Pilot 批准文件会锁定该值，production 阶段不能改写。

## 第一级：背景归属

- `background_owner: video`（默认场景路线）：背景与主体在同一视频中烘焙生成。
  镜头运动、环境光、地面接触或阴影、景深、背景连续性中任意一项重要，或主体不需要
  脱离背景复用时使用。交付 `baked-video`，不抠色。
- `background_owner: page`（透明复用路线）：主体必须以透明形式叠加到页面自有、
  可更换的背景上时才使用。所有生成素材使用均匀色键背景，再由预算在
  `alpha-atlas` 与 `chroma-video` 之间选择。

禁止把“镜头、环境光、地面接触重要”的场景硬塞进 chroma 路线，也禁止把“需要透明
复用”的主体烘焙进场景。选错背景归属是路线错误，返工成本高于重新生成。

## 第二级：必须执行预算脚本

把 Motion Brief 的真实参数连同合同锁定的背景归属一起传给脚本：

```bash
python3 scripts/motion_budget.py \
  --frames 551 \
  --display 1536x864 \
  --dpr 1 \
  --driver scroll \
  --parameter-space linear \
  --background-owner video \
  --scroll-pages 8 \
  --report build/motion-budget.json \
  --strict \
  --json
```

读取 `delivery.selected`、`delivery.reasonCodes` 和 `delivery.thresholds`。
`--report` 保存的文件是后续编译的强制输入，运行时实现必须与选择结果一致。

## 固定决策顺序

1. `background_owner=video`：选择 `baked-video`。二维或离散参数不能压成一条线性
   烘焙视频，必须拆成多条独立片段分别预算。
2. `parameter_space=2d`：选择 `alpha-atlas`。二维输入需要网格随机访问，不能压成
   一条线性视频。
3. `parameter_space=discrete`：预算内选择 `alpha-atlas`；超预算时拆成独立状态或
   转场并分别预算，不能把无序状态拼成一条视频。
4. 随机访问且单张图集、解码内存都在预算内：选择 `alpha-atlas`。
5. 一维顺序访问且不少于 180 帧：选择 `chroma-video`。
6. 一维资源的理论 Alpha 图集超过单张 4096 纹理或 192 MiB 解码内存：选择
   `chroma-video`；若是随机访问，增加快速跳转和反向 seek 验收。
7. 其余小型资源：选择 `alpha-atlas`。

默认阈值来自 `motion_budget.py`，可根据明确的目标设备约束通过命令参数调整，但不
能根据用户是否懂技术来调整。

## 三种典型结果

场景叙事（演武、镜头穿越、环境光重要的画面）：

```bash
python3 scripts/motion_budget.py \
  --frames 551 --display 1536x864 --dpr 1 \
  --driver scroll --parameter-space linear \
  --background-owner video --strict
```

应选择 `baked-video`，因为 Concept Contract 把背景归属锁定为视频。

小型鼠标方向环（透明复用）：

```bash
python3 scripts/motion_budget.py \
  --frames 96 --display 240x240 --dpr 1 \
  --driver pointer --parameter-space circular \
  --background-owner page --strict
```

应选择 `alpha-atlas`，因为需要快速随机反向，且单张图集可承受。

全屏长滚动（透明复用）：

```bash
python3 scripts/motion_budget.py \
  --frames 551 --display 1536x864 --dpr 1 \
  --driver scroll --parameter-space linear \
  --background-owner page --strict
```

应选择 `chroma-video`，因为线性时间轴很长，图集的理论解码内存和纹理数量远高于
视频路线。

## 超预算处理

- `alpha-atlas` 被选中但报告不通过：二维输入降低采样密度或调整已确认的显示尺寸；
  离散输入拆成独立状态或转场。之后重新预算，不得偷偷压低单帧清晰度。
- `chroma-video` 被选中：不得再生成全量 Alpha PNG 或大型图集作为主资源；只保留
  QA 所需帧和静态 Alpha 降级图。
- `baked-video` 被选中：二维或离散参数必须拆成多条独立片段分别预算；不得在运行时
  对烘焙视频做任何抠色。
- chroma 两条路线都保留原始绿幕母版，页面背景始终由 CSS 或页面合成层提供；
  baked 路线保留原始场景母版，背景属于视频本身。

## 路由到后续流程

- `alpha-atlas`：阅读 [minimax-spritesheet.md](minimax-spritesheet.md)。
- `chroma-video`：阅读 [chroma-video.md](chroma-video.md)。
- `baked-video`：阅读 [baked-video.md](baked-video.md)。
