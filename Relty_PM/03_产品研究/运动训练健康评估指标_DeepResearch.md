# 运动训练健康评估指标 Deep Research
> 研究时间：2026-06-29 | 研究对象：普通健身人群与消费级被动记录产品 | 核心问题：健身领域是否存在类似 HEI 的训练健康评分

## 1. 结论

### 1.1 有没有健身版 HEI

**没有一个得到广泛认可、能像 Healthy Eating Index（HEI）那样同时覆盖“训练是否健康”的统一指数。**

HEI 能成立，是因为它有相对清晰的对象：饮食模式对膳食指南的依从程度。训练更难压成一条轴。一个人可能：

- 达到每周有氧活动建议，却完全不做抗阻训练；
- 每周规律力量训练，但心肺活动不足；
- 训练剂量合理，但动作疼痛、恢复变差；
- 训练过程并不“均衡”，却在专项能力上持续进步；
- 本周训练很少，却拥有很高的心肺适能和力量基础。

这些分别是行为、训练处方、耐受性、安全和结果，不是同一个构念。

目前最接近“健身版 HEI”的体系有三类：

1. **指南依从型评分**：WHO / 美国身体活动指南、AHA Life’s Essential 8、加拿大 24 小时活动指南。它们判断一个人的活动行为是否接近公共健康建议。
2. **单一生理暴露评分**：Personal Activity Intelligence（PAI）。它把心率暴露折算成周分，并用长期队列结局验证。
3. **健康相关体适能测试组**：心肺适能、肌力、功能能力、身体组成等。它们测“身体具备什么能力”，不是“这周训练安排得是否健康”。

**产品结论：可以建立“运动健康画像”，不应声称已经得到一个科学验证的“训练健康总分”。**【强证据支持分域；总分设计属于待验证产品构造】

### 1.2 对 Fitness Agent 最有价值的科学骨架

建议使用四层模型：

| 层级 | 回答的问题 | 最强可用依据 | 当前设备可用性 |
|---|---|---|---|
| 安全闸门 | 是否出现不适合继续自行训练的信号 | PAR-Q+、ACSM 运动前筛查 | 需要用户问答，不能靠视频诊断 |
| 健康行为 | 本周活动是否达到公共健康建议 | WHO、PAG、AHA LE8、PAVS | 力量频率和覆盖可做；有氧强度需心率或用户输入 |
| 训练过程 | 剂量是否可解释、是否在个人耐受范围 | FITT-VP、RPE/RIR、sRPE、ACSM 抗阻训练立场 | 组次可做；负重、努力度和恢复仍缺 |
| 体适能结果 | 身体能力有没有改善 | VO₂max/CRF、1RM、握力、功能场测 | 需要标准测试或更多传感器 |

如果产品必须显示一个 0–100 数字，最诚实的名字是：

> **Movement Guideline Score / 运动指南达成度**

它只表示公共健康活动建议的完成情况。不要命名为“训练健康分”“安全分”或“恢复分”。

### 1.3 最值得借鉴的现成评分

**AHA Life’s Essential 8 的身体活动子分最接近可公开复用的 0–100 评分。**

它以每周中等强度等效分钟数计分，高强度 1 分钟按中等强度 2 分钟折算：

| 等效中等强度分钟/周 | 分数 |
|---:|---:|
| 0 | 0 |
| 1–29 | 20 |
| 30–59 | 40 |
| 60–89 | 60 |
| 90–119 | 80 |
| 120–149 | 90 |
| ≥150 | 100 |

这个非线性分档反映了从“完全不动”增加少量活动时，边际健康收益较大。它有 AHA 正式评分定义，并已用于队列研究，但它只测有氧型身体活动，没有评价抗阻训练结构、恢复或动作质量。【强证据】

### 1.4 研究后的明确建议

Fitness Agent 不应寻找一条神奇公式。应建立以下五张卡：

1. **有氧活动达成度**：直接借鉴 LE8 身体活动 0–100 分；
2. **力量训练达成度**：每周力量训练日数，以及是否覆盖主要功能区；
3. **训练剂量记录**：动作、组、次、时长；有负重和 RIR 后再升级为刺激量；
4. **个人负荷与耐受趋势**：本周相对过去 28 天，不设置跨用户统一“最佳负荷”；
5. **体适能结果**：用标准化测试单独展示心肺、力量和功能趋势。

总览页可以给“达成 / 部分达成 / 数据不足”状态，不建议一开始做平均总分。

## 2. 研究对象的边界

### 2.1 “训练健康”至少有五种不同含义

日常语言里的“练得健康”可能指：

- 对慢病和死亡风险有益；
- 训练处方满足目标；
- 没有过量、恢复良好；
- 动作安全、没有疼痛；
- 身体能力正在改善。

运动科学没有证明这五项可以被同一个潜变量完整代表。把它们混合，会让一个高分产生错误保证。例如用户达到 150 分钟有氧和两次力量训练，不代表他动作无风险；用户 VO₂max 很高，也不代表最近没有过度训练。

### 2.2 评价对象必须先选定

本报告把指标分为：

- **行为依从**：做了多少符合指南的活动；
- **训练暴露**：训练量、强度、频率、密度；
- **生理反应**：心率、疲劳、酸痛、睡眠、表现变化；
- **体适能结果**：心肺适能、力量、功能、身体组成；
- **不良信号**：胸痛、晕厥、异常呼吸困难、持续疼痛等。

HEI 类比只适合第一层。训练暴露和生理反应更像药物剂量与耐受监测；体适能结果更像化验结果；不良信号则是安全筛查。

## 3. 纵向演进：运动健康是怎样被量化的

### 3.1 第一阶段：从“是否运动”到活动剂量

公共健康最早需要回答的不是健身计划是否完美，而是人群需要多少活动才能降低疾病风险。现代指南逐步形成了“频率、强度、时间、类型”的 FITT 框架。

WHO 2020 与美国《身体活动指南（第二版）》的成人主干建议高度一致：

- 每周 150–300 分钟中等强度有氧；或
- 每周 75–150 分钟高强度有氧；或等效组合；
- 每周至少 2 天进行涉及所有主要肌群的中等或更高强度肌力活动；
- 减少久坐，任何活动都比没有好。

它们的优势是结局明确：全因死亡、心血管疾病、糖尿病、部分癌症和心理健康。局限也明确：这是群体公共健康建议，不是某个健身用户的最佳处方。

### 3.2 第二阶段：把活动变成临床“生命体征”

Kaiser Permanente 推出的 Exercise Vital Sign（EVS）和 Exercise is Medicine 使用的 Physical Activity Vital Sign（PAVS）把问题压缩为：

1. 平均每周有几天进行中等至剧烈活动？
2. 每次平均多少分钟？

两者相乘得到每周分钟数。与加速度计比较时，EVS 对是否达到 150 分钟建议的识别只有中等水平：一项研究报告敏感度 67%、特异度 68%，加权一致性有限。它的价值不是精密测量，而是低成本筛查和长期追踪。

英国 GPPAQ 则把工作和休闲活动组合为四级 Physical Activity Index，用于初级医疗决定是否提供活动干预。它同样是筛查工具，不是训练质量量表。

这一步很重要：科学落地不一定意味着复杂公式。一个构念清楚、误差已知的两问题工具，常常比一个来源不明的 87 分更可靠。

### 3.3 第三阶段：从活动行为走向体适能结果

身体活动是行为，体适能是身体属性。两者相关但不相同。

美国心脏协会 2016 年将心肺适能（CRF）主张为临床生命体征。CRF 对心血管和全因死亡有很强预测价值；AHA 总结中，低于 5 METs 的成人风险较高，而 8–10 METs 以上通常与更高生存率相关。这里的 METs 是最大运动能力，不是把日常活动 MET 简单相加。

肌力也与健康结局相关，但测量必须具体到测试：握力、1RM、椅子起立等测量不同能力，不能直接求一个未经验证的平均值。成人场地测试系统综述认为，YMCA 台阶测试和握力在受限条件下是较实用的替代，但每种测试仍有特定效度范围。

这条路线非常适合年度或季度体适能评估，不适合每日生成训练健康分。

### 3.4 第四阶段：从统一分钟数走向个体化强度

PAI 是最接近“运动版单一健康分”的尝试。它依据年龄、性别、静息和最大心率，把不同强度活动转为滚动周分。HUNT 队列以及中国 Kadoorie Biobank 等研究发现，周 PAI ≥100 与较低的心血管疾病、缺血性心脏病或死亡风险相关。

PAI 的突破是：一分钟高强度活动和一分钟轻活动不再等价，分数还能随个体心率能力调整。

但 PAI 不是训练综合健康分：

- 它主要反映心肺强度暴露；
- 不能评价力量训练的肌群覆盖和机械张力；
- 不能判断动作质量；
- 不能直接判断恢复；
- 公开研究中的 PAI 常由问卷回推，并不等同于所有商业设备的实时算法；
- 具体算法和消费产品实现存在知识产权与透明度限制。

还要披露利益相关：PAI 发明人 Ulrik Wisløff 在部分研究中同时担任 PAI Health 的科学顾问。该信息不否定大型队列结果，但会降低“仅凭同一研究团队即可完成产品效标验证”的可信度要求，外部复现应获得更高权重。

它适合作为“心肺活动健康效应分”的参照，不适合作为 Fitness Balance 的底层公式。

### 3.5 第五阶段：全天行为与多维健康

加拿大 24 小时活动指南把一整天视为有限时间预算，联合考虑：

- 中高强度活动；
- 肌力活动；
- 久坐与娱乐屏幕时间；
- 睡眠。

近期成人队列研究通常发现，满足更多 24 小时建议与更好的健康结局相关，但各分项贡献并不一定相等；2025 年一项 SUN 队列研究中，三项全部达标者死亡风险更低，但独立分析时身体活动是最稳定的预测项。

这给产品一个启示：恢复和睡眠可以与训练并列展示，但不能因为它们都在“一天”里就直接等权平均。

## 4. 横向对比：哪些体系最像 HEI

| 体系 | 测量对象 | 输出 | 验证基础 | 最大优点 | 不能回答 |
|---|---|---|---|---|---|
| WHO / PAG | 活动指南依从 | 分钟与达标状态 | 系统综述、公共健康结局 | 权威、透明、跨产品 | 训练质量和个人恢复 |
| AHA LE8 身体活动分 | 中等强度等效分钟 | 0–100 | AHA 正式算法、队列研究 | 最接近 HEI 式评分 | 力量、动作、恢复 |
| EVS / PAVS | 自报 MVPA | 分钟/周、是否达标 | 与加速度计和问卷比较 | 极低输入成本 | 精确强度和训练结构 |
| GPPAQ | 工作与休闲活动 | 四级 PAI | 英国初级医疗验证 | 适合筛查干预 | 健身房训练细节 |
| PAI | 个体化心率暴露 | 周分，100 为目标 | 多个大型长期队列 | 把强度和个人心率纳入 | 力量刺激与训练结构 |
| 24 小时活动指南 | 活动、久坐、睡眠 | 分项达标数 | 指南与队列研究 | 避免只看健身房时间 | 不能诊断恢复 |
| AHA CRF 生命体征 | 最大心肺能力 | VO₂max / MET capacity | 强预后证据 | 是强结果指标 | 这周训练是否合理 |
| 体适能测试组 | 心肺、力量、功能等 | 分项测试结果 | 测试级效度与常模 | 真实能力而非行为代理 | 日常训练过程 |
| ACSM 抗阻训练立场 | 抗阻处方变量 | 频率、组数、负重、ROM 等 | 系统综述总览 | 目标相关、训练学最直接 | 没有统一健康总分 |
| PAR-Q+ / ACSM 筛查 | 运动前风险信号 | 是否需要进一步评估 | 专家共识与证据更新 | 处理安全边界 | 不能当健康得分 |

### 4.1 最接近 HEI：AHA LE8

LE8 总体系包含饮食、身体活动、尼古丁暴露、睡眠、BMI、血脂、血糖和血压。每项 0–100，整体分为八项等权平均。

它值得借鉴的不是“等权平均”本身，而是三件事：

1. 每个构成项有明确语义；
2. 每项先独立归一化到 0–100；
3. 评分档位公开，能够被外部研究复现。

身体活动子分没有纳入力量训练，是它用于 Fitness Agent 时最大的缺口。若直接照搬，规律举铁但有氧较少的用户可能分数很低；这并非算法错误，而是构念只覆盖了 MVPA。

### 4.2 最接近消费级周分：PAI

PAI 的结局验证强于多数可穿戴产品自创分数。它在 HUNT 和中国大样本人群中有前瞻性关联。

但关联不等于随机干预因果，也不能证明“100”对所有设备、所有用户都是精确生理阈值。研究常依赖自报活动估算 PAI，健康用户更可能保持活动的混杂也无法完全消除。

### 4.3 最接近临床可实施：PAVS

PAVS 的精度不惊艳，却非常诚实：它只回答每周中高强度活动分钟。它告诉我们一个产品设计原则：

> 用户轻量输入可以补上传感器最关键的盲区。

对第一人称训练设备，一次训练后的 session RPE，可能比模型再推断十个“恢复特征”更有科学价值。

### 4.4 最接近“训练是否合理”：ACSM 抗阻训练框架

ACSM 2026 抗阻训练立场整合 137 篇系统综述、超过 3 万名参与者。它支持：

- 规律渐进的抗阻训练；
- 每周至少 2 次并覆盖主要肌群；
- 较高努力程度；
- 力量目标更偏向较高负重、多组、完整 ROM；
- 肌肥大与更高周组数相关；
- 绝对力竭并非所有目标的必要条件。

它没有发布“抗阻训练健康指数”。原因不是研究者忘了做，而是最优处方依目标、训练史、动作和个体反应而变。产品可以借用变量，不应伪造一个 ACSM 背书的加权总分。

## 5. 哪些科学依据能真正评价“训练健康”

### 5.1 维度 A：有氧活动剂量

**可作为公共健康评分，有强依据。**

基本变量：

\[
M_{eq}=M_{moderate}+2M_{vigorous}
\]

其中 \(M_{eq}\) 是每周等效中等强度分钟。

推荐直接采用 LE8 分档。它比简单的 \(100\times M_{eq}/150\) 更符合低剂量区边际收益较大的证据，也减少“149 分钟不及格、150 分钟突然满分”的跳变。

数据要求：

- 心率区间且最大心率估计可靠；或
- 经验证的活动类型与强度模型；或
- 用户 RPE / talk test 输入。

仅凭看到“在跑步”不能判断所有人的相对强度。

### 5.2 维度 B：力量训练频率与覆盖

**可作为指南依从评分，有强方向证据，但连续分数需要产品化。**

官方建议支持每周至少 2 天、涉及所有主要肌群。可以显示：

- 本周力量训练 0 / 1 / ≥2 天；
- 六个功能区分别记录到几天；
- 哪些功能区未获得可信记录。

六类功能区可用：

1. 上肢推；
2. 上肢拉；
3. 膝主导；
4. 髋主导；
5. 小腿；
6. 核心 / 躯干。

六类是测量和产品折衷，不是指南原文。它需要用模型混淆矩阵证明比 10 类或 15 类更稳定。

### 5.3 维度 C：训练量与努力程度

**可以监测，不能给普通人统一最佳线。**

最低可用记录：

- 每动作组数；
- 每组次数；
- 训练时长；
- 休息时间；
- 同一动作的周趋势。

更完整的剂量需要：

- 外部负重；
- RPE 或 RIR；
- ROM；
- 动作速度；
- 是否为热身组或工作组。

组数与肌肥大存在剂量—反应关系，但“更多”不是无限更好，也没有一个跨人群、跨肌群的通用 MEV / MRV 表。MEV、MAV、MRV 可作为教练的个体化框架，不是已经效标验证的消费级阈值。

### 5.4 维度 D：负荷变化与恢复耐受

**适合个人纵向监测，不适合跨用户静态判分。**

常见内部负荷：

\[
sRPE\ Load=session\ RPE\times duration
\]

可比较最近 7 天与过去 28 天，但不应简单使用 Acute:Chronic Workload Ratio 作为伤病预测器。相关文献对 ACWR 的因果解释、数学耦合、分母不稳定和“甜蜜区”存在持续批评。

更稳妥的产品输出：

- 本周负荷较个人过去 4 周明显上升 / 接近 / 下降；
- 同时展示睡眠、酸痛、主观疲劳和表现是否同向变化；
- 不输出“受伤概率 37%”。

固定的“连续两天同肌群扣分”也缺乏依据。训练量、密度、负重、接近力竭程度和训练史都会改变恢复时间。

### 5.5 维度 E：心肺适能

**是强健康结果指标，但需要标准测量。**

优先级：

1. 实验室心肺运动试验 VO₂max / VO₂peak；
2. 经验证的次最大运动测试；
3. 标准场地测试；
4. 可穿戴估计值。

产品必须区分实测和估算，并提供误差范围。VO₂max 不应按天剧烈波动；如果算法每天随心率噪声大幅改变，它更可能是负荷分而不是体适能结果。

### 5.6 维度 F：肌力和功能

**是重要结果指标，但没有一个适合所有动作的总及格线。**

可用指标包括：

- 握力；
- 特定动作 1RM / 3RM / 5RM；
- 相对力量；
- 30 秒椅子起立；
- 起立行走或步速，尤其适用于老年人。

1RM 有较高重测信度，但需要标准动作、熟悉过程和安全流程。把深蹲、卧推和硬拉各自的百分位直接平均，需要专门验证。

### 5.7 维度 G：疼痛和安全信号

**应该作为闸门，不应该成为可被其他高分抵消的子项。**

需要明确问询：

- 运动中胸痛；
- 晕厥或接近晕厥；
- 与活动不相称的异常呼吸困难；
- 已知心血管、代谢或肾脏疾病；
- 新发或持续加重的肌肉骨骼疼痛；
- 医生要求限制的活动。

PAR-Q+ 和 ACSM 运动前筛查用于决定是否需要进一步医疗评估。它们不是诊断工具。产品遇到红旗时应给安全提示，而不是扣 20 分后继续推荐高强度训练。

## 6. 可以借鉴的白皮书、指南和立场声明

### 6.1 第一优先级：直接构成产品健康基线

1. **WHO Guidelines on Physical Activity and Sedentary Behaviour（2020）**  
   用于成人有氧剂量、力量训练频率和减少久坐的总框架。

2. **Physical Activity Guidelines for Americans, 2nd edition（2018）**  
   对主要肌群、活动强度、健康收益和特殊人群有详细解释。

3. **AHA Life’s Essential 8（2022）**  
   提供公开的身体活动 0–100 计分，是最接近 HEI 的可复用模块。

4. **ACSM Resistance Training Prescription Position Stand（2026）**  
   用于抗阻训练频率、负重、组数、努力程度、ROM 与不同训练目标。

### 6.2 第二优先级：筛查和测量方法

5. **Exercise is Medicine / PAVS**  
   用于最小化活动问询和临床式达标判断。

6. **GPPAQ**  
   用于理解如何把短问卷转为四级身体活动分类。

7. **PAR-Q+ 与 ACSM Preparticipation Screening**  
   用于安全闸门和转诊逻辑。

8. **AHA Cardiorespiratory Fitness as a Clinical Vital Sign（2016）**  
   用于心肺适能结果层和产品声明边界。

9. **2024 Adult Compendium of Physical Activities**  
   用于活动类型参考 MET；不可当作个体真实能耗测量。

### 6.3 第三优先级：产品个体化与全天行为

10. **PAI / HUNT 系列研究**  
    用于理解如何将心率强度暴露与长期结局连接。

11. **Canadian 24-Hour Movement Guidelines for Adults**  
    用于活动、久坐和睡眠分项展示。

12. **训练负荷监测共识与 sRPE 文献**  
    用于个人趋势，不用于跨用户统一健康诊断。

## 7. 推荐的产品指标体系

### 7.1 第一层：Movement Guideline Profile

#### 有氧活动分

直接采用 AHA LE8 身体活动分档。若设备无法可靠判断强度，显示“数据不足”，不要用动作类型硬算。

#### 力量训练状态

- 0 天：未记录；
- 1 天：部分达到；
- ≥2 天：达到频率建议；
- 同时显示六功能区明细。

将 0 / 1 / 2 天映射为 0 / 50 / 100 是易解释的产品插值，**不是 WHO 或 ACSM 发布的正式评分**。

#### 久坐与日常活动

若胸前设备不是全天佩戴，不能据此判断全天久坐。可以接入手机或手表数据，但应作为另一数据源。

### 7.2 第二层：Training Dose Profile

- 各动作可信组数和次数；
- 功能区记录工作量；
- 时长和密度；
- session RPE；
- 有负重后增加 Volume Load；
- 有 RIR 后区分低努力组和高努力组。

这些指标用于解释，不先做总分。

### 7.3 第三层：Tolerance Profile

- 7 天负荷相对 28 天个人历史；
- 酸痛；
- 主观疲劳；
- 睡眠；
- 同动作表现变化；
- 疼痛或不适。

只有多个信号同向异常时才提示“近期负荷增加且恢复信号变差”。仍不应诊断过度训练综合征或预测伤病。

### 7.4 第四层：Fitness Outcomes

按季度或月度展示：

- 心肺适能；
- 关键动作力量；
- 功能测试；
- 用户关心的身体组成。

每个结果保留独立单位、测试协议和可信度，不强制平均。

## 8. 如果业务坚持要一个 0–100 总分

可以做一个**研究版 Movement Guideline Score**，但必须标注“待效标验证”：

\[
S_{movement}=w_A S_A+w_R S_R+w_C S_C
\]

- \(S_A\)：AHA LE8 有氧活动子分；
- \(S_R\)：力量训练频率分，0 天=0、1 天=50、≥2 天=100；
- \(S_C\)：六功能区中达到 2 个可信训练日的比例；
- \(w_A,w_R,w_C\)：**当前没有权威依据决定三者的相对权重**。

不建议直接设 40% / 30% / 30% 并称为科学公式。研究版可以暂时等权：

\[
w_A=w_R=w_C=\frac13
\]

等权的含义只是“没有足够证据区分重要性时少做假设”，不是三者生理贡献相等。

正式发布前必须进行：

1. **内容效度**：运动医学、运动生理、抗阻训练专家审查；
2. **构念效度**：与 PAVS、加速度计 MVPA、真实训练日志比较；
3. **准则效度**：与 CRF、力量、血压、血糖或长期健康结果比较；
4. **重测信度**：相同训练输入能否稳定输出；
5. **敏感度**：真实增加活动后能否合理变化；
6. **可解释性测试**：用户是否误认为它是安全或恢复诊断；
7. **公平性测试**：年龄、性别、残障、慢病和不同训练方式是否系统性偏低。

在这些验证完成前，三个分项比总分更科学。

## 9. 当前设备的数据能力映射

| 指标 | 当前可做 | 需要补充 | 不应宣称 |
|---|---|---|---|
| 力量训练日数 | 是 | 训练段识别验证 | 不漏记任何训练 |
| 功能区覆盖 | 有条件 | 动作映射、置信度校准 | 精确肌肉刺激 |
| 组数 / 次数 | 有条件 | IMU 与人工复核 | 每组均为有效组 |
| 训练时长 | 是 | 间歇与离场规则 | 生理负荷 |
| 有氧分钟 | 有条件 | 心率或主观强度 | 只靠视频精确分强度 |
| session RPE | 尚无 | 训练后一次问询 | 从表情或动作自动推断 |
| 外部负重 | 尚无 | 器械识别或用户录入 | %1RM、Volume Load |
| 恢复 | 尚无 | 睡眠、酸痛、疲劳、表现 | 恢复充分或过度训练 |
| VO₂max | 否 | 标准协议、心率、速度/功率 | 心肺适能实测 |
| 受伤风险 | 否 | 临床级前瞻性验证 | 个体受伤概率 |

## 10. 关键风险

### 10.1 把活动达标写成训练安全

指南达标只说明活动行为与较好的群体健康结局相关。它不能抵消疼痛、胸痛、晕厥或动作风险。

### 10.2 把训练量写成训练质量

组数、次数和分钟是暴露。没有负重、努力程度、ROM 和用户目标时，不能判断刺激是否充分。

### 10.3 把群体关联写成个体处方

PAI 100、150 分钟或每周 2 天是群体证据锚点。用户不应被告知“达到后一定健康”或“低于就不健康”。

### 10.4 用一个总分掩盖短板

高有氧分不应抵消安全红旗；高力量覆盖不应抵消长期完全没有有氧；好睡眠也不应把疼痛平均掉。

### 10.5 让模型误差变成身体评价

设备漏识别背部训练时，产品应说“未记录到足够证据”，而不是“你的背部训练不健康”。

### 10.6 给未经验证的权重穿上科学外衣

公式里最容易被忽略的不是变量，而是权重。只要相对权重没有效标研究，就必须标注为产品假设。

## 11. 落地路线

### 阶段 A：先做分项，不做总分

- 接入 AHA LE8 有氧活动分；
- 输出力量训练 0 / 1 / ≥2 天；
- 输出六功能区可信覆盖；
- 增加训练后 session RPE；
- 安全问询独立为闸门。

### 阶段 B：建立验证集

- 人工标注训练、有氧强度、动作、组次和功能区；
- 校准模型置信度；
- 与心率、加速度计和用户日志对照；
- 检查不同动作、器械、性别和体型的误差。

### 阶段 C：做个人纵向指标

- 建立至少 28 天基线；
- 用 sRPE、时长、组次和表现趋势描述负荷；
- 不采用未经验证的 ACWR 伤病甜蜜区；
- 只在多信号同向异常时给恢复提示。

### 阶段 D：加入体适能结果

- 设计标准化心肺和力量测试；
- 明确实测值、估算值和参考常模；
- 用月度或季度趋势，而不是日分波动。

### 阶段 E：研究总分是否真的有价值

对比三种界面：

1. 只有分项；
2. 状态标签 + 分项；
3. 总分 + 分项。

若总分增加用户误解、不能改善行为决策，就不要为了视觉简洁强行保留。

## 12. 最终判断

健身领域并不缺数字。缺的是一个能诚实区分“行为、剂量、耐受和结果”的产品结构。

最接近 HEI 的科学路径，不是给每次训练打一个玄学分，而是建立一套公开的指南依从画像：

- 有氧活动有没有达到健康剂量；
- 每周是否进行了主要肌群抗阻训练；
- 活动、久坐和睡眠是否形成合理的全天结构；
- 身体的心肺、力量和功能是否在长期改善；
- 是否出现需要停止自动建议、转向人工或医疗评估的红旗。

对 Fitness Agent，第一版最值得做的是 **AHA LE8 有氧分 + 力量训练频率与覆盖 + session RPE + 个人 28 天趋势**。

它没有一个华丽的万能分数，但它比万能分数更接近科学。

## 信息来源

访问时间均为 2026-06-29。

1. World Health Organization. [WHO Guidelines on Physical Activity and Sedentary Behaviour](https://www.who.int/publications/i/item/9789240014886). 2020.
2. U.S. Department of Health and Human Services. [Physical Activity Guidelines for Americans, 2nd edition](https://odphp.health.gov/sites/default/files/2019-09/Physical_Activity_Guidelines_2nd_edition.pdf). 2018.
3. Lloyd-Jones DM, et al. [Life’s Essential 8: Updating and Enhancing the American Heart Association’s Construct of Cardiovascular Health](https://pmc.ncbi.nlm.nih.gov/articles/PMC10503546/). Circulation. 2022.
4. American Heart Association. [Life’s Essential 8](https://www.heart.org/en/professional/workplace-health/lifes-simple-7).
5. American Heart Association. [Life’s Essential 8 physical activity scoring table](https://svn.bmj.com/content/svnbmj/9/5/481/DC1/embed/inline-supplementary-material-1.pdf).
6. Coleman CJ, et al. [Dose-response association of aerobic and muscle-strengthening physical activity with mortality](https://pubmed.ncbi.nlm.nih.gov/35953241/). Br J Sports Med. 2022.
7. Momma H, et al. [Muscle-strengthening activities and risk and mortality in major non-communicable diseases](https://pmc.ncbi.nlm.nih.gov/articles/PMC9209691/). Br J Sports Med. 2022.
8. Currier BS, et al. [ACSM Position Stand: Resistance Training Prescription for Muscle Function, Hypertrophy, and Physical Performance in Healthy Adults](https://pmc.ncbi.nlm.nih.gov/articles/PMC12965823/). Med Sci Sports Exerc. 2026.
9. Sallis RE, et al. [Validity of the Exercise Vital Sign Tool to Assess Physical Activity](https://pmc.ncbi.nlm.nih.gov/articles/PMC8154650/). Am J Prev Med. 2021.
10. Exercise is Medicine. [Physical Activity Vital Sign](https://www.exerciseismedicine.org/eim-in-action/health-care/health-care-providers/assess-physical-activity-levels-of-your-patients/).
11. UK Department of Health and Social Care. [General Practice Physical Activity Questionnaire](https://www.gov.uk/government/publications/general-practice-physical-activity-questionnaire-gppaq).
12. Zisko N, et al. [Personal Activity Intelligence, Sedentary Behavior and Cardiovascular Risk Factor Clustering](https://pubmed.ncbi.nlm.nih.gov/28274818/). Prog Cardiovasc Dis. 2017.
13. Hammer P, et al. [Personal Activity Intelligence and Ischemic Heart Disease in the China Kadoorie Biobank](https://pubmed.ncbi.nlm.nih.gov/36362780/). J Clin Med. 2022.
14. Tari AR, et al. [Temporal changes in PAI and incident dementia and dementia-related mortality](https://pmc.ncbi.nlm.nih.gov/articles/PMC9403490/). Lancet Reg Health Eur. 2022.
15. Ross R, et al. [Importance of Assessing Cardiorespiratory Fitness in Clinical Practice](https://professional.heart.org/en/science-news/importance-of-assessing-cardiorespiratory-fitness-in-clinical-practice-a-case-for-fitness/top-things-to-know). AHA Scientific Statement. 2016.
16. Chen W, et al. [Criterion-Related Validity of Field-Based Fitness Tests in Adults](https://pmc.ncbi.nlm.nih.gov/articles/PMC8397016/). Front Physiol. 2021.
17. Canadian Society for Exercise Physiology. [Canadian 24-Hour Movement Guidelines for Adults](https://csepguidelines.ca/wp-content/uploads/2020/11/24HGuidelines-Poster-ENG.pdf). 2020.
18. Ferrari G, et al. [Adherence to the 24-Hour Movement Guidelines and all-cause mortality](https://pmc.ncbi.nlm.nih.gov/articles/PMC12857418/). 2025.
19. ePARmed-X. [Official PAR-Q+ evidence resources](https://eparmedx.com/resources/publications/).
20. Exercise is Medicine. [ACSM Preparticipation Screening Guidelines](https://www.exerciseismedicine.org/assets/page_documents/ACSM%20Preparticipation%20Screening%20Guidelines.pdf).
21. Herrmann SD, et al. [2024 Adult Compendium of Physical Activities](https://pmc.ncbi.nlm.nih.gov/articles/PMC10818145/). J Sport Health Sci. 2024.
22. Haddad M, et al. [Session-RPE Method for Training Load Monitoring](https://pubmed.ncbi.nlm.nih.gov/29163016/). Front Neurosci. 2017.
23. Impellizzeri FM, et al. [Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls](https://pubmed.ncbi.nlm.nih.gov/32502973/). Int J Sports Physiol Perform. 2020.
24. Parkinson AO, et al. [The Calculation, Thresholds and Reporting of Inter-Limb Strength Asymmetry](https://pubmed.ncbi.nlm.nih.gov/35321131/). J Sports Sci Med. 2021.

## 方法论说明

本报告采用横纵分析法：纵向追踪运动健康量化从公共健康活动剂量、临床生命体征、体适能结果到个体化可穿戴评分的演进；横向比较指南依从、心率暴露、训练处方、安全筛查和体适能测试，最后将可复用的科学锚点与仍需产品验证的评分假设分开。
