# Relty Diet Balance 计算说明文档

版本：v0.1  
用途：供后续 Codex / 工程实现 Diet Balance 计算逻辑使用。  
范围：仅定义 Diet Balance，不定义 Goal，不计算热量目标，不纳入 Diversity。

---

## 0. 核心口径

Diet Balance 是一个不受用户 Goal 影响的客观饮食状态指标。

它不计算：

- 总热量是否符合减脂 / 增肌目标
- 用户是否完成 calorie deficit / surplus
- 饮食丰富度 / 新鲜感 / 心情体验
- 识别置信度
- 睡前重餐

识别不到的营养项，不参与该项评分。

最终用户端只展示一个 Diet Balance 分数，不拆分展示 HEI、AMDR、RDA、Meal Timing 等子分。

---

## 1. 总公式

```text
Diet Balance =
0.50 × HEI_2020
+ 0.20 × AMDR_Fit
+ 0.20 × RDA_AI_Adequacy
+ 0.10 × Meal_Timing
```

所有输入分数范围均为：

```text
0–100
```

最终输出：

```text
Diet Balance ∈ [0, 100]
```

---

## 2. 四个组成项的职责

### 2.1 HEI-2020：饮食结构是否健康

HEI-2020，全称 Healthy Eating Index 2020，是 USDA 用来衡量饮食模式是否符合美国膳食指南的指标。

在 Diet Balance 中，HEI-2020 负责判断：

```text
用户吃的食物组结构是否接近健康膳食模式。
```

通俗解释：

```text
HEI 看的是：你这一整天吃的东西，整体结构像不像一套健康饮食。
```

它主要覆盖：

- 水果
- 蔬菜
- 深绿色蔬菜和豆类
- 全谷物
- 乳制品
- 总蛋白质食物
- 海鲜和植物蛋白
- 脂肪酸结构
- 精制谷物
- 钠
- 添加糖
- 饱和脂肪

HEI 使用 density approach。也就是说，很多食物组项目不是直接看绝对摄入量，而是换算成每 1000 kcal 中含有多少对应食物组。

这样做的意义是：

```text
把“饮食质量”与“吃了多少总量”分开。
```

例子：

```text
用户 A：
总摄入 3000 kcal，蔬菜 3 cups
=> 每 1000 kcal 蔬菜 = 1 cup

用户 B：
总摄入 1500 kcal，蔬菜 2 cups
=> 每 1000 kcal 蔬菜 = 1.33 cups
```

虽然 A 的蔬菜绝对量更多，但 B 的饮食结构中蔬菜密度更高。  
因此 HEI 更像一个“结构达标 / 符合度”指标，而不是“总量摄入”指标。

### 2.2 AMDR Fit：三大宏量营养素供能比例是否合理

AMDR，全称 Acceptable Macronutrient Distribution Range，中文可译为：

```text
宏量营养素可接受供能比例范围
```

AMDR 负责判断：

```text
碳水、脂肪、蛋白质这三大核心营养素的供能比例是否合理。
```

通俗解释：

```text
AMDR 看的是：你的饮食能量结构有没有偏科。
```

例如：

- 碳水比例过高
- 脂肪比例过高
- 蛋白质比例过低
- 某一类宏量营养素极端偏离正常范围

成人常用 AMDR 范围：

```text
Carbohydrate 碳水：45%–65% energy
Fat 脂肪：20%–35% energy
Protein 蛋白质：10%–35% energy
```

AMDR 与 HEI 的区别：

```text
HEI 看食物组结构。
AMDR 看三大宏量营养素的供能比例。
```

一个用户可能 HEI 不低，但碳水比例过高；这时 AMDR 会补足 HEI 没有直接表达的问题。

### 2.3 RDA / AI Adequacy：关键营养素绝对量是否足够或过多

RDA，全称 Recommended Dietary Allowance，中文可译为：

```text
推荐膳食摄入量
```

AI，全称 Adequate Intake，中文可译为：

```text
适宜摄入量
```

RDA / AI 负责判断：

```text
某些关键营养素的绝对摄入量是否达到人体基本需要。
```

通俗解释：

```text
RDA / AI 看的是：你身体需要的具体营养素有没有吃够。
```

它和 AMDR 的区别：

```text
AMDR 看比例。
RDA / AI 看绝对量。
```

例子：

```text
用户今天碳水、脂肪、蛋白质比例正常，AMDR 得分很高；
但钙、膳食纤维、钾、维生素 D 长期不足。
```

这种情况 AMDR 不一定能发现，但 RDA / AI 可以发现。

UL，全称 Tolerable Upper Intake Level，中文可译为：

```text
可耐受最高摄入量
```

如果某个营养素存在 UL，则该营养素既要判断是否摄入不足，也要判断是否摄入过多。

### 2.4 Meal Timing：用餐时间是否规律

Meal Timing 负责判断：

```text
用户吃饭时间是否稳定。
```

通俗解释：

```text
Meal Timing 看的是：你吃饭的节奏稳不稳。
```

它不判断食物营养质量，也不判断热量目标。  
它只作为轻权重节律项，占 Diet Balance 的 10%。

Meal Timing 包含：

- Eating Window：每日进食窗口
- Eating Jetlag：工作日和周末用餐时差
- Meal Timing SD：近期用餐时间标准差

睡前重餐暂不纳入，因为它需要睡眠时间数据。

---

## 3. HEI-2020 计算

### 3.1 输入

HEI-2020 的输入来自食物识别、食物数据库和营养数据库。

输入需要能计算或估算：

- 每日总摄入食物
- 食物组 cup equivalent / oz equivalent
- 每 1000 kcal 中各食物组密度
- 添加糖能量占比
- 饱和脂肪能量占比
- 钠密度
- 脂肪酸比例

### 3.2 输出

直接调用 HEI-2020 官方规则，得到：

```text
HEI_2020 ∈ [0, 100]
```

进入总公式：

```text
HEI_Contribution = HEI_2020 × 0.50
```

---

## 4. AMDR Fit 计算

### 4.1 输入

```text
carb_g
fat_g
protein_g
```

### 4.2 换算为供能量

```text
carb_kcal = carb_g × 4
fat_kcal = fat_g × 9
protein_kcal = protein_g × 4

macro_kcal = carb_kcal + fat_kcal + protein_kcal
```

### 4.3 计算供能比例

```text
carb_pct = carb_kcal / macro_kcal
fat_pct = fat_kcal / macro_kcal
protein_pct = protein_kcal / macro_kcal
```

注意：这里的 `macro_kcal` 只用于计算三大营养素供能比例，不代表把“总热量控制”纳入 Diet Balance。

### 4.4 单个宏量营养素评分函数

函数名：

```text
MacroRangeScore(x, lower, upper, hard_low, hard_high)
```

参数说明：

```text
x = 当前营养素供能比例
lower = 推荐下限
upper = 推荐上限
hard_low = 严重偏低边界
hard_high = 严重偏高边界
```

函数：

```text
if lower <= x <= upper:
    score = 100

elif hard_low <= x < lower:
    score = 100 × (x - hard_low) / (lower - hard_low)

elif upper < x <= hard_high:
    score = 100 × (hard_high - x) / (hard_high - upper)

else:
    score = 0
```

### 4.5 AMDR 阈值

```text
Carbohydrate:
lower = 0.45
upper = 0.65
hard_low = 0.25
hard_high = 0.80

Fat:
lower = 0.20
upper = 0.35
hard_low = 0.10
hard_high = 0.50

Protein:
lower = 0.10
upper = 0.35
hard_low = 0.05
hard_high = 0.45
```

### 4.6 AMDR Fit 总分

```text
AMDR_Fit =
Carb_AMDR_Score × 0.40
+ Fat_AMDR_Score × 0.30
+ Protein_AMDR_Score × 0.30
```

进入总公式：

```text
AMDR_Contribution = AMDR_Fit × 0.20
```

### 4.7 示例

输入：

```text
carb_g = 280
fat_g = 70
protein_g = 90
```

换算：

```text
carb_kcal = 280 × 4 = 1120
fat_kcal = 70 × 9 = 630
protein_kcal = 90 × 4 = 360
macro_kcal = 1120 + 630 + 360 = 2110
```

比例：

```text
carb_pct = 1120 / 2110 = 0.531
fat_pct = 630 / 2110 = 0.299
protein_pct = 360 / 2110 = 0.171
```

三项均在 AMDR 范围内：

```text
Carb_AMDR_Score = 100
Fat_AMDR_Score = 100
Protein_AMDR_Score = 100
```

所以：

```text
AMDR_Fit = 100
AMDR_Contribution = 100 × 0.20 = 20
```

---

## 5. RDA / AI Adequacy 计算

### 5.1 纳入计算的营养素

```text
Protein 蛋白质
Fiber 膳食纤维
Calcium 钙
Iron 铁
Potassium 钾
Vitamin D 维生素 D
Magnesium 镁
Folate 叶酸
Vitamin B12 维生素 B12
```

每个用户需要根据年龄、性别等信息匹配对应 RDA / AI / UL。

### 5.2 识别不到时的处理

如果某个营养素没有识别到或无法计算：

```text
该营养素不参与 RDA / AI Adequacy 计算。
```

也就是说，它从分子和分母中同时移除。

### 5.3 单个营养素摄入不足评分

定义：

```text
adequacy_ratio = actual_intake / RDA_or_AI
```

函数：

```text
if adequacy_ratio >= 1.00:
    adequacy_score = 100

elif 0.80 <= adequacy_ratio < 1.00:
    adequacy_score = 80 + (adequacy_ratio - 0.80) / 0.20 × 20

elif 0.50 <= adequacy_ratio < 0.80:
    adequacy_score = 40 + (adequacy_ratio - 0.50) / 0.30 × 40

else:
    adequacy_score = adequacy_ratio / 0.50 × 40
```

### 5.4 UL 摄入过量评分

如果该营养素存在 UL，则继续计算：

```text
ul_ratio = actual_intake / UL
```

函数：

```text
if ul_ratio <= 1.00:
    ul_score = 100

elif 1.00 < ul_ratio <= 1.20:
    ul_score = 100 - (ul_ratio - 1.00) / 0.20 × 20

elif 1.20 < ul_ratio <= 1.50:
    ul_score = 80 - (ul_ratio - 1.20) / 0.30 × 40

else:
    ul_score = 40
```

最终该营养素得分：

```text
final_nutrient_score = min(adequacy_score, ul_score)
```

如果该营养素没有 UL：

```text
final_nutrient_score = adequacy_score
```

### 5.5 RDA / AI 权重

```text
Protein: 0.20
Fiber: 0.20
Calcium: 0.10
Iron: 0.10
Potassium: 0.10
Vitamin D: 0.10
Magnesium: 0.07
Folate: 0.07
Vitamin B12: 0.06
```

### 5.6 RDA / AI Adequacy 总分

```text
RDA_AI_Adequacy =
Σ(final_nutrient_score_i × weight_i)
/
Σ(weight_i for available nutrients)
```

进入总公式：

```text
RDA_AI_Contribution = RDA_AI_Adequacy × 0.20
```

### 5.7 示例

用户对应参考值：

```text
Protein RDA = 60 g
Fiber AI = 30 g
Calcium RDA = 1000 mg
Iron RDA = 8 mg
```

当天识别到：

```text
Protein = 72 g
Fiber = 18 g
Calcium = 650 mg
Iron = 10 mg
```

计算：

```text
Protein ratio = 72 / 60 = 1.20
Protein score = 100

Fiber ratio = 18 / 30 = 0.60
Fiber score = 40 + (0.60 - 0.50) / 0.30 × 40 = 53.3

Calcium ratio = 650 / 1000 = 0.65
Calcium score = 40 + (0.65 - 0.50) / 0.30 × 40 = 60

Iron ratio = 10 / 8 = 1.25
Iron score = 100
```

可用权重：

```text
Protein 0.20
Fiber 0.20
Calcium 0.10
Iron 0.10

Weight sum = 0.60
```

总分：

```text
RDA_AI_Adequacy =
(100×0.20 + 53.3×0.20 + 60×0.10 + 100×0.10) / 0.60

= (20 + 10.66 + 6 + 10) / 0.60
= 77.8
```

贡献：

```text
RDA_AI_Contribution = 77.8 × 0.20 = 15.56
```

---

## 6. Meal Timing 计算

### 6.1 Meal Timing 定义

Meal Timing 指用餐时间规律性。

它负责判断：

```text
用户一天的进食窗口是否过长，
工作日和周末之间的用餐节律是否偏移，
最近一段时间用餐时间是否稳定。
```

Meal Timing 不判断食物质量，不判断总热量，不判断 Goal。

Meal Timing 最终输出范围：

```text
Meal_Timing ∈ [70, 100]
```

这样它只对 Diet Balance 做轻度修正。

### 6.2 时间格式统一规则

所有时间转为 24 小时小数：

```text
08:30 = 8.5
12:45 = 12.75
19:15 = 19.25
23:30 = 23.5
```

凌晨 00:00–03:59 计入前一天饮食日：

```text
00:30 = 24.5
01:30 = 25.5
02:15 = 26.25
03:45 = 27.75
```

### 6.3 Eating Window

中文名：

```text
每日进食窗口
```

定义：

```text
一天中第一次有热量摄入到最后一次有热量摄入之间的时间跨度。
```

公式：

```text
Eating_Window = Last_Caloric_Time - First_Caloric_Time
```

评分：

```text
if 8 <= Eating_Window <= 12:
    EW_raw = 100

elif 12 < Eating_Window <= 14:
    EW_raw = 100 - (Eating_Window - 12) / 2 × 20

elif 14 < Eating_Window <= 16:
    EW_raw = 80 - (Eating_Window - 14) / 2 × 30

elif Eating_Window > 16:
    EW_raw = 50

elif 6 <= Eating_Window < 8:
    EW_raw = 90

else:
    EW_raw = 80
```

### 6.4 Eating Jetlag

中文名：

```text
用餐时差
```

定义：

```text
工作日和周末之间的用餐节律偏移。
```

先计算每日用餐中点：

```text
Eating_Midpoint = First_Caloric_Time + Eating_Window / 2
```

再计算：

```text
Weekday_Midpoint = average(Eating_Midpoint on weekdays)
Weekend_Midpoint = average(Eating_Midpoint on weekends)

Eating_Jetlag = abs(Weekend_Midpoint - Weekday_Midpoint)
```

评分：

```text
if Eating_Jetlag <= 1:
    EJ_raw = 100

elif 1 < Eating_Jetlag <= 2:
    EJ_raw = 100 - (Eating_Jetlag - 1) / 1 × 20

elif 2 < Eating_Jetlag <= 3:
    EJ_raw = 80 - (Eating_Jetlag - 2) / 1 × 30

else:
    EJ_raw = 50
```

### 6.5 Meal Timing SD

中文名：

```text
用餐时间标准差
```

定义：

```text
最近 7 天每日用餐中点的标准差。
```

公式：

```text
Meal_Timing_SD = std(Eating_Midpoint_7d)
```

单位：小时。

评分：

```text
if Meal_Timing_SD <= 0.5:
    SD_raw = 100

elif 0.5 < Meal_Timing_SD <= 1:
    SD_raw = 100 - (Meal_Timing_SD - 0.5) / 0.5 × 15

elif 1 < Meal_Timing_SD <= 2:
    SD_raw = 85 - (Meal_Timing_SD - 1) / 1 × 30

else:
    SD_raw = 55
```

### 6.6 Eating Jetlag 与 Meal Timing SD 的区别

```text
Eating Jetlag 看的是：工作日和周末之间有没有系统性偏移。
Meal Timing SD 看的是：最近 7 天每天的用餐时间整体波动大不大。
```

例子 1：

```text
周一到周五都在 14:00 左右吃饭
周六周日都在 17:00 左右吃饭
```

结果：

```text
Eating Jetlag 高
Meal Timing SD 中等偏高
```

说明问题是：

```text
周末明显后移
```

例子 2：

```text
周一 12:00
周二 17:00
周三 13:00
周四 18:00
周五 11:30
周六 16:30
周日 14:00
```

结果：

```text
Eating Jetlag 可能不高
Meal Timing SD 高
```

说明问题是：

```text
每天都不稳定
```

### 6.7 Meal Timing 总计算

```text
Meal_Timing_raw =
0.35 × EW_raw
+ 0.30 × EJ_raw
+ 0.35 × SD_raw
```

将结果修正到 70–100：

```text
Meal_Timing = 70 + (Meal_Timing_raw / 100) × 30
```

进入总公式：

```text
Meal_Timing_Contribution = Meal_Timing × 0.10
```

因为 Meal Timing 只占 10%，且自身被压缩到 70–100，所以它对 Diet Balance 的最大影响约为 3 分。

---

## 7. Diet Balance 完整计算示例

输入：

```text
HEI_2020 = 72
AMDR_Fit = 100
RDA_AI_Adequacy = 77.8
Meal_Timing = 95.0
```

计算：

```text
Diet Balance =
72 × 0.50
+ 100 × 0.20
+ 77.8 × 0.20
+ 95.0 × 0.10

= 36
+ 20
+ 15.56
+ 9.50

= 81.06
```

最终：

```text
Diet Balance = 81
```

---

## 8. 输出结构建议

工程输出可以包含底层分数，但用户端只展示 Diet Balance。

```json
{
  "diet_balance": 81,
  "components": {
    "hei_2020": 72,
    "amdr_fit": 100,
    "rda_ai_adequacy": 77.8,
    "meal_timing": 95.0
  },
  "debug": {
    "amdr": {
      "carb_pct": 0.531,
      "fat_pct": 0.299,
      "protein_pct": 0.171,
      "carb_score": 100,
      "fat_score": 100,
      "protein_score": 100
    },
    "meal_timing": {
      "eating_window": 11.36,
      "eating_jetlag": 2.45,
      "meal_timing_sd": 1.20,
      "ew_raw": 100,
      "ej_raw": 66.5,
      "sd_raw": 79,
      "meal_timing_raw": 83.38
    }
  }
}
```

---

## 9. 删除项

以下内容不进入 Diet Balance：

```text
Calories / EER
Goal
Diversity
Confidence
Late Heavy Meal
```

---

## 10. 资料依据

- USDA Food and Nutrition Service, How the HEI Is Scored  
  https://www.fns.usda.gov/cnpp/how-hei-scored

- NIH Office of Dietary Supplements, Nutrient Recommendations and Databases  
  https://ods.od.nih.gov/healthinformation/nutrientrecommendations.aspx

- National Academies / NCBI Bookshelf, Description of the Acceptable Macronutrient Distribution Range  
  https://www.ncbi.nlm.nih.gov/books/NBK610333/

- National Academies, Acceptable Macronutrient Distribution Ranges by Age Group  
  https://www.nationalacademies.org/read/27957/chapter/5

- Zerón-Rugerio et al., Eating Jet Lag: A Marker of the Variability in Meal Timing and Its Association with Body Mass Index  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6950551/
