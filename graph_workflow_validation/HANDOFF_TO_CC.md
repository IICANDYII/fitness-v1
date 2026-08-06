# Graph 动作识别验证交接文档

接手对象：CC  
项目目录：`/Users/maxgao/Documents/GitHub/fitness-v1`  
验证目录：`graph_workflow_validation/`  
当前日期：2026-06-25

## 背景

本轮工作是验证 `graph/` 文件夹里的抽帧截图拼图能否通过现有 Gemini 动作识别流程识别出动作，并和 `shared/*/ground_truth.json` 以及用户后续人工修正后的 groundtruth 做对照。

用户强调：

- 必须走项目里的 Gemini/nextrouter API 调用链，不用 Codex 自己的 API。
- 所有验证 prompt、脚本、结果都单独放在 `graph_workflow_validation/`，不要污染主流程输出。
- 当前 graph 输入只有抽帧拼图，没有真实光流、IMU、Phase 1 equipment/posture、入场帧原图和时间戳。
- 当前重点不是完整 `recognizer.py` 里的所有约束，而是 Phase 1 切出每段运动后，Phase 2 对每段单独调用 AI，回答：器械、动作、动作方向、几组、每组几次，以及后处理所需的候选动作、置信度和上下文。

## 重要结论

置信度不是客观概率，是大模型对自己判断的主观自评。客观指标来自预测结果和用户修正后 groundtruth 的对比。

旧的 `full-pipeline` 跑法把 `recognizer.py` 中大量动态 prompt 直接注入模型，其中包含光流、IMU、Phase 1 结果、入场帧等当前 graph 不具备的信息。这样会让模型在缺输入时仍强行套约束，导致高置信错判。

后续新增的 `image-main-focus` 模式没有去掉易混淆动作，而是跳过当前输入不存在的光流/IMU/Phase 1 硬约束，同时保留器械优先、第一人称、动作候选、置信度校准、组次估计和后处理语境。它只修好了一小部分错例，说明真正的主要问题还在图片视觉判别和易混动作优先级。

## 当前关键文件

脚本：

- `graph_workflow_validation/analyze_graph_actions.py`
- `graph_workflow_validation/build_ground_truth_alignment.py`
- `graph_workflow_validation/apply_manual_ground_truth_corrections.py`
- `graph_workflow_validation/compare_predictions_to_corrected_gt.py`

主 prompt / 主流水线相关：

- `gym_analyzer/prompts/phase2_exercise_recognize_v9.yaml`
- `gym_analyzer/recognizer.py`

重要输出：

- `graph_workflow_validation/results/graph_action_predictions.json`
- `graph_workflow_validation/results/graph_action_predictions.md`
- `graph_workflow_validation/yaml_only_results/graph_action_predictions.json`
- `graph_workflow_validation/yaml_only_results/yaml_only_corrected_prediction_comparison.md`
- `graph_workflow_validation/ground_truth_alignment/corrected_ground_truth_by_graph.json`
- `graph_workflow_validation/ground_truth_alignment/corrected_prediction_comparison.md`
- `graph_workflow_validation/image_main_focus_results/graph_action_predictions.json`
- `graph_workflow_validation/image_main_focus_results/image_main_focus_corrected_prediction_comparison.md`

## 已生成的三轮结果

### 1. full-pipeline

位置：

- `graph_workflow_validation/results/`
- 对比文件：`graph_workflow_validation/ground_truth_alignment/corrected_prediction_comparison.md`

口径：

- 注入 `recognizer.py` 中 `_recognize_one_exercise` 的动态 prompt 构造源码。
- 严格贴近主流水线，但对 graph 图片这种缺少光流/IMU/Phase1 的输入不够友好。

修正后 groundtruth 对比结果：

- Total evaluated: 63
- Normalized matches: 24
- Mismatches: 39

### 2. yaml-only

位置：

- `graph_workflow_validation/yaml_only_results/`
- 对比文件：`graph_workflow_validation/yaml_only_results/yaml_only_corrected_prediction_comparison.md`

口径：

- 只用 `phase2_exercise_recognize_v9.yaml`，不注入 `recognizer.py` 动态长规则。

修正后 groundtruth 对比结果：

- Total evaluated: 63
- Normalized matches: 23
- Mismatches: 39
- API errors: 1

备注：

- `肩背-叶翔/动作8` 曾出现空响应/API error。

### 3. image-main-focus

位置：

- `graph_workflow_validation/image_main_focus_results/`
- 对比文件：`graph_workflow_validation/image_main_focus_results/image_main_focus_corrected_prediction_comparison.md`

口径：

- 只重跑 full-pipeline 中原来的 39 个 mismatch。
- 仍走 `gym_analyzer.recognizer._gemini_generate()`，即 Gemini/nextrouter API。
- 保留图片识别流程所需输出：器械、动作、方向、组次、候选、置信度、上下文。
- 明确跳过当前 graph 输入没有的光流、IMU、Phase 1 参考值、入场帧硬约束。

结果：

- Total evaluated: 39
- Matches: 6
- Mismatches: 33
- API errors: 0

这轮修好的 6 个：

| folder | action | groundtruth | new prediction |
|---|---|---|---|
| 4 | 动作1 | 宽距高位下拉 | 高位下拉 |
| 4 | 动作9 | 哑铃弯举 | 哑铃弯举 |
| 肩-秦紫渝 | 动作1 | 跑步 | 跑步机 |
| 肩背-叶翔 | 动作4 | 直杆高位下拉 | 高位下拉 |
| 腿-张开 | 动作2 | 杠铃深蹲 | barbell_squat |
| 腿-张开 | 动作8 | 未知动作 | UNKNOWN_ACTION |

仍然高置信错判的主要簇：

- 绳索下拉 / 单臂绳索下拉 / 直杆高位下拉 / 面拉 / 绳索锤式弯举 被坍缩成绳索下压。
- 史密斯卧推被识别成高位下拉。
- 夹胸和推胸混淆。
- 跑步机和爬楼机混淆。
- 哑铃卧推、哑铃弯举在部分遮挡或第一人称视角下被误判为别的器械动作。

## 用户修正后的 groundtruth 规则

用户后续澄清过一个关键点：

未提到的动作继续沿用原始 `ground_truth.json` / base alignment；用户提到的动作覆盖原始标注。

当前修正逻辑写在：

- `graph_workflow_validation/apply_manual_ground_truth_corrections.py`

特别注意：

- `腿-张开/动作6` 和 `腿-张开/动作8` 保留为 `未知动作`，不是删除。
- 不要直接改 `shared/*/ground_truth.json`，本轮验证用的是独立 corrected groundtruth 文件。

修正后 groundtruth 输出：

- `graph_workflow_validation/ground_truth_alignment/corrected_ground_truth_by_graph.json`
- `graph_workflow_validation/ground_truth_alignment/corrected_ground_truth_by_graph.md`

## 常用命令

重新生成用户修正后的 groundtruth：

```bash
python3 graph_workflow_validation/apply_manual_ground_truth_corrections.py
```

跑 full-pipeline：

```bash
.venv/bin/python graph_workflow_validation/analyze_graph_actions.py \
  --prompt-mode full-pipeline \
  --out-dir graph_workflow_validation/results \
  --workers 4 \
  --overwrite
```

跑 yaml-only：

```bash
.venv/bin/python graph_workflow_validation/analyze_graph_actions.py \
  --prompt-mode yaml-only \
  --out-dir graph_workflow_validation/yaml_only_results \
  --workers 4 \
  --overwrite
```

只重跑 full-pipeline 的 mismatch，并使用 image-main-focus：

```bash
.venv/bin/python graph_workflow_validation/analyze_graph_actions.py \
  --prompt-mode image-main-focus \
  --only-mismatches-from graph_workflow_validation/ground_truth_alignment/corrected_prediction_comparison.json \
  --out-dir graph_workflow_validation/image_main_focus_results \
  --workers 4 \
  --overwrite
```

比较某个预测文件和修正后 groundtruth：

```bash
python3 graph_workflow_validation/compare_predictions_to_corrected_gt.py \
  --predictions graph_workflow_validation/image_main_focus_results/graph_action_predictions.json \
  --out-json graph_workflow_validation/image_main_focus_results/image_main_focus_corrected_prediction_comparison.json \
  --out-md graph_workflow_validation/image_main_focus_results/image_main_focus_corrected_prediction_comparison.md
```

## API 和运行注意事项

- Gemini 调用路径在 `gym_analyzer/recognizer.py` 的 `_gemini_generate()`。
- 它读取环境变量：
  - `NEXTROUTER_API_KEY`
  - `NEXTROUTER_BASE_URL`
  - `GEMINI_FLASH_MODEL`
- 当前使用模型默认是 `gemini-3-flash-preview`。
- 跑 image-main-focus 时中途出现过 429 和 HTTP 524，但脚本重试成功，最终 API error 为 0。
- 之前 yaml-only 有一次 API empty response / error；如果重跑，注意额度和接口稳定性。

## 当前工作区状态

`graph_workflow_validation/` 是本轮新增的验证目录，目前未跟踪。

`git status` 显示还有不少主项目文件已修改或未跟踪，例如：

- `gym_analyzer/agent.py`
- `gym_analyzer/api.py`
- `gym_analyzer/config.py`
- `gym_analyzer/extractor.py`
- `gym_analyzer/recognizer.py`
- `gym_analyzer/stitcher.py`
- `shared/`
- `docs/dify_action_recognition_workflow.md`

这些不一定都是本轮验证造成的，接手时不要随意 revert。尤其不要用 `git reset --hard` 或 `git checkout --` 清理。

## 下一步建议

优先不要继续简单删规则。当前证据显示，去掉光流/IMU硬约束只修复了 6/39 个错例，主要错误仍来自图片视觉判别和易混动作优先级。

建议下一步改 prompt 时集中处理：

- 绳索类动作候选表：下拉、单臂下拉、面拉、下压、锤式弯举必须有更明确的器械、身体姿态、手柄路径、终点位置判据。
- 卧推 vs 高位下拉：史密斯机导轨、仰卧姿态、杠铃在胸前垂直移动，要优先判卧推；不要因看到上方结构误判高位下拉。
- 推胸 vs 夹胸：没有光流时不要强行用“左右/前后光流”规则；改成根据把手初末位置、手臂是否水平内收、胸部器械形态来给候选。
- 有氧器械：跑步机、爬楼机、椭圆机要依赖踏板/扶手/履带形态，不要只看站姿和把手。
- 置信度：如果依赖的关键视觉证据缺失，应降到 0.7 以下并保留多个候选。

## Changelog

### 2026-06-25

- 新建 `graph_workflow_validation/` 作为独立验证目录。
- 新增 `analyze_graph_actions.py`，支持读取 `graph/*/*.jpg` 并通过项目现有 Gemini/nextrouter API 跑动作识别。
- 新增 `full-pipeline` prompt 模式：注入 `recognizer.py` 当前 Phase 2 动态 prompt 构造源码。
- 新增 `yaml-only` prompt 模式：只使用 `phase2_exercise_recognize_v9.yaml`。
- 新增 `build_ground_truth_alignment.py`，从 `shared/*/ground_truth.json` 抽取 `type=exercise` 标签并对齐到 `graph/<folder>/动作N.jpg`。
- 根据用户人工审阅新增 `apply_manual_ground_truth_corrections.py`，输出修正后的 graph-level groundtruth。
- 用户澄清“没提到的动作沿用原 groundtruth”，脚本按该规则修正。
- 用户澄清 `腿-张开/动作6`、`腿-张开/动作8` 保留为 `未知动作`，不是删除。
- 生成 full-pipeline 对比结果：63 个评估项，24 match，39 mismatch。
- 生成 yaml-only 对比结果：63 个评估项，23 match，39 mismatch，1 API error。
- 新增 `image-main-focus` prompt 模式：跳过当前 graph 输入不具备的光流/IMU/Phase1硬约束，保留图片识别与后处理核心输出。
- 用 `image-main-focus` 只重跑 full-pipeline 的 39 个 mismatch，生成 `image_main_focus_results/`。
- 新增 `compare_predictions_to_corrected_gt.py`，支持任意预测 JSON 和 corrected groundtruth 的归一化比较。
- 生成 image-main-focus 对比结果：39 个原错例中 6 match，33 mismatch，0 API error。
- 形成当前结论：本轮变好主要来自跳过不适用的光流/IMU/Phase1硬约束，不是去掉易混淆动作；易混淆动作仍应保留为候选和置信度校准机制。
