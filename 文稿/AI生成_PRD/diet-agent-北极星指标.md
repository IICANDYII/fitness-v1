# diet-ai-agent 北极星指标体系

> 版本：v1.0
> 日期：2026-06-01
> 适用：Relty Health Agent / diet-ai-agent 子项目
> 对齐文档：`health_agent_prd.md` / `CLAUDE.md`

---

## TL;DR

我们盯两个数：

1. **当天的**：AI 看到你吃了啥，你愿意点确认吗？ → KR-1 **行为识别确认率**，目标 > 60%
2. **后续的**：AI 给的饮食建议，你愿意听吗（点采用 + 或者第二天 Pin 真的看到你吃了）？ → 北极星 **建议采纳率**，目标 > 25%

第二个更重要，但**要先把 tomorrow_meal / weekly_meal_plan / food_recommend 这 3 个 0 输出报告接通**，不然第二个数永远算不出来。

---

## 1. 为什么需要北极星

北极星指标是产品里**最重要的那个数**，团队所有人盯着它，决定产品做得好不好。

- 一堆指标 → 大家各做各的，方向散
- 一个指标 → 所有改动都问"这能让这个数涨吗"，团队对齐

类比：
- 抖音的北极星 = 用户每天刷多久
- Spotify 的北极星 = 每月听歌时长
- 我们的北极星 = **AI 给的建议，用户真的采纳的比例**

---

## 2. 候选指标对照（为什么选/不选）

| 候选 | 选不选 | 原因 |
|---|---|---|
| DAU / MAU | ❌ | 引擎活跃度不是产品价值，违反 CLAUDE.md "刷使用时长"反原则 |
| 热量记录数 | ❌ | 违反 CLAUDE.md 第 3 节"严禁做成热量账本" |
| 餐次记录数 | ❌ | 数量不是质量，AI 检测多没用，用户不确认就是 0 价值 |
| 7 日留存 | ❌ | 经典但**早期太晚反映**（alpha 一周才算一次） |
| 推荐 CTR | ❌ | 我们不是推荐场景，是"识别 + 洞察" |
| 用户停留时长 | ❌ | 抖音化指标，违反"克制"产品气质 |
| **行为识别确认率** | ✅ KR | 反映 AI 识别准 + 用户信任 |
| **建议采纳率** | ✅ 主北极星 | 反映 AI 决策真实价值 |

---

## 3. 双指标定义

### 3.1 KR-1：行为识别确认率（事后 - 验证识别能力）

```
行为识别确认率 = 已确认餐次 / AI 检测的总待确认餐次
```

**细分三档**：

| 细分 | 含义 | 信号方向 |
|---|---|---|
| 直接确认（confirm-as-is） | 用户原封不动点确认 | 信任 + 识别准（最理想） |
| 修改后确认（edit then confirm） | 识别有偏差但用户接受 | 识别可用，但需优化 |
| 忽略（ignore） | 用户主动忽略 | 识别错或无价值 |

**回答的产品问题**：Pin 看得准不准 + 用户信不信任？

### 3.2 北极星：建议采纳率（事前 - 验证决策价值）

```
建议采纳率 = (显式采纳 + 隐式采纳) / AI 给出的建议总数
```

**针对 4 类输出建议**：
- `daily_insight_reports` 的 `main_suggestion`
- `tomorrow_meal_reports`
- `weekly_meal_plan_reports`
- `food_recommend_reports`

**回答的产品问题**：AI 给的建议，用户愿意听吗？

### 3.3 显式 vs 隐式采纳（关键设计）

| 类型 | 定义 | 信号强度 |
|---|---|---|
| **显式采纳** | 用户在 UI 上点"采用"按钮 | 强（主动行为） |
| **隐式采纳** | AI 推荐了 X，次日 Pin 检测到用户实际吃了 X | 最强（行为印证） |

**隐式采纳是 Relty 独有的杀手锏**——Pin 在持续观察，所以可以做"建议 → 行为"闭环验证：

```
周日 AI 推荐："明早建议吃燕麦+鸡蛋"
       ↓
周一早上 Pin 检测到：用户吃了燕麦
       ↓
隐式采纳成立 ✓
```

淘宝/抖音都做不到这个闭环——他们只能看你加购点击，不能看你是否真的吃/穿了。**这是产品壁垒，应该写进北极星定义。**

---

## 4. 指标关系图

```
┌──────────────────────────────────────────────────────┐
│  Pin 持续观察                                          │
│        ↓                                              │
│  AI 检测到用户吃了 X → 推送"待确认"                     │
│        ↓                                              │
│  ┌─────────────────────────────────────────┐         │
│  │ KR-1：行为识别确认率                       │         │
│  │  用户：确认 / 修改后确认 / 忽略            │         │
│  └─────────────────────────────────────────┘         │
│        ↓                                              │
│  累积今日饮食数据                                      │
│        ↓                                              │
│  生成 daily_insight + 明日建议 + 周膳食 + 食物推荐      │
│        ↓                                              │
│  ┌─────────────────────────────────────────┐         │
│  │ 北极星：建议采纳率                         │         │
│  │  显式采纳（点采用）+ 隐式采纳（行为印证）    │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────┘

   识别准（KR-1 高）  →  建议有数据基础  →  采纳率高
   ↓                                          ↓
   是因                                       是果
```

链条任何一环掉，最终北极星都会掉。所以 KR-1 必须配合北极星一起看。

---

## 5. 配套 3 个诊断指标

只看北极星会被刷数据（确认率 95% 但修改率 0% = 用户无脑点确认）。必须配诊断：

| 诊断指标 | 含义 | 健康阈值 |
|---|---|---|
| **修改率**（edited / confirmed） | 用户改了多少 AI 识别结果 | 10–25% 健康；< 5% 可能盲目确认；> 40% 识别有大问题 |
| **忽略率**（ignored / pending） | 用户主动忽略的比例 | < 15% 健康 |
| **主动查看 insight 比例** | 一天内打开过 daily_insight 的用户 | > 40% 说明洞察有价值 |

---

## 6. 目标数值

### 6.1 三阶段目标

| 指标 | Alpha（5–30 用户） | Beta（100–500） | 成熟期（1000+） |
|---|---|---|---|
| **KR-1 识别确认率** | > 60% | > 75% | > 85% |
| **北极星 建议采纳率（显+隐）** | > 25% | > 35% | > 50% |
| **建议采纳率·只看隐式** | > 15% | > 25% | > 35% |
| **诊断 1：修改率** | 10–25% | 10–25% | 10–25% |
| **诊断 2：忽略率** | < 15% | < 15% | < 15% |
| **诊断 3：主动查看 insight** | > 40% | > 50% | > 60% |

### 6.2 为什么采纳率目标比确认率低

- **确认率是"反馈"**，门槛低（点一下）
- **采纳率是"行动"**，门槛高（真的去吃/真的去做）
- 行业基线（健康类 App 建议采纳率 20–40%），不要拍脑袋定 50%+ 把团队压死

---

## 7. 阶段性切换策略

**当前现状**：tomorrow_meal / weekly_meal_plan / food_recommend 3 类报告 **0 输出**——意味着建议采纳率**现在算不出来**（分母为 0）。

所以分阶段执行：

| 阶段 | 时间 | 主看指标 | 原因 |
|---|---|---|---|
| **阶段 0**（现在 ~ 3 类报告接通） | 2–3 周 | **KR-1 识别确认率**（暂代主指标） | 建议还没出，没法算采纳率 |
| **阶段 1**（3 类报告接通后） | beta 启动 | **建议采纳率**（升为正式北极星）+ KR-1 配合看 | 完整双指标体系建立 |
| **阶段 2**（用户量上来后） | 公测+ | 加入 30 日留存 + 习惯组合 | 单一确认/采纳率不够反映长期价值 |

**最紧急的事**：让开发哥这周第一优先级**修 3 类报告 0 输出问题**。不修这个，建议采纳率永远是 N/A，双指标体系立不起来。

---

## 8. 指标计算 SQL（开发哥实现参考）

> 待开发哥根据真实 schema 完善，本节只列查询思路。

### 8.1 KR-1：日级行为识别确认率

```sql
-- 当日待确认餐次 → 确认情况
SELECT
  COUNT(CASE WHEN status='confirmed' THEN 1 END)                AS confirmed_count,
  COUNT(CASE WHEN status='edited' THEN 1 END)                   AS edited_count,
  COUNT(CASE WHEN status='ignored' THEN 1 END)                  AS ignored_count,
  COUNT(*)                                                       AS total_pending,
  ROUND(100.0 * COUNT(CASE WHEN status IN ('confirmed','edited') THEN 1 END) / COUNT(*), 1) AS confirm_rate_pct,
  ROUND(100.0 * COUNT(CASE WHEN status='edited' THEN 1 END) / NULLIF(COUNT(CASE WHEN status IN ('confirmed','edited') THEN 1 END), 0), 1) AS edit_rate_pct,
  ROUND(100.0 * COUNT(CASE WHEN status='ignored' THEN 1 END) / COUNT(*), 1) AS ignore_rate_pct
FROM diet_records
WHERE record_date = CURRENT_DATE
  AND status IN ('pending_confirmation', 'confirmed', 'edited', 'ignored');
```

### 8.2 北极星：建议采纳率（显式 + 隐式）

```sql
-- 显式采纳：用户点"采用"
SELECT
  COUNT(CASE WHEN adopted_at IS NOT NULL THEN 1 END)            AS explicit_adopted,
  COUNT(*)                                                       AS total_suggestions,
  ROUND(100.0 * COUNT(CASE WHEN adopted_at IS NOT NULL THEN 1 END) / COUNT(*), 1) AS explicit_rate_pct
FROM ai_suggestions  -- 需要新建表，详见 §9
WHERE created_date = CURRENT_DATE - INTERVAL '1 day';

-- 隐式采纳：建议 vs 次日实际进食的食物名匹配
SELECT
  s.id AS suggestion_id,
  s.recommended_food,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM diet_timeline_events e
      WHERE e.user_id = s.user_id
        AND DATE(e.frame_time) = s.target_date
        AND e.food_name LIKE '%' || s.recommended_food || '%'  -- 简化版，应用模糊匹配
        AND e.status IN ('confirmed', 'edited')
    ) THEN 1 ELSE 0
  END AS implicit_adopted
FROM ai_suggestions s
WHERE s.target_date = CURRENT_DATE;
```

### 8.3 总采纳率

```sql
最终采纳率 = (显式采纳数 + 隐式采纳数 - 两者重叠) / 总建议数
```

> 注意：显式 + 隐式可能重叠（用户既点了采用又真吃了），去重后才是最终值。

---

## 9. Schema 改动建议（落地这套指标需要）

### 9.1 新建 `ai_suggestions` 表

```sql
CREATE TABLE ai_suggestions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  source_report_type VARCHAR(50) NOT NULL,
    -- 'daily_insight' | 'tomorrow_meal' | 'weekly_meal_plan' | 'food_recommend'
  source_report_id BIGINT NOT NULL,
  recommended_food VARCHAR(200),       -- 建议吃什么（可结构化或纯文本）
  recommendation_text TEXT,            -- 建议原文
  target_date DATE NOT NULL,           -- 建议针对哪天
  created_at DATETIME NOT NULL,
  adopted_at DATETIME,                 -- 用户显式点"采用"的时间
  ignored_at DATETIME,                 -- 用户显式忽略时间
  implicit_adopted BOOLEAN DEFAULT NULL, -- 次日定时任务计算后写入
  INDEX idx_user_date (user_id, target_date),
  INDEX idx_source (source_report_type, source_report_id)
);
```

### 9.2 前端 UI 改动

在每条 AI 建议下加两个按钮：
- 「采用这个建议」→ 写入 `adopted_at`
- 「不感兴趣」→ 写入 `ignored_at`

### 9.3 后台定时任务

每天凌晨跑 `compute_implicit_adoption.py`：
- 遍历昨天 `target_date` 的所有 suggestion
- 跟昨天的 `diet_timeline_events.food_name` 做模糊匹配
- 命中 → 写入 `implicit_adopted = true`

---

## 10. Dashboard 设计建议

每天发飞书群一份卡片，包含：

```
diet-ai-agent 日报 · 2026-XX-XX
──────────────────────────────
🎯 北极星 · 建议采纳率：__%
   ├─ 显式 __%  ├─ 隐式 __%

📊 KR-1 · 识别确认率：__%
   ├─ 直接确认 __%
   ├─ 修改确认 __%  ⚠ 修改率 __% [偏高/正常/偏低]
   └─ 忽略 __%      ⚠ 忽略率 __% [偏高/正常/偏低]

🔍 诊断
   ├─ insight 主动查看率 __%
   └─ 活跃用户数 __

⚠️ 异常告警
   - tomorrow_meal_reports 仍为 0 ← 待开发哥修复
```

---

## 11. 给开发哥/团队的一句话

> 我们盯两个数：
>
> 1. **当天的**：AI 看到你吃了啥，你愿意点确认吗？目标 > 60%
> 2. **后续的**：AI 给的饮食建议，你愿意听吗（点采用 + 或者第二天 Pin 真的看到你吃了）？目标 > 25%
>
> 第二个更重要——这是产品真实价值。但要先把 tomorrow_meal / weekly_meal_plan / food_recommend 这 3 个报告接通，不然第二个数永远算不出来。

---

## 附录：与 CLAUDE.md 的对齐校验

| CLAUDE.md 要求 | 本指标是否符合 |
|---|---|
| §3 不做热量账本 | ✅ 北极星不是热量数 |
| §3 不做打卡社区 | ✅ 不看活跃时长 |
| §4.2 不精准到个位数 | ✅ 采纳率是行为指标，不涉及精准热量 |
| §8 数据不足不输出结论 | ✅ 阶段 0 明确等"建议接通"再用北极星 |
| §17 强化生活方式 Agent | ✅ 隐式采纳是 Pin 持续观察的独有能力 |
| §17 减少记录负担 | ✅ 高确认率隐含 UI 摩擦低 |
| §17 让 AI 更可信可解释 | ✅ 采纳率本身就是"建议是否可信"的代理 |
