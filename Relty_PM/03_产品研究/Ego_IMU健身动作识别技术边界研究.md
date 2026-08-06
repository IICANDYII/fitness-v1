# Ego / Ego+IMU 健身动作识别技术边界研究 —— 调研交接文档

> 用途：交接给 Gemini（或其他研究者）继续完成「横纵分析法」深度研究报告。
> 立场：写给健身硬件产品经理（胸前相机 + IMU 设备），目标是把"技术能做到什么、做不到什么"的边界讲清楚，供产品定义使用。
> 本文档分三部分：
> 1. 已经核实过的素材（可直接引用）
> 2. 上一轮被对抗验证否决 / 出处存疑、绝不能直接抄的数字
> 3. 还需要继续搜的清单和检索建议

---

## 一、研究目标（产品视角，必须先对齐）

PM 的设备：**胸前单目相机 + IMU**，针对**健身房器械训练场景**。

PM 要从这份报告里得到的，不是技术爽文，而是边界判断：

1. **单独 Ego（纯第一人称视觉）能做到什么粒度？**——能稳定识别到"动作+器械"层，还是能到"动作变式"层（平板/上斜哑铃卧推）？
2. **Ego + IMU 融合到底补了什么？**——是补语义、补运动学、补时序边界，还是只补一点点？
3. **低帧率（1fps 量级）下，哪些信息退化最严重？**
4. **哪些任务再怎么堆模型也做不到，必须靠 ①用户手动标 ②训练计划先验 ③额外硬件（双目/深度）补？**
5. **能否把"open-world 分类"压成"closed-set 验证"，量级上能带来多大增益？**

最终是要回答："哪些功能我可以承诺，哪些功能必须设计成用户参与的形态。"

---

## 二、已核实素材（可放心引用）

### 2.1 Ego4D（CVPR 2022）

- **arXiv:2110.07058**，标题 *Ego4D: Around the World in 3,000 Hours of Egocentric Video*。
- 规模：3,670 小时，931 名参与者，74 个地点，9 个国家。
- 标注体系：自由叙述 *"C [动词] [名词]"*——这意味着**Ego4D 本身没有运动专项的子类别标签**（如"上斜哑铃卧推"在标注体系里不存在）。
- 5 大基准任务：Episodic Memory（情景记忆，含 Natural Language Queries 子任务）、Hands and Objects、Audio-Visual Diarization、Social、Forecasting（含 Short-term/Long-term Action Anticipation）。
- 重要事实：**Ego4D 数据集本身包含 IMU 信号**（部分子集），这是 IMU2CLIP 等工作得以训练的基础。

> 边界含义：业界最大的第一人称数据集都没标到健身子类别，意味着任何想做"区分卧推变式"的产品，**不能指望开箱即用的 Ego4D 预训练模型**，必须自己造数据或加先验。

### 2.2 Ego-Exo4D（CVPR 2024）

- **arXiv:2311.18259**，标题 *Ego-Exo4D: Understanding Skilled Human Activity from First- and Third-Person Perspectives*。
- 规模：740 名参与者，13 个城市，1,286 小时视频，123 个自然场景。
- 模态：第一人称 + 第三人称同步视频、多通道音频、**eye gaze、3D 点云、相机姿态、IMU**、多组配对的语言描述（包含"专家解说"——教练/老师录的）。
- 新任务：fine-grained activity understanding、**proficiency estimation（熟练度评估）**、cross-view translation、3D hand/body pose。
- 项目页：http://ego-exo4d-data.org/

> 边界含义：
> 1. Meta/CMU 联手做 Ego-Exo4D 这件事本身就是对"纯第一人称做不动"的承认——**为了理解技能性动作（运动、乐器、修车），必须加第三人称视角**。这对 PM 是关键信号：胸前单目相机看不全自身动作（自遮挡），加 IMU 是补偿手段之一，但不是万能的。
> 2. "Proficiency estimation"任务的引入说明：业界从"识别在做什么"开始往"做得怎么样"延伸——这正是健身教练 App 的能力天花板方向。

### 2.3 IMU2CLIP（Meta，EMNLP Findings 2023）

- **arXiv:2210.14395**，*IMU2CLIP: Multimodal Contrastive Learning for IMU Motion Sensors from Egocentric Videos and Text*。
- 作者：Seungwhan Moon, Andrea Madotto 等（Meta）。
- 方法：把 IMU 信号通过对比学习对齐到 CLIP 的视频+文本联合空间，使得 IMU 数据也能"理解"语言描述。
- 关键结论（来自摘要）：
  - 可以做"motion-based media retrieval"——用 IMU 信号检索对应的视频和文本描述。
  - 可以做"natural language reasoning with motion data"。
  - **微调后显著提升下游动作识别准确率**（具体数字需读全文表格，摘要未给出）。
- 训练数据：Ego4D 中带 IMU 的子集。

> 边界含义：这是目前唯一能直接证明"IMU 可以补语义"的工作——传统认知里 IMU 只能给运动学（节奏/方向），但 IMU2CLIP 表明，把 IMU 跟视觉对齐预训练后，IMU 通道获得了"理解动作概念"的能力。对 PM 的含义是：
> - **不要把 IMU 当成纯节奏传感器使用**；它有潜力承担一部分动作分类的语义工作。
> - 但这一切都建立在"有大量配对视频做对齐训练"的前提上。健身房垂类如果没有自己的视频+IMU 对齐数据，这套预训练能不能迁移过去，是研发同学要验证的关键问题。

### 2.4 EPIC-Kitchens-100（IJCV 2022）

- **arXiv:2006.13256**，*Rescaling Egocentric Vision*。
- 规模：100 小时，45 名参与者，89,977 个动作片段。
- 标注：开放词汇的"动词 + 名词"对，例：*cut tomato*、*open drawer*。
- 标注流程：**两阶段**——参与者录制时**用语音同步叙述自己的动作**（演员自标注名称），第二阶段由标注员手动**对齐时间戳**并归类动词/名词。

> 边界含义：EPIC-Kitchens-100 这套"语音自述 + 后期时间戳对齐"是当前业界细粒度 egocentric 标注的事实标准流程。对 PM 的含义是：
> - **让用户在做完一组后说一句"刚才是 X 动作 X kg"**，本质就是 EPIC 的第一阶段——这是已被验证可行的范式。
> - 时间戳的精确对齐成本很高，靠用户实时打卡比靠 AI 自动找边界更靠谱。

### 2.5 已确认的孤立事实（次要但可引用）

- 健身房固定相机数次数代表作 **GymCam**（CMU，UbiComp/IMWUT 2018，*GymCam: Detecting, Recognizing and Tracking Simultaneous Exercises in Unconstrained Scenes*）—— **不在 arxiv**，发表于 ACM IMWUT；用 optical flow + 固定俯视相机做计数和识别。
- **MM-Fit**（UbiComp 2020 ）—— 多模态健身数据集，含视频+IMU+智能手表，覆盖 10 种健身动作。**arxiv 上没有原始论文**，发表于 IMWUT 4(4)。
- **TSN（Temporal Segment Networks，ECCV 2016）**：经典稀疏采样方法，证明视频分类**不需要密集帧**，用稀疏的 3–8 帧已能达到高准确率——这是"低帧率下场景/物体识别仍可靠"的理论基础。
- **EPIC-Kitchens-100** 多模态版本（含 audio）：证明仅视觉之外的模态对 egocentric 识别有显著贡献。

---

## 三、上一轮被对抗验证否决 / 出处存疑的数字（⚠️ 不要直接抄）

> 这些数字在前一次 deep-research 工作流的 3 票对抗验证里被否决，或者本次复核发现 arXiv ID 挂错了。继续研究的人要**重新从原文核实**，不要照搬。

### 3.1 ⚠️ 被否决的"硬数字"

| 声明 | 被引到的来源 | 投票 | 处理方式 |
|---|---|---|---|
| EPIC-Kitchens-100 最优 Top-1 action accuracy 约 44–47% | arXiv:2006.13256 | 0-3 否决 | 必须查 PapersWithCode 当前 leaderboard，并核实指标定义 |
| RepNet 在 QUVA 上 OBO = 0.17、MAE = 0.104 | arXiv:2104.11670 | 0-3 否决 | 直接读 RepNet 论文 Table 表格 |
| RepNet 用合成数据训练、class-agnostic | arXiv:2104.11670 | 1-2 否决 | 需读全文 method 章节核实 |
| TransRAC 在所有数据集 SOTA 且零样本泛化 | arXiv:2204.01018 | 0-3 否决 | 需读全文 experiments |
| WEAR 早期融合 ~82.26%、camera-only 81.30%、IMU-only 76.86% | 据称 arXiv:2301.07676 | 0-3 否决 | **此 arxiv ID 本次复核发现是档案学论文，挂错号！需重新定位 WEAR 真正出处** |

### 3.2 ⚠️ 本次新发现的引用错误

- **`arXiv:2301.07676` 不是 WEAR 论文**。本轮用 `curl https://export.arxiv.org/api/query?id_list=2301.07676` 直查，得到的标题是档案学/工作流相关论文。
- 之前 deep-research 报告里关于 WEAR 的"F1 = 93.99%、mAP = 83.13%、oracle 上界"等数字，**所引 arXiv ID 错误**。这些数字本身可能正确（WEAR 论文真实存在，由 Bock 等人发表），但必须重新定位真实 arxiv 编号或 IMWUT 出处。
- 候选搜索方向：用 Google Scholar 直接搜 "WEAR outdoor sports egocentric inertial Bock"；该论文可能首发于 **IMWUT 2024** 或 **arxiv 2024 年某 ID**，需要确认。

### 3.3 Episodic Memory NLQ "10–15% recall@1" 数字

- 上次报告里出现的"Ego4D NLQ 最优 recall@1 IoU=0.3 约 10–15%"，**被对抗验证 0-3 否决**。
- 实际数字应直接查 Ego4D 官方 leaderboard（https://eval.ai/web/challenges/challenge-page/1626 或类似）或最新挑战赛报告。
- 注意：该数字过去两年涨得很快，2022 年的数字到 2025 年已经过时。

---

## 四、还需要继续搜的清单（给 Gemini 的任务单）

### 4.1 必须解决的"硬数字"补全

| 待查事实 | 用途 | 建议检索路径 |
|---|---|---|
| Ego4D 各 benchmark 任务最新 SOTA（特别是 STA Short-term Action Anticipation 和 LTA Long-term） | 证明 Ego 单独的能力边界 | Ego4D 官方 leaderboard / CVPR 2024-2026 challenge 报告 |
| EPIC-Kitchens-100 当前 SOTA Top-1 action / verb / noun | 同上 | PapersWithCode EPIC-Kitchens-100 |
| IMU2CLIP 论文 Table 中具体的 ablation 数字（vision-only / IMU-only / IMU+vision） | 证明 IMU 补什么 | 读 arXiv:2210.14395 全文 PDF |
| WEAR 论文真实 arxiv ID 和 oracle / camera-only / IMU-only / fusion 各组指标 | 证明多模态融合上限 | Google Scholar "WEAR dataset Bock 2024 egocentric inertial" |
| MM-Fit 论文（IMWUT 4(4) 2020）中视频-only / IMU-only / 多模态各自准确率 | 健身场景多模态融合证据 | 直接读 ACM IMWUT 论文 |
| 任何已发表的"chest-worn IMU + resistance training"数据集和准确率 | 与 PM 设备形态完全对应 | Google Scholar "chest IMU resistance training classification" |
| Recofit（CHI 2014）和后续 wearable 健身识别准确率 | IMU-only 健身识别基线 | Recofit 原论文 |

### 4.2 低帧率证据

- 找 "low frame rate / sparse sampling / 1fps action recognition" 的论文。TSN（2016）是经典基线，但需要 2022–2026 的更新工作。
- 重点找：把帧率从 30fps → 1fps，准确率下降曲线的实验。
- 推荐查 EPIC-Kitchens 的 ablation 部分。

### 4.3 Closed-set vs Open-world 量化

- 找 "context-aware human activity recognition" 真实带数字的工作（不是综述）。本轮 arxiv 检索发现了 2024 年的 *Heterogeneous Hyper-Graph Neural Networks for Context-aware HAR*，可以作为入口。
- 找 "few-shot exercise recognition" 或 "prior-constrained action classification"。
- 核心问题：当候选集从 100 类压到 5 类，准确率从 X% 提升到 Y%——这个 X/Y 必须有论文支撑。如果没找到健身专项的，至少要找通用 HAR 领域的。

### 4.4 第一人称的固有物理局限

- 自身遮挡（self-occlusion）：胸前相机看不到下肢/背部的量化研究。
- 运动模糊对 egocentric 识别的影响：可能要在 Ego4D 数据集统计里找。
- 双目/stereo 在运动场景的实测：有没有专门做运动/健身的，还是仅在 SLAM、机器人领域有？

### 4.5 VLM / 视频 LLM 时代的更新（2024-2026）

- 检索关键词：Video-LLaVA、VideoLLaMA、EgoVLP、EgoVLPv2、LaViLa、HierVL（Meta）、Ego4D Goal-Step 等。
- 重点判断：基础模型时代，**zero-shot 识别健身动作的能力到了哪一步**？是否已经能不训练就识别"哑铃卧推"这个粒度？
- 这是 PM 决策"等大模型 vs 现在自己造数据"的关键依据。

---

## 五、报告结构建议（按横纵分析法）

完整方法论：https://github.com/KKKKhazix/khazix-skills/blob/main/hv-analysis/SKILL.md

简化版结构：

```
封面页

一、一句话定义
   第一人称视觉是用"戴在身上的相机"理解人在做什么；它的边界正在被多模态融合和大模型同时推开。

二、纵向：从 GTEA 到 Ego-Exo4D 的演进史（6000-15000字）
   1. 起源（2009-2015）：GTEA、ADL、可穿戴相机时代
   2. EPIC-Kitchens 时代（2018-2020）：动词+名词标注范式确立
   3. Ego4D 时代（2022）：规模化、5 大 benchmark、IMU 模态加入
   4. 多模态融合时代（2022-2023）：IMU2CLIP 把 IMU 提升到语义级
   5. Ego-Exo4D 时代（2024）：承认纯第一人称做不动，加第三人称
   6. VLM 时代（2024-2026）：基础模型对粒度天花板的冲击

三、横向：同期技术路线对比（3000-10000字）
   - 路线 A：纯第一人称视觉（Ego4D 路线）
   - 路线 B：纯 IMU 可穿戴 HAR
   - 路线 C：第一人称视觉 + IMU 融合（WEAR、MM-Fit、IMU2CLIP）
   - 路线 D：第三人称固定相机（GymCam）
   - 路线 E：智能镜 / 智能器械嵌入式
   每条路线：能识别什么 / 准确率上限 / 强项 / 弱项 / 代表系统

四、横纵交汇洞察（1500-3000字）
   1. 为什么 Ego4D 路线必然走向加 IMU 和加第三人称？历史选择决定了今天的边界。
   2. 哪些边界是物理性的（自遮挡、视角），哪些是数据性的（缺细粒度标签）？
   3. 对 PM 的三个剧本：
      - 悲观：纯自动识别永远做不到健身变式粒度，必须靠用户标记
      - 中性：VLM + IMU 融合 + 训练计划先验，能在 2 年内把"动作名称"层做到 95%
      - 乐观：基础模型零样本能力突破，3 年内不需要垂类数据
   4. 产品建议：把"用户输入"设计成"训练计划 + 组开始结束"两项，AI 接管其余

五、信息来源
   所有引用的论文清单（arxiv ID + 验证状态）

六、方法论说明
   横纵分析法由数字生命卡兹克提出，本报告遵循其方法论框架。
```

---

## 六、报告写作的几条原则（写给 Gemini）

1. **不要编造数字**。搜不到的就标"暂缺"，绝不为了报告完整性凑数字。
2. **每个关键数字都要标 arxiv ID 或具体来源**，便于审阅时复核。
3. **被对抗验证否决过的数字（见第三节）禁用**，要重新核实才能用。
4. **写给 PM 看，不是写给研究员看**。专业术语第一次出现必须紧跟大白话解释。
5. **每个技术节点都要回答"对 PM 设备意味着什么"**，不能写成单纯的学术综述。
6. **诚实标注边界**：哪些是已被论文证实的、哪些是合理推断、哪些是猜测。
7. **PDF 渲染管线**：本仓库 `/tmp/hv-analysis/scripts/md_to_pdf_chrome.py` 已写好（基于 Chrome headless，绕开 weasyprint 的系统依赖），可直接使用。

---

## 七、当前进度盘点

| 任务 | 状态 |
|---|---|
| 卡兹克横纵分析法 skill 已下载并理解 | ✅ |
| PDF 渲染管线（Chrome headless）已写好测试通过 | ✅，路径 `/tmp/hv-analysis/scripts/md_to_pdf_chrome.py` |
| 上一轮 deep-research 报告已盘点，识别出引用错误 | ✅，见第三节 |
| 三个研究子 Agent（纵向/横向/边界专题）首轮启动 | ❌ 撞上会话额度限流，无有效产出 |
| 重启子 Agent 二轮 | ❌ WebSearch 后端模型异常，本轮不可用 |
| arxiv 直查核实关键论文 | 🟡 部分完成（Ego-Exo4D、IMU2CLIP 已核实；WEAR 真实 arxiv ID 未定位） |
| 撰写正式横纵报告 | ⏳ 未开始，待 Gemini 接手 |

---

## 八、给 Gemini 的开场建议

1. 先把第三节里那张"已被否决数字"表过一遍，建立"哪些数字一定要重查"的清单。
2. 再用 Google Scholar 把第四节里的待查项一项项落实。Google Scholar 比 arxiv API 覆盖更广，能找到 IMWUT/UbiComp 这类不在 arxiv 的论文。
3. 写报告时，**纵向部分**重点放在"为什么 Ego4D 不得不加 IMU、为什么 Ego-Exo4D 不得不加第三人称"——这两个转折直接对应 PM 设备形态的关键决策。
4. **横纵交汇部分**给 PM 的三剧本必须有逻辑链，不要写成"未来会更好"的空话。

祝研究顺利。
