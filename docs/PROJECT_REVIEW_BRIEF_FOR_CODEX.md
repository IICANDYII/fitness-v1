# fitness-v1 快速审阅说明

用途：把这份文档贴给另一个 Codex / Claude / ChatGPT 对话，让它不用从零扫完整仓库，也能快速进入正确审阅路径。

当前仓库：`/Users/maxgao/Documents/GitHub/fitness-v1`  
生成日期：2026-06-26  
建议先读本文，再按“最短审阅路径”打开对应文件。

## 可直接复制给另一个对话的提示词

```text
你现在审阅的是 fitness-v1 项目。请不要先泛泛讲架构，也不要把 agent_service/orchestrator.py 当成主实现。

这个项目的真实主链路是：
1. gym_analyzer/api.py 提供视频分析 API 和 analyzer.html 页面。
2. gym_analyzer/agent.py 用 Gemini/nextrouter tool calling 编排工具。
3. gym_analyzer/tools.py 的 analyze_frame_batch 会调用 gym_analyzer/pipeline.py。
4. gym_analyzer/pipeline.py 执行两阶段动作识别：抽帧元数据 -> 光流 -> Phase 1 区间划分 -> Phase 2 逐 EXERCISE 动作识别。
5. gym_analyzer/recognizer.py 是识别核心，使用 prompt YAML、拼图、光流、可选 IMU、exercise_mapping_v1.json 做 LLM 识别和标准化。

请优先审阅：
- gym_analyzer/api.py
- gym_analyzer/agent.py
- gym_analyzer/tools.py
- gym_analyzer/pipeline.py
- gym_analyzer/recognizer.py
- gym_analyzer/prompts/phase1_period_recognize_v6.yaml
- gym_analyzer/prompts/phase2_exercise_recognize_v9.yaml
- gym_analyzer/exercises_data/exercise_mapping_v1.json
- agent_service/reports/api.py
- agent_service/planner/plan_generator.py
- docs/current_action_recognition_flow.md
- graph_workflow_validation/HANDOFF_TO_CC.md

审阅重点：
- 当前动作识别是否真的按两阶段 pipeline 跑通。
- Agent tool calling 的提示词和实际工具是否一致。
- API、结果保存、DB 写入、dashboard 数据转换之间有没有字段不匹配。
- prompt 里强约束和当前输入信号是否一致，尤其光流、IMU、Phase 1、入场帧。
- 不要把 graph_workflow_validation/ 的实验结果误认为主流程输出；它是独立验证夹具。
```

## 项目一句话

`fitness-v1` 是一个第一人称健身视频/IMU动作识别 + 训练报告 + 训练计划生成 + 可穿戴 App 原型的组合项目。当前最关键的研发主线不是前端，也不是空的 OpenAI Agent SDK scaffold，而是 `gym_analyzer` 里的两阶段动作识别链路。

## 当前真实主链路

```text
gym_analyzer/analyzer.html
  -> POST /api/analyze
  -> gym_analyzer/api.py
  -> GymAnalyzerAgent.run()
  -> tool calling:
     extract_frames
     load_training_plan
     analyze_frame_batch
     compute_dashboard
     save_to_db
     save_result
  -> gym_analyzer/pipeline.py
  -> gym_analyzer/recognizer.py
  -> gym_analyzer/results/
  -> agent_service/reports/api.py / dashboard pages
```

关键点：

- `gym_analyzer/api.py` 是视频分析服务入口，默认服务页面是 `/analyzer`。
- `GymAnalyzerAgent` 现在已经是一层流程编排 Agent，但主要用途是按工具顺序调 pipeline，不是“易混动作专项 verifier agent”。
- `analyze_frame_batch()` 实际调用 `gym_analyzer.pipeline.run_pipeline()`。
- `run_pipeline()` 会读取 `frames_meta.json`，加载可选 `IMU_data.txt`，计算/加载 `optical_flow.json`，再走 Phase 1 和 Phase 2。
- Phase 2 的核心规则在 `gym_analyzer/prompts/phase2_exercise_recognize_v9.yaml`，动态拼接和后处理在 `gym_analyzer/recognizer.py`。

## 主要模块分工

| 模块 | 作用 | 审阅提示 |
|---|---|---|
| `gym_analyzer/` | 视频动作识别主系统 | 优先看这里，尤其 `pipeline.py`、`recognizer.py`、`tools.py` |
| `gym_analyzer/prompts/` | Phase 1 / Phase 2 prompt | 当前主版本是 `phase1_period_recognize_v6.yaml` 和 `phase2_exercise_recognize_v9.yaml` |
| `gym_analyzer/exercises_data/` | 标准动作映射 | `exercise_mapping_v1.json` 决定 LLM 输出如何标准化 |
| `agent_service/reports/` | Dashboard API 和报告页面 | 读取 DB / `gym_analyzer/results`，做肌群、周报、日历、时间轴展示 |
| `agent_service/planner/` | 训练计划生成 | 规则初筛 + embedding 排序 + LLM 生成周计划 |
| `agent_service/orchestrator.py` | 实时 fitness decision scaffold | 当前 `decide()` 仍是 `pass`，不要当主链路 |
| `Relty/` | 可穿戴 App / 前端原型 | 与识别主链路关联弱，更多是展示原型 |
| `shared/` | 评估/回放数据 | 不是共享代码库，是 ground_truth/optical_flow 等评估产物 |
| `graph_workflow_validation/` | graph 截图拼图识别验证夹具 | 独立实验目录，不要污染主流程结论 |

## 两阶段动作识别机制

Phase 1：粗区间识别

- 输入：全视频抽帧后的窗口拼图、光流摘要、可选 IMU 摘要。
- prompt：`gym_analyzer/prompts/phase1_period_recognize_v6.yaml`。
- 输出：`period_result.json`，包含 `segments` 和可能的 `equipment_timeline`。
- 目标：区分 `EXERCISE` / `REST` / `TRANSITION`，并尽量给出器械时间线。

Phase 2：逐动作精细识别

- 输入：每个 `EXERCISE` segment 扩展后的动作拼图、入场帧、光流摘要、可选 IMU 摘要、Phase 1 的器械/时间线信息。
- prompt：`gym_analyzer/prompts/phase2_exercise_recognize_v9.yaml`。
- 输出：`exercise_result.json`，包含 `equipment`、`exercise`、`exercise_id`、`sets`、`confidence`、候选和上下文。
- 后处理：通过 `exercise_mapping_v1.json` 标准化动作名称；必要时生成 `period_result_adjusted.json` 修正 Phase 1。

## API 和运行环境

常见启动入口：

- Windows：`start_dashboard.bat`
- macOS：`start_dashboard_mac.sh`
- 停止脚本：`stop_dashboard_mac.sh`
- DB：`docker-compose.dev.yml` 启动 PostgreSQL + pgvector，默认端口 `5432`

常见服务：

| 服务 | 端口 | 入口 |
|---|---:|---|
| Dashboard API | 8000 | `agent_service.reports.api:app` |
| Gym Analyzer API | 8002 | `gym_analyzer.api:app` |

关键环境变量：

- `NEXTROUTER_API_KEY` 或 `API_KEY`
- `NEXTROUTER_BASE_URL`
- `GEMINI_FLASH_MODEL`
- DB 相关：`DB_HOST` / `POSTGRES_HOST`、`DB_PORT` / `POSTGRES_PORT`、`DB_NAME` / `POSTGRES_DB`、`DB_USER` / `POSTGRES_USER`、`DB_PASSWORD` / `POSTGRES_PASSWORD`

注意：`agent_service/planner/plan_generator.py` 里存在硬编码 API key 默认值。审阅安全性时应单独标出，不要忽略。

## 已知审阅陷阱

- 不要只看 `agent_service/orchestrator.py`。它看起来像 Agent SDK 主入口，但目前 `decide()` 没实现。
- 不要把 `recognize/src_new/` 或 `recognize/visualize/` 当成唯一主线；当前真实运行入口集中在 `gym_analyzer/`。
- `shared/` 不是通用 shared library，而是评估/回放数据。
- `graph_workflow_validation/` 是为了验证 `graph/` 截图拼图动作识别的独立夹具，里面的 prompt 模式和结果是实验性质。
- 当前 graph 输入缺少真实光流、IMU、Phase 1 结果、入场帧和时间戳；因此相关实验不能直接等同生产 pipeline 表现。
- LLM `confidence` 是模型自评，不是客观准确率；客观指标应来自预测和 ground truth 的对比。
- 当前工作区已有未提交改动和新增目录，审阅时先看 `git status --short`，不要误以为全是基线代码。

## Graph 验证结论速览

`graph_workflow_validation/` 已做过三种模式：

| 模式 | 位置 | 结果速览 |
|---|---|---|
| `full-pipeline` | `graph_workflow_validation/results/` | 修正后 groundtruth：63 条中 24 match，39 mismatch |
| `yaml-only` | `graph_workflow_validation/yaml_only_results/` | 63 条中 23 match，39 mismatch，1 API error |
| `image-main-focus` | `graph_workflow_validation/image_main_focus_results/` | 只重跑 39 个 mismatch，修好 6 个，剩 33 个 mismatch |

重要解释：

- `image-main-focus` 不是去掉易混动作，而是跳过 graph 输入不具备的光流/IMU/Phase 1/入场帧硬约束。
- 结果只小幅改善，说明主要瓶颈仍是第一人称截图下的视觉判别和易混动作优先级。
- 高发混淆包括：绳索下拉/单臂绳索下拉/直杆高位下拉/面拉/绳索锤式弯举坍缩成绳索下压，夹胸/推胸混淆，跑步机/爬楼机混淆。

## 最短审阅路径

1. 先看整体流程：`docs/current_action_recognition_flow.md`
2. 看 API 入口：`gym_analyzer/api.py`
3. 看 Agent 编排：`gym_analyzer/agent.py`
4. 看工具桥接：`gym_analyzer/tools.py`
5. 看主 pipeline：`gym_analyzer/pipeline.py`
6. 看识别核心：`gym_analyzer/recognizer.py`
7. 看 prompt：`gym_analyzer/prompts/phase1_period_recognize_v6.yaml`、`gym_analyzer/prompts/phase2_exercise_recognize_v9.yaml`
8. 看标准动作映射：`gym_analyzer/exercises_data/exercise_mapping_v1.json`
9. 看结果如何进入看板：`agent_service/reports/api.py`
10. 如果审阅 graph 实验，再看：`graph_workflow_validation/HANDOFF_TO_CC.md`

## 建议重点问题清单

- `GymAnalyzerAgent` system prompt 里描述的工具顺序和 `TOOL_SCHEMAS` / `TOOL_REGISTRY` 是否完全一致。
- `analyze_frame_batch()` 的函数参数和 Agent 传参是否存在字段漂移。
- `pipeline.py` 的 shared 光流缓存路径是否仍符合当前目录结构。
- Phase 1 输出字段是否被 Phase 2 正确消费，尤其 `segmentId`、`equipment_timeline`、`start_sec`、`end_sec`。
- Phase 2 输出的动作名、`exercise_id`、`sets`、`confidence` 是否能被 `_convert_v2_results()`、`compute_dashboard()` 和 DB 写入稳定消费。
- `exercise_mapping_v1.json` 的动作覆盖是否足够；`UNKNOWN_ACTION` 的处理是否会污染报告。
- prompt 中对光流、IMU、入场帧、训练计划、器械时间线的约束是否和真实输入一致。
- Dashboard 的 `EXERCISE_ALIAS` 和 `gym_analyzer` 的标准动作映射是否存在双套标准。
- planner 的硬编码 key、DB 默认密码、日志和结果目录是否适合提交/部署。
- `graph_workflow_validation/` 的验证结果是否应转化为 prompt 规则、动作候选分组或 verifier，而不是只保留实验输出。

## 当前工作区提示

生成本文时，`git status --short` 显示已有未提交改动，涉及：

- `gym_analyzer/agent.py`
- `gym_analyzer/api.py`
- `gym_analyzer/config.py`
- `gym_analyzer/extractor.py`
- `gym_analyzer/recognizer.py`
- `gym_analyzer/stitcher.py`
- `gym_analyzer/input/.../frames_meta.json`
- 新增：`artifacts/`、`docs/current_action_recognition_flow.md`、`docs/dify_action_recognition_workflow.md`、`graph_workflow_validation/`、`logs/`、`requirements-mac.txt`、macOS 启停脚本、`shared/`

接手审阅时请把这些视作当前现场状态，不要随手 revert。
