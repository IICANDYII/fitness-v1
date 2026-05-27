# 健身 Agent — 视频分析后端

基于第一视角健身视频 + 心率数据，自动生成训练日报 + 月历的 Python 后端。

## 工作流

```
video.mp4 + heart_rate.csv + user_profile.json
        ↓
[1] keyframe_extractor       → 每 3 秒抽 1 帧 + 计算 motion
[2] frame_classifier         → GPT-5 视觉识别每帧（status / equipment / movement）
[3] segment_merger           → 关键帧 → VideoSegment 时间线
[4] set_detector             → 段内切组 + tempo 估次数
[5] heart_rate_loader        → CSV → 标准化心率数据
[6] calorie_calculator       → 心率法 / MET 法卡路里
[7] visualizer               → timeline / pie / hr_curve / time_breakdown PNG
[8] report_generator         → report.md
        ↓
calendar_view                → 按月扫描，生成月历 PNG + MD
```

## 目录结构

```
video_analysis/
├── src/
│   ├── pipeline.py              # CLI 入口
│   ├── models.py                # 数据类（VideoSegment / WorkoutSession 等）
│   ├── config.py                # 器械库 / tempo / MET / 心率区间 / 部位映射
│   ├── keyframe_extractor.py    # 3 秒抽帧 + motion 计算
│   ├── frame_classifier.py      # 批次模式（8 张/批）GPT 分类
│   ├── frame_classifier_full_context.py  # 全量模式（所有帧拼网格图一次性提交）
│   ├── segment_merger.py        # 关键帧 → VideoSegment + 组间休息吸收
│   ├── set_detector.py          # 段内切组 + tempo 估次数
│   ├── heart_rate_loader.py     # CSV 心率解析
│   ├── calorie_calculator.py    # 心率法 + MET 法 + 心率区间
│   ├── visualizer.py            # matplotlib 图表
│   ├── report_generator.py      # 日报 MD 生成
│   └── calendar_view.py         # 月历汇总
├── user_profile.json            # 用户资料（体重/年龄/性别/最大心率）
├── requirements.txt
├── 分析部分数据格式.md           # 技术方案 v2.1
├── 心率曲线.jpg                  # 心率曲线视觉参考
├── video/                       # 输入视频 + 心率 CSV（gitignored）
└── output/{视频名}/              # 产物输出（gitignored）
    ├── frames/
    ├── keyframes.json
    ├── workout_session.json
    ├── timeline.png / pie.png / hr_curve.png / time_breakdown.png
    └── report.md
```

## CLI 用法

```bash
# 默认批次模式（8 张/批）
python -m src.pipeline video/20260525-132917.mp4

# 全量上下文模式（所有帧拼成一张大网格图一次性提交）
python -m src.pipeline video/20260525-132917.mp4 --full-context

# 复用已有的 GPT 分类结果，只重生成图表 + 报告
python -m src.pipeline video/20260525-132917.mp4 --skip-classify

# 生成某月月历
python -m src.calendar_view 2026 5
```

心率 CSV 自动按文件名匹配：`{视频名}_heart_rate_data.csv`。

## 关键设计点

- **17 个器械标签** + **每器械下的具体动作清单**（在 `config.EQUIPMENT_LIBRARY` 定义）
- **3 秒抽帧** 平衡识别精度和成本
- **组数检测**：段内连续 ≥2 帧 rest（≥6s 静止）视为组间休息
- **次数估算**：tempo 法（动作时长 / 该动作典型节奏）
- **卡路里**：有心率用 Keytel 心率公式；无心率回退到 MET × 体重
- **心率区间**：基于最大心率（用户填写 或 `220 - age`）的 5 级（热身/燃脂/有氧/峰值/极限）
- **月历强度等级**：按主导心率区间 + kcal/min 兜底，5 级（休息/低/中/高/极强度）
- **训练部位**：胸/背/肩/臂/腿/腹/心肺 7 类（按 movementName 关键词映射）

## 已知问题

- 第一视角下 **悍马机/划船 偶尔被误识为引体向上**（视觉特征相似：双立柱 + 上方握把）
- **次数估算偏粗**（依赖 tempo 表 + 切组阈值），建议接前端后用户手动校验
- 全量上下文模式（`--full-context`）有**过度合并**倾向，AI 看完整时间线后倾向给出粗粒度分段

## 环境

- Python 3.11+
- 关键依赖：`opencv-python<5`、`numpy<2`（matplotlib 3.10 与 numpy 2 ABI 不兼容）、`pandas<3`、`openai>=1.30`、`matplotlib`、`python-dotenv`
- AI 模型：`gpt-5`（视觉），可在 `src/config.py` 修改

`.env`（不入库）必须包含：
```
API_KEY=sk-...
BASE_URL=https://your-gateway/v1   # 自建网关或官方 endpoint
```
（也兼容 `OPENAI_API_KEY` / `OPENAI_BASE_URL`）
