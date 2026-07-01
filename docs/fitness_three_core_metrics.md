# 健身动作识别三类核心评估指标方案

## 1. 目标

本方案只关注三个最终问题：

1. **动作识别是否准确？**
2. **组别和个数是否准确？**
3. **动作识别 + 组别个数的综合结果是否准确？**

对应推荐三个主指标：

| 编号 | 指标名称 | 推荐指标名 | 回答的问题 |
|---|---|---|---|
| 1 | 动作识别准确指标 | `Action_F1` | 预测动作是否识别正确 |
| 2 | 组别个数准确指标 | `SetRep_Accuracy@1` | 预测组数和次数是否准确 |
| 3 | 综合评估指标 | `Joint_Log_F1@1` | 一条训练记录是否整体正确 |

其中 `@1` 表示次数允许误差不超过 1 次；如果业务要求完全严格，可以同时输出 `@0`，即次数必须完全一致。

---

## 2. 输入数据与字段含义

### 2.1 预测结果：`exercise_result`

每个视频的动作识别结果来自：

```text
exercise_result.results[*]
```

关键字段：

| 字段 | 含义 | 用途 |
|---|---|---|
| `startTime` / `endTime` | 当前预测运动段的起止时间，单位秒 | 与 GT 做时间匹配 |
| `result.exercise` | 预测动作中文名 | 动作展示、文本兜底匹配 |
| `result.exercise_id` | 预测动作标准 ID | 动作准确率主判断字段 |
| `result.total_sets` | 预测总组数 | 组数评估 |
| `result.total_reps` | 预测总次数 | 次数评估 |
| `result.sets[*].reps` | 每组预测次数 | 当 `total_reps` 缺失时用于求和 |
| `result.sets[*].start_time/end_time` | 预测每组起止时间 | 可作为更精细的时间匹配依据 |

推荐取值规则：

```text
pred_action_id = result.exercise_id
pred_action_name = result.exercise
pred_sets = result.total_sets if exists else len(result.sets)
pred_reps = result.total_reps if exists else sum(result.sets[*].reps)
pred_window = [startTime, endTime)
```

如果 `result.sets` 中有更精细的起止时间，也可以使用：

```text
pred_window = [min(result.sets[*].start_time), max(result.sets[*].end_time))
```

但需要在所有样本中保持同一规则。

### 2.2 标注结果：`ground_truth`

每个视频的人工标注来自：

```text
ground_truth[*]
```

只评估：

```text
type = "exercise"
```

关键字段：

| 字段 | 含义 | 用途 |
|---|---|---|
| `start` / `end` | GT 动作起止时间，单位秒 | 与预测结果做时间匹配 |
| `label` | GT 动作名称 | 动作准确率判断 |
| `reps` | GT 次数，可选 | 次数评估 |

推荐取值规则：

```text
gt_action_name = label
gt_window = [start, end)
gt_sets = 1, unless GT has explicit set field
gt_reps = int(reps), if reps exists
```

如果后续 GT 中出现显式组字段，例如 `set_id`、`sets`、`round`，则优先使用显式组字段；否则每个连续 `exercise` 区间默认视为 1 组。

### 2.3 `period_result` 的作用

`period_result` 用于诊断阶段一的运动/休息切分质量，但这三个核心指标主要基于 `exercise_result` 和 `ground_truth` 计算。

如果 `exercise_result` 依赖 `period_result` 的运动段输入，那么阶段一漏检会自然体现为：

```text
GT 动作没有匹配到预测动作
```

从而影响 `Action_F1`、`SetRep_Accuracy@1` 和 `Joint_Log_F1@1`。

---

## 3. 评估前置步骤

### 3.1 时间统一

所有时间统一为秒，并统一采用半开区间：

```text
[start, end)
```

时长计算：

```text
duration = end - start
```

### 3.2 动作名称归一化

不要直接用中文文本做严格匹配，因为同一个动作可能有不同表达方式。

例如：

| 预测表达 | GT 表达 | 是否应视为同一动作 |
|---|---|---|
| 跑步机 | 跑步 | 是 |
| 史密斯深蹲 | 史密斯机深蹲 | 是 |
| 悬垂举腿 | 悬垂举腿 | 是 |

推荐建立动作 ontology：

```text
canonical_action_id = normalize(exercise_id or exercise_name)
```

判断动作是否正确时，比较归一化后的 `canonical_action_id`。

### 3.3 预测事件与 GT 事件匹配

设：

```text
G = 所有 GT exercise 事件
P = 所有预测 exercise 事件
```

对每个预测事件 `p` 和 GT 事件 `g` 计算时间重叠：

```text
overlap(p,g) = max(0, min(p.end, g.end) - max(p.start, g.start))

IoU(p,g) = overlap(p,g) / (duration(p) + duration(g) - overlap(p,g))

GT_Coverage(p,g) = overlap(p,g) / duration(g)

Pred_Purity(p,g) = overlap(p,g) / duration(p)
```

推荐匹配规则：

```text
候选匹配条件：IoU >= 0.3 OR GT_Coverage >= 0.5
匹配方式：按 IoU 从高到低做一对一匹配
```

如果业务更关注完整覆盖 GT 动作，可以提高 `GT_Coverage` 阈值；如果动作时间边界经常有误差，可以适当降低 IoU 阈值。

---

# 指标 1：动作识别是否准确

## 4. 动作识别准确指标：`Action_F1`

### 4.1 单条匹配判断

对于一组已匹配的预测事件 `p` 和 GT 事件 `g`：

```text
action_ok(p,g) = 1 if canonical_action_id(p) == canonical_action_id(g) else 0
```

### 4.2 统计量定义

```text
Action_TP = 匹配成功且动作正确的预测事件数

Action_FP = 未匹配预测事件数 + 匹配成功但动作错误的预测事件数

Action_FN = 未匹配 GT 事件数 + 匹配成功但动作错误的 GT 事件数
```

说明：

```text
匹配成功但动作错误
```

需要同时记作一次 `FP` 和一次 `FN`，因为模型既多预测了一个错误动作，也漏掉了一个正确动作。

### 4.3 指标公式

```text
Action_Precision = Action_TP / (Action_TP + Action_FP)

Action_Recall = Action_TP / (Action_TP + Action_FN)

Action_F1 = 2 * Action_Precision * Action_Recall / (Action_Precision + Action_Recall)
```

### 4.4 推荐主指标

```text
动作识别是否准确 = Action_F1
```

原因：

- 能惩罚动作错识别；
- 能惩罚漏识别；
- 能惩罚多识别；
- 适合跨视频、跨版本做整体比较。

### 4.5 建议同时输出的辅助字段

| 字段 | 含义 |
|---|---|
| `action_tp` | 动作识别正确数量 |
| `action_fp` | 多识别或错识别数量 |
| `action_fn` | 漏识别或错识别数量 |
| `action_precision` | 预测出来的动作有多少是对的 |
| `action_recall` | GT 动作有多少被正确识别出来 |
| `action_f1` | 动作识别综合准确指标 |

---

# 指标 2：组别和个数是否准确

## 5. 组别个数准确指标：`SetRep_Accuracy@k`

这里的“组别和个数”包含两个部分：

```text
组别 = total_sets
个数 = total_reps / reps
```

其中：

- 组数必须完全一致；
- 次数可以设置容忍阈值 `k`；
- 推荐主指标使用 `k = 1`，即 `SetRep_Accuracy@1`；
- 严格指标使用 `k = 0`，即 `SetRep_Accuracy@0`。

## 5.1 单条 GT 的组数判断

对于 GT 事件 `g` 和其匹配的预测事件 `p`：

```text
set_ok(p,g) = 1 if pred_sets(p) == gt_sets(g) else 0
```

GT 组数取值规则：

```text
若 GT 有显式组数字段：gt_sets = GT 显式组数
否则：gt_sets = 1
```

预测组数取值规则：

```text
若 result.total_sets 存在：pred_sets = result.total_sets
否则：pred_sets = len(result.sets)
```

## 5.2 单条 GT 的次数判断

若 GT 有 `reps`：

```text
rep_ok@k(p,g) = 1 if abs(pred_reps(p) - gt_reps(g)) <= k else 0
```

若 GT 没有 `reps`，例如跑步、椭圆机等有氧运动：

```text
rep_ok@k(p,g) = 1
```

即不评估次数，只评估组数。

预测次数取值规则：

```text
若 result.total_reps 存在：pred_reps = result.total_reps
否则：pred_reps = sum(result.sets[*].reps)
```

## 5.3 单条 GT 的组别个数是否正确

如果 GT 事件 `g` 没有匹配到任何预测事件：

```text
count_ok@k(g) = 0
```

如果 GT 事件 `g` 匹配到预测事件 `p`：

```text
count_ok@k(g) = set_ok(p,g) AND rep_ok@k(p,g)
```

注意：

```text
count_ok@k
```

可以独立于动作是否正确来计算，用于单独评估计数能力；但最终综合指标会要求动作和计数都正确。

## 5.4 指标公式

```text
SetRep_Accuracy@k = sum(count_ok@k(g)) / number_of_GT_exercise_events
```

推荐主指标：

```text
组别个数是否准确 = SetRep_Accuracy@1
```

严格指标：

```text
Strict_SetRep_Accuracy = SetRep_Accuracy@0
```

## 5.5 建议同时输出的辅助指标

| 指标 | 公式 | 含义 |
|---|---|---|
| `Set_Exact_Accuracy` | `set_ok` 的平均值 | 组数完全正确比例 |
| `Rep_Acc@0` | `abs(pred_reps - gt_reps) <= 0` 的比例 | 次数完全正确比例 |
| `Rep_Acc@1` | `abs(pred_reps - gt_reps) <= 1` 的比例 | 次数允许 1 次误差的正确比例 |
| `Rep_MAE` | `mean(abs(pred_reps - gt_reps))` | 平均次数误差 |
| `Total_Rep_Error` | `sum(pred_reps) - sum(gt_reps)` | 总次数偏多或偏少 |

---

# 指标 3：综合评估指标

## 6. 综合指标：`Joint_Log_F1@k`

综合指标用于判断一条训练记录是否整体正确。

一条 GT 训练记录只有同时满足以下条件，才算综合正确：

```text
1. 匹配到预测事件；
2. 动作识别正确；
3. 组数正确；
4. 若 GT 有 reps，则次数误差 <= k。
```

推荐使用：

```text
Joint_Log_F1@1
```

严格版本：

```text
Joint_Log_F1@0
```

## 6.1 单条综合正确判断

对于 GT 事件 `g` 和匹配预测事件 `p`：

```text
joint_ok@k(p,g) = action_ok(p,g) AND set_ok(p,g) AND rep_ok@k(p,g)
```

如果 GT 事件没有匹配到预测事件：

```text
joint_ok@k(g) = 0
```

## 6.2 综合 TP / FP / FN

```text
Joint_TP@k = 匹配成功，且 action_ok = 1，set_ok = 1，rep_ok@k = 1 的事件数

Joint_FP@k = 未匹配预测事件数 + 匹配成功但 joint_ok@k = 0 的预测事件数

Joint_FN@k = 未匹配 GT 事件数 + 匹配成功但 joint_ok@k = 0 的 GT 事件数
```

## 6.3 综合指标公式

```text
Joint_Precision@k = Joint_TP@k / (Joint_TP@k + Joint_FP@k)

Joint_Recall@k = Joint_TP@k / (Joint_TP@k + Joint_FN@k)

Joint_Log_F1@k = 2 * Joint_Precision@k * Joint_Recall@k / (Joint_Precision@k + Joint_Recall@k)
```

## 6.4 推荐主指标

```text
综合评估指标 = Joint_Log_F1@1
```

含义：

```text
模型最终生成的训练日志中，有多少动作记录在动作名称、组数、次数三个层面都可接受。
```

## 6.5 可选的更直观版本：`Joint_Log_Accuracy@k`

如果只想从 GT 角度看“每条 GT 是否被完整识别对”，可以输出：

```text
Joint_Log_Accuracy@k = sum(joint_ok@k(g)) / number_of_GT_exercise_events
```

区别：

| 指标 | 是否惩罚漏识别 | 是否惩罚多识别 | 推荐用途 |
|---|---:|---:|---|
| `Joint_Log_Accuracy@k` | 是 | 否 | 简单业务报表 |
| `Joint_Log_F1@k` | 是 | 是 | 版本对比主指标 |

因此主指标推荐使用：

```text
Joint_Log_F1@1
```

---

## 7. 三个指标的最终定义汇总

| 指标 | 计算对象 | 正确条件 | 推荐主指标 |
|---|---|---|---|
| 动作识别是否准确 | 预测动作事件 vs GT 动作事件 | 时间匹配成功，且归一化动作 ID 一致 | `Action_F1` |
| 组别个数是否准确 | 已时间匹配的事件 | 组数一致，且 reps 误差 <= 1 | `SetRep_Accuracy@1` |
| 综合评估指标 | 完整训练记录 | 动作正确，组数正确，reps 误差 <= 1 | `Joint_Log_F1@1` |

严格版本：

| 宽松 / 主指标 | 严格指标 | 差异 |
|---|---|---|
| `SetRep_Accuracy@1` | `SetRep_Accuracy@0` | 次数是否允许 1 次误差 |
| `Joint_Log_F1@1` | `Joint_Log_F1@0` | 综合正确是否允许 1 次 reps 误差 |

---

## 8. 全样本聚合方式

### 8.1 Micro 聚合，推荐用于版本主评分

把所有视频的 TP / FP / FN 汇总后再计算指标。

```text
Micro_Action_F1 = F1(sum(Action_TP), sum(Action_FP), sum(Action_FN))

Micro_Joint_Log_F1@1 = F1(sum(Joint_TP@1), sum(Joint_FP@1), sum(Joint_FN@1))

Micro_SetRep_Accuracy@1 = sum(count_ok@1) / sum(number_of_GT_exercise_events)
```

优点：

```text
每条动作记录权重相同，适合衡量整体业务准确率。
```

### 8.2 Macro 聚合，推荐用于观察视频间稳定性

先计算每个视频的指标，再对视频求平均。

```text
Macro_Action_F1 = mean(video_action_f1)

Macro_SetRep_Accuracy@1 = mean(video_setrep_accuracy@1)

Macro_Joint_Log_F1@1 = mean(video_joint_log_f1@1)
```

优点：

```text
每个视频权重相同，能发现模型是否只在部分长视频上表现好。
```

推荐最终报表同时输出：

```text
Micro 指标作为主结果
Macro 指标作为稳定性参考
```

---

## 9. 推荐输出报表格式

### 9.1 全量样本汇总表

| 指标类别 | 指标名 | 数值 | 说明 |
|---|---|---:|---|
| 动作识别 | `Micro_Action_F1` |  | 主指标，动作是否识别准确 |
| 组别个数 | `Micro_SetRep_Accuracy@1` |  | 主指标，组数正确且 reps 误差 <= 1 |
| 综合评估 | `Micro_Joint_Log_F1@1` |  | 主指标，动作、组数、次数整体正确 |
| 动作识别 | `Macro_Action_F1` |  | 视频级平均动作准确性 |
| 组别个数 | `Macro_SetRep_Accuracy@1` |  | 视频级平均计数准确性 |
| 综合评估 | `Macro_Joint_Log_F1@1` |  | 视频级平均整体准确性 |

### 9.2 动作级明细表

| video_id | gt_action | pred_action | time_iou | action_ok | gt_sets | pred_sets | gt_reps | pred_reps | set_ok | rep_ok@1 | count_ok@1 | joint_ok@1 | error_type |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |

### 9.3 错误类型建议

| 错误类型 | 判断规则 | 说明 |
|---|---|---|
| `missed_action` | GT 没有匹配预测 | 漏识别动作 |
| `extra_action` | 预测没有匹配 GT | 多识别动作 |
| `wrong_action` | 时间匹配成功但动作 ID 不一致 | 动作类别识别错 |
| `wrong_set_count` | 动作匹配但组数不一致 | 组数错误 |
| `rep_under_count` | `pred_reps < gt_reps - k` | 次数少数 |
| `rep_over_count` | `pred_reps > gt_reps + k` | 次数多数 |
| `fully_correct` | `joint_ok@k = 1` | 完整正确 |

---

## 10. 计算流程伪代码

```python
for video in dataset:
    gt_events = [x for x in ground_truth if x["type"] == "exercise"]
    pred_events = exercise_result["results"]

    normalize gt_events:
        gt.action_id = normalize_action(gt.label)
        gt.sets = gt.sets if exists else 1
        gt.reps = int(gt.reps) if exists else None
        gt.window = [gt.start, gt.end)

    normalize pred_events:
        pred.action_id = normalize_action(pred.result.exercise_id or pred.result.exercise)
        pred.sets = pred.result.total_sets or len(pred.result.sets)
        pred.reps = pred.result.total_reps or sum(set.reps for set in pred.result.sets)
        pred.window = [pred.startTime, pred.endTime)

    matched_pairs = bipartite_match_by_time_iou(
        gt_events,
        pred_events,
        candidate_rule = "IoU >= 0.3 OR GT_Coverage >= 0.5"
    )

    for each matched pair (g, p):
        action_ok = g.action_id == p.action_id
        set_ok = g.sets == p.sets

        if g.reps is None:
            rep_ok_0 = True
            rep_ok_1 = True
        else:
            rep_ok_0 = abs(p.reps - g.reps) <= 0
            rep_ok_1 = abs(p.reps - g.reps) <= 1

        count_ok_1 = set_ok and rep_ok_1
        joint_ok_1 = action_ok and count_ok_1

    compute Action_TP / FP / FN
    compute SetRep_Accuracy@1
    compute Joint_TP@1 / FP@1 / FN@1
    compute Joint_Log_F1@1
```

---

## 11. 推荐最终结论格式

每次评估一个模型版本时，最终只需要重点汇报三行：

| 评估问题 | 主指标 | 结果 | 结论 |
|---|---|---:|---|
| 动作识别是否准确？ | `Action_F1` |  | 动作分类能力 |
| 组别个数是否准确？ | `SetRep_Accuracy@1` |  | 组数和次数计数能力 |
| 整体训练日志是否准确？ | `Joint_Log_F1@1` |  | 端到端可用性 |

其中：

```text
Action_F1 高，SetRep_Accuracy@1 低
=> 动作识别对，但计数能力差。

Action_F1 低，SetRep_Accuracy@1 高
=> 时间匹配到的动作计数还可以，但动作分类能力差。

Action_F1 高，SetRep_Accuracy@1 高，Joint_Log_F1@1 低
=> 可能存在多识别、漏识别，或动作正确与计数正确没有出现在同一条记录上。

Joint_Log_F1@1 高
=> 动作、组数、次数端到端整体表现好。
```

---

## 12. 默认参数建议

| 参数 | 默认值 | 说明 |
|---|---:|---|
| 时间匹配 IoU 阈值 | `0.3` | 允许边界有一定误差 |
| GT 覆盖率阈值 | `0.5` | 防止短预测片段误匹配长 GT |
| reps 容忍阈值 | `k = 1` | 主指标允许 1 次误差 |
| 严格 reps 阈值 | `k = 0` | 用于严格版本对比 |
| 主动作指标 | `Action_F1` | 同时惩罚多识别和漏识别 |
| 主计数指标 | `SetRep_Accuracy@1` | 组数完全一致，次数误差不超过 1 |
| 主综合指标 | `Joint_Log_F1@1` | 动作、组数、次数同时正确 |
