# HEI-2020 指标面板 MVP 设计

> 当前版本：v0.2  
> 日期：2026-06-10  
> 状态：MVP 已落地，先定义最小可用 artifact 与工程边界  
> 相关模块：`nutrition/input_adapter.py`、`nutrition/linker.py`、`nutrition/rag_agent.py`、`nutrition/estimate.py`、Workbench 营养页  
> 官方参考：NCI Healthy Eating Index 说明与 scoring standards  
> - https://epi.grants.cancer.gov/hei/  
> - https://epi.grants.cancer.gov/hei/developing.html  
> - https://epi.grants.cancer.gov/hei/calculating-hei-scores.html  
> - https://epi.grants.cancer.gov/hei/hei-scoring-method.html

## 1. 一句话目标

做一个 **HEI-2020 风格的 13 项饮食质量指标面板**。

第一版不承诺“官方 HEI 分数”，而是给用户和内部评测一个可解释的结构：

```text
这一餐/这一天在水果、蔬菜、全谷物、乳制品、蛋白、钠、添加糖、饱和脂肪等 13 个维度上，
哪些做得好，哪些拉低质量，哪些因为数据不足只能低置信显示。
```

核心原则：

```text
先能看懂，再追求准。
先显示 component 和证据，再显示总分。
先做 daily aggregation，再把 single meal 当成贡献解释。
```

## 2. 为什么不能直接上线“HEI 官方分”

HEI-2020 的 13 项不是只靠热量和 P/F/C 就能算。

它需要几类额外信息：

- 食物组等价量：水果 cup eq、蔬菜 cup eq、全谷物 oz eq、乳制品 cup eq、蛋白食物 oz eq。
- 钠、添加糖、饱和脂肪、MUFA、PUFA。
- 复合食物拆解：披萨、汉堡、盖饭、奶茶、沙拉、套餐需要拆到谷物、蛋白、蔬菜、乳制品、糖、油脂等贡献。
- 按天或多人群饮食周期聚合更有意义；单餐 HEI 容易被餐型偏置。

所以本项目第一版应该叫：

```text
HEI-2020 Component Estimate
```

而不是：

```text
Official HEI Score
```

## 3. HEI-2020 13 项

总分 100 分，由 13 个 component 加总。

Adequacy 类是“越充足越好”；Moderation 类是“越少越好”。中间值线性给分。

| 类别 | 指标 | 满分 |
|---|---|---:|
| Adequacy | Total Fruits | 5 |
| Adequacy | Whole Fruits | 5 |
| Adequacy | Total Vegetables | 5 |
| Adequacy | Greens and Beans | 5 |
| Adequacy | Whole Grains | 10 |
| Adequacy | Dairy | 10 |
| Adequacy | Total Protein Foods | 5 |
| Adequacy | Seafood and Plant Proteins | 5 |
| Adequacy | Fatty Acids | 10 |
| Moderation | Refined Grains | 10 |
| Moderation | Sodium | 10 |
| Moderation | Added Sugars | 10 |
| Moderation | Saturated Fats | 10 |

MVP 页面不需要把所有计算标准直接露给用户。用户更需要看到：

```text
指标名
当前状态
大致得分
为什么这样判
置信度
缺了什么数据
```

## 4. MVP 范围

### 4.1 MVP 要做

第一版只做 13 项面板，不把它接入主热量评分。

输出每个 component：

- `score_estimate`：估计分数。
- `max_score`：该项满分。
- `status`：`good` / `watch` / `low` / `unknown`。
- `evidence`：用到的食物、BOM、link、营养字段。
- `confidence`：`high` / `medium` / `low`。
- `missing_data`：缺哪些字段。
- `notes`：一句人能读懂的解释。

页面展示：

- 13 项列表。
- 按 `good / watch / low / unknown` 分组或排序。
- 每项显示“贡献/风险”的一句话。
- 允许点开看证据。

### 4.2 MVP 不做

第一版暂时不做：

- 不给“官方 HEI 总分”背书。
- 不声称医学或营养诊断。
- 不做长期 dietary recall 的科研级统计。
- 不强行给所有 unknown component 估分。
- 不把 HEI 分数写入 calorie benchmark 主指标。

## 5. 产品呈现建议

### 5.1 页面名称

建议叫：

```text
饮食质量 HEI-2020
```

小字说明：

```text
基于 HEI-2020 的 13 项指标做估计；部分指标依赖食物组和营养素映射，低置信时仅作参考。
```

### 5.2 单餐页

单餐页不要强调总分。

更适合展示：

```text
本餐贡献
```

例子：

- `Total Vegetables`: 有蔬菜，贡献中等。
- `Whole Grains`: 未识别到全谷物。
- `Sodium`: 可能偏高，因为包含汤底/酱汁/加工肉，但当前钠数据低置信。
- `Added Sugars`: 饮料或甜品缺少品牌 label，暂不确定。

### 5.3 每日页

每日页可以展示估计总分，但要带标签：

```text
HEI-style score estimate
```

原因是 HEI 本身更适合按一天或多天饮食评估，不适合单餐孤立评价。

## 6. 数据来源分层

MVP 的关键不是一次把所有 component 算准，而是把证据分层。

### 6.1 已有输入

我们现在已有：

- 感知层输出：dish、BOM、brand signals、package signals、portion evidence。
- 营养估算输出：kcal range、macro pct、dish reasoning。
- RAG/link trace：raw name、canonical name、KB candidates、selected、warnings。
- N5K：dish/ingredient-level kcal、mass、P/F/C，用于开发和校验，不是 HEI 主库。

### 6.2 还缺的输入

HEI 真正需要的是：

- Food pattern equivalents：水果、蔬菜、全谷物、乳制品等 cup/oz equivalents。
- Sodium。
- Added sugars。
- Saturated fat。
- MUFA / PUFA。
- Composite dish disaggregation。

这些不能只靠当前 calorie estimate 推出来。

### 6.3 MVP 的数据优先级

每个 component 按下面顺序取证据：

1. **明确 KB 映射**：食物已 link 到可信 KB，并且 KB 有对应 HEI 所需字段。
2. **明确类别规则**：例如 `米饭`、`苹果`、`牛奶`、`鸡蛋` 这类稳定 food group。
3. **复合菜近似拆分**：例如 `汉堡`、`披萨`、`盖饭`，用 dish template 给低到中置信估计。
4. **模型解释证据**：只作为 low confidence，不自动进入总分。
5. **unknown**：缺数据，不猜。

## 7. 输出契约

已新增 artifact：

```text
output/runs/<run_id>/hei_2020/<nutrition_subdir>/<meal>.json
```

结构示意：

```json
{
  "schema": "hei_2020_component_estimate.v1",
  "run_id": "20260609-v7-short-crops",
  "nutrition_subdir": "nutrition_v3_rag_strong",
  "meal": "三明治-孙一丹",
  "scope": "meal",
  "energy_kcal": {
    "value": 520,
    "source": "<selected_nutrition_subdir>.kcal_mid",
    "confidence": "medium"
  },
  "score": {
    "mode": "component_estimate",
    "total_estimate": 54,
    "max_score": 100,
    "confidence": "low",
    "show_total_to_user": false
  },
  "components": [
    {
      "id": "total_fruits",
      "name": "Total Fruits",
      "group": "adequacy",
      "score_estimate": 0,
      "max_score": 5,
      "status": "low",
      "confidence": "medium",
      "evidence": [],
      "missing_data": [],
      "notes": "本餐未识别到水果。"
    }
  ],
  "warnings": [
    "Added sugars 缺少品牌饮料 label 或配料表，暂不计入高置信总分。"
  ],
  "created_at": "2026-06-10 12:00:00"
}
```

注意：

- `total_estimate` 第一版可以保留给内部，不默认给用户展示。
- 前端主要读 `components[]`。
- `missing_data` 是产品可解释性的关键，不能省。

## 8. 工程模块

### 8.1 新增 `nutrition/hei.py`

职责：

```text
读取 nutrition output + nutrition_links
生成 hei_2020 component artifact
```

它不调用大模型。

第一版以规则和已有 linker 结果为主，保证可重复。

### 8.2 新增 `data/nutrition_kb/hei_food_groups.json`

职责：

```text
把常见 canonical food 映射到 HEI food group。
```

例子：

规则表以 pattern + component hit 表达，例如 `苹果 -> total_fruits / whole_fruits`，
`米饭 -> refined_grains watch`，`三文鱼 -> total_protein_foods / seafood_and_plant_proteins`。

第一版不需要很大。先覆盖我们 benchmark 和 v7 结果里的高频食物。

### 8.3 可选新增 `nutrition/hei_templates.yaml`

用于复合菜低置信拆分。

例子：

```yaml
汉堡:
  refined_grains: medium
  total_protein_foods: medium
  saturated_fats: watch
  sodium: watch
披萨:
  refined_grains: medium
  dairy: medium
  saturated_fats: watch
  sodium: watch
奶茶:
  dairy: low
  added_sugars: watch
```

这层只用于提示风险，不应该直接当高置信分数。

### 8.4 当前工程接入

当前 MVP 已落地为：

- `nutrition/hei.py`：读取指定 `nutrition_subdir`，生成 HEI side-car artifact。
- `data/nutrition_kb/hei_food_groups.json`：小规则表，覆盖当前 benchmark/业务餐高频食物。
- Workbench 营养页：新增 `HEI-2020` tab、单餐 HEI 预览、`生成HEI` 按钮。
- 后端状态：`_nutrition_workbench_state()` 返回 `summary.hei_summary` 和 `meal.hei`。
- 营养 job：跑完 estimate/AB 后 best-effort 生成 HEI，不影响热量评测成败。

注意：当前 `nutrition_estimate@v4` 已作为 active prompt，但历史目录名仍可能是
`nutrition_v3` / `nutrition_v3_rag_evidence` / `nutrition_v3_rag_strong`。
HEI 不判断 prompt 版本，只读取用户当前选择的 `nutrition_subdir`。

## 9. Scoring MVP

为了可读性，第一版 scoring 分两层。

### 9.1 展示层状态

先给状态，不急着给精确小数：

```text
good    证据足，接近或达到目标
watch   有贡献/风险，但不足或偏高
low     明确缺失或明显不达标
unknown 数据不足，不判断
```

这能让产品先有可解释体验。

### 9.2 内部估分

内部可以按官方 component max score 做线性估计。

但每项要带 confidence：

```text
high    有明确等价量/营养素字段
medium  有类别映射 + 合理份量估计
low     只有模型或模板风险判断
unknown 不进入总分
```

第一版总分规则：

```text
只有 high/medium component 进入 internal total_estimate。
low/unknown 不强行补齐。
用户端默认不展示总分。
```

## 10. 与现有 RAG 的关系

HEI MVP 不替代 agentic RAG。

它消费 RAG/linker 的结果：

```text
BOM raw item
-> deterministic linker / agentic RAG
-> selected canonical food or candidate_only
-> HEI food group mapper
-> component evidence
```

如果 RAG 结果是：

- `safe_selected`：可以进入 medium/high 证据。
- `candidate_only`：最多进入 low/unknown。
- `needs_review`：前端显示“待确认”，不进总分。
- `rejected`：不进入 HEI。

## 11. Benchmark 方式

第一版不评“HEI 总分误差”，因为我们没有 HEI gold。

先评三类工程指标：

1. Coverage

```text
13 项里有多少项能给出非 unknown 状态？
```

2. Evidence quality

```text
每项有多少 evidence 来自 safe_selected link？
多少来自 template？
多少来自 model-only？
```

3. Human review usefulness

```text
人工看 20 餐，判断每个 component 的 good/watch/low 是否方向正确。
```

N5K 可以用来校验：

- kcal / mass / P/F/C 是否被正确读入。
- ingredient-level 食材是否能映射到 food group。

但 N5K 不能直接提供完整 HEI gold，因为它缺 food pattern equivalents、added sugars、fatty acid 细项等。

## 12. 迭代路线

### P0：只展示 13 项框架

目标：

- Workbench 能看到 13 个 HEI component。
- 每项先显示 `unknown` 或基于少量规则的状态。
- 不显示总分。

产物：

- `nutrition/hei.py`
- `output/runs/<run_id>/hei_2020/<nutrition_subdir>/<meal>.json`
- Workbench `HEI-2020` tab。

### P1：高频食物组映射

目标：

- 覆盖 v7 short+crops run 里的高频 BOM。
- 支持水果、蔬菜、谷物、蛋白、乳制品的基础 component。

产物：

- `data/nutrition_kb/hei_food_groups.json`
- coverage report。

### P2：Moderation 风险提示

目标：

- 对 sodium、added sugars、saturated fats 给风险提示。
- 高盐汤底、加工肉、甜饮、甜品、奶茶、酱汁先以 `watch/low confidence` 展示。

产物：

- `hei_templates` 或 FPED/食物组等价量表。
- 前端风险 badge。

### P3：接入更可信外部库

目标：

- 引入 FNDDS/FPED 或等价 food-pattern table。
- 从“方向判断”升级到“等价量估计”。

这一步之后，才适合讨论把 total estimate 对用户展示。

## 13. 当前推荐决策

建议立刻做 P0 + P1。

原因：

- 产品能先看到 13 项结构。
- 工程成本低，不影响现有 calorie pipeline。
- 能复用现有 RAG/linker trace。
- 不会过早承诺官方 HEI 精度。

第一版验收标准：

- 任意一个 nutrition run，可以生成 `hei_2020/<nutrition_subdir>/<meal>.json`。
- Workbench 单餐页能看到 13 项。
- 每项都有 `status / confidence / notes`。
- unknown 明确显示原因，而不是空白。
- 不改写当前 nutrition output（例如 `nutrition_v3` / RAG 子目录），不影响现有 benchmark。
