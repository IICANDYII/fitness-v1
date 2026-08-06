# Diet Recognition 研发需求

# Relty Diet Recognition Structured Output v2

## 文档目的

本文档用于定义 Diet Agent 在食物识别阶段需要输出的结构化营养字段。

当前 Diet Agent 已经能够识别：

```Plain Text
食物名称
每餐热量范围
每餐热量中位数
每餐宏量营养比例
全天热量汇总
全天宏量营养比例
```

但这些信息还不足以支撑 Diet Balance 的稳定计算。

Diet Balance 的核心不是简单判断：

```Plain Text
用户吃了什么食物
```

而是需要将用户真实吃下去的一组食物转化为可计算的 food pattern components。

因此，本阶段研发目标不是重新设计 Diet Balance 公式，而是补齐 Diet Balance 所需的结构化输入。

---

## 当前问题

当前 nutrition recognition 输出仍主要停留在：

```Plain Text
food name
energy estimate
macro estimate
```

这可以支持：

```Plain Text
AMDR_Fit
蛋白质摄入量初步反推
每日能量摄入解释
```

但不能稳定支持：

```Plain Text
HEI-2020 component scoring
Food group density calculation
Fiber adequacy estimation
Whole grain / refined grain gap analysis
Fruit / dairy / vegetable component calculation
```

原因是 HEI\-2020 需要的不是食物名称本身，而是：

```Plain Text
食物组
份量
食物组等价量
营养成分估计
置信度
证据来源
```

---

## 本阶段需要新增的识别能力

本阶段优先补充以下字段：

```Plain Text
1. Food group serving
2. Whole grain / refined grain 区分
3. Dairy 识别
4. Whole fruit / fruit juice 区分
5. Fiber 估算
6. Confidence 与 evidence
```

暂时不处理：

```Plain Text
sodium
saturated fat
added sugar
meal timing
fatty acid quality
```

这些指标理论上重要，但当前识别难度较高，容易造成不稳定判断。本阶段先不进入结构化输出要求。

---

## 核心原则

### 1\. 不要只输出 food name

Diet Agent 不能只识别：

```Plain Text
这是米饭
这是鸡肉
这是沙拉
```

而是需要进一步输出：

```Plain Text
米饭 → refined grains
鸡肉 → total protein foods
沙拉 → vegetables
```

并尽量估算对应的 serving amount。

---

### 2\. 全天记录完整时，缺失应视为 0，而不是 unknown

如果当天三餐记录完整，并且没有识别到水果，则应输出：

```Plain Text
total_fruits_cup = 0
whole_fruits_cup = 0
```

而不是不输出水果字段。

同理：

```Plain Text
没有奶制品 → dairy_cup = 0
没有全谷物 → whole_grains_oz = 0
```

不输出字段只适用于数据本身不完整或识别失败的情况。

---

### 3\. 不确定时输出 range \+ confidence

食物识别天然存在不确定性。

因此，本阶段不要求所有估算都是精确值。

但每个结构化字段都应尽量输出：

```Plain Text
value
value_range
value_mid
confidence
evidence
```

如果无法确定，应降低 confidence，而不是删除字段。

---

## 目标 JSON 格式

当前 JSON 保持原有结构：

```Plain Text
schema
generated_at
source_dir
model
vision_mode
users
meals
daily_total
```

在每餐下新增：

```Plain Text
food_group_estimates
```

在 daily\_total 下新增：

```Plain Text
food_group_totals
coverage_flags
```

---

## JSON 示例

```JSON
{
  "schema": "batch_nutrition_results.v2",
  "generated_at": "2026-06-12 17:50:39",
  "source_dir": "/mnt/nas-diet/output/diet_agent_meal_photos",
  "model": "gemini-3.1-flash-lite-preview",
  "vision_mode": "crops_enhanced",
  "users": [
    {
      "user_id": "user01-01",
      "profile": "carbohydrate-heavy day",
      "meals": [
        {
          "meal_slot": "breakfast",
          "foods": [
            "stir-fried noodles with vegetables"
          ],
          "kcal_range": [450, 850],
          "kcal_mid": 650,
          "band": "中",
          "macro_structure_pct": {
            "protein": 12,
            "fat": 35,
            "carb": 53
          },
          "food_group_estimates": {
            "total_fruits_cup": {
              "value": 0,
              "confidence": "high",
              "evidence": []
            },
            "whole_fruits_cup": {
              "value": 0,
              "confidence": "high",
              "evidence": []
            },
            "fruit_juice_cup": {
              "value": 0,
              "confidence": "high",
              "evidence": []
            },
            "total_vegetables_cup": {
              "value_range": [0.25, 0.5],
              "value_mid": 0.35,
              "confidence": "medium",
              "evidence": ["vegetables"]
            },
            "greens_and_beans_cup": {
              "value_range": [0, 0.25],
              "value_mid": 0.1,
              "confidence": "low",
              "evidence": ["vegetables"]
            },
            "whole_grains_oz": {
              "value": 0,
              "confidence": "high",
              "evidence": []
            },
            "refined_grains_oz": {
              "value_range": [2, 4],
              "value_mid": 3,
              "confidence": "medium",
              "evidence": ["noodles"]
            },
            "dairy_cup": {
              "value": 0,
              "confidence": "high",
              "evidence": []
            },
            "total_protein_foods_oz": {
              "value_range": [0.5, 1.5],
              "value_mid": 1,
              "confidence": "low",
              "evidence": []
            },
            "seafood_and_plant_proteins_oz": {
              "value": 0,
              "confidence": "high",
              "evidence": []
            },
            "fiber_g": {
              "value_range": [2, 5],
              "value_mid": 3.5,
              "confidence": "medium",
              "evidence": ["vegetables", "noodles"]
            }
          },
          "error": ""
        }
      ],
      "daily_total": {
        "available_meals": 3,
        "kcal_range": [1720, 2930],
        "kcal_mid": 2325,
        "macro_structure_pct": {
          "protein": 19.0,
          "fat": 33.0,
          "carb": 48.4
        },
        "food_group_totals": {
          "total_fruits_cup": 0,
          "whole_fruits_cup": 0,
          "fruit_juice_cup": 0,
          "total_vegetables_cup": 1.1,
          "greens_and_beans_cup": 0.2,
          "whole_grains_oz": 0,
          "refined_grains_oz": 7.5,
          "dairy_cup": 0,
          "total_protein_foods_oz": 4.5,
          "seafood_and_plant_proteins_oz": 1.5,
          "fiber_g_range": [8, 14],
          "fiber_g_mid": 11
        },
        "coverage_flags": {
          "full_day_record_complete": true,
          "missing_fruit_treated_as_zero": true,
          "missing_dairy_treated_as_zero": true,
          "missing_whole_grain_treated_as_zero": true
        }
      }
    }
  ]
}
```

---

## 具体字段说明

### Whole grain / refined grain

需要区分：

```Plain Text
whole_grains_oz
refined_grains_oz
```

默认规则：

```Plain Text
white rice
noodles
rice rolls
congee
bun
baozi
jianbing
pizza crust
burger bun
waffle
white bread
```

应进入：

```Plain Text
refined_grains_oz
```

只有明确出现：

```Plain Text
brown rice
oats
whole wheat
whole grain bread
quinoa
barley
whole grain cereal
```

才进入：

```Plain Text
whole_grains_oz
```

---

### Dairy

需要识别：

```Plain Text
milk
yogurt
cheese
dairy drink
cream
```

并输出：

```Plain Text
dairy_cup
```

注意：

```Plain Text
soy milk 不计入 dairy
没有奶制品时输出 dairy_cup = 0
```

---

### Fruit

需要区分：

```Plain Text
whole_fruits_cup
fruit_juice_cup
```

完整水果、水果块、水果切片进入：

```Plain Text
whole_fruits_cup
```

果汁进入：

```Plain Text
fruit_juice_cup
```

少量水果装饰不应直接算作完整一份水果。

例如：

```Plain Text
apple slice
```

应按少量水果估算。

---

### Fiber

Fiber 不建议直接通过关键词猜测。

Fiber 应优先从以下结构化结果推导：

```Plain Text
vegetables
greens and beans
whole fruits
whole grains
beans / legumes
nuts / seeds
```

精制主食不应被高估为高 fiber 来源。

例如：

```Plain Text
white rice
white noodles
white buns
```

不应作为主要 fiber 来源。

---

## 暂时跳过的字段

以下字段暂时不进入本阶段研发范围：

```Plain Text
sodium
saturated fat
added sugar
meal timing
fatty acid quality
```

原因是这些字段识别难度较高，需要更细的食材、调味料、加工方式、品牌或时间数据支持。

本阶段如果强行输出，容易造成低置信度判断，反而影响 Diet Balance 的稳定性。

因此，本阶段先将研发目标收敛为：

```Plain Text
food name
→ food group
→ serving amount
→ fiber estimate
→ confidence / evidence
```

---

## 本阶段完成标准

本阶段完成后，Diet Agent 每餐应至少能够输出：

```Plain Text
fruits
vegetables
grains
dairy
protein foods
fiber
```

并且能够在 daily\_total 中聚合为全天结果。

最终目标是让 Diet Balance 不再依赖简单关键词判断，而是能够基于结构化 food group estimates 进行 HEI\-2020 的初步计算。

---

## 与主 PRD 的关系

本文档是《Relty 指标计算框架》的 Diet Agent 识别输出补充文档。

[Relty 指标计算框架](https://rcnp1ka0syi7.feishu.cn/wiki/Kox8wjBtVitudvkAvpCcDbRHngc?from=from_copylink)

主 PRD 继续定义：

```Plain Text
Diet Balance 是什么
Diet Finish 是什么
Balance 与 Finish 如何区分
Diet Agent 的指标边界
```

本文档只定义：

```Plain Text
为了计算 Diet Balance，识别模型需要输出什么结构化字段。
```

因此，本文档不替代主 PRD，只作为 Diet Recognition v2 的研发输入标准。

