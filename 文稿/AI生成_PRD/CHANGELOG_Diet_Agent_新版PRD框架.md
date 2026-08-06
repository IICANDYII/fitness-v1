# Diet Agent 新版PRD框架变更记录

## 2026-06-24

### 操作目的

新增一份与当前阶段进度对齐的 Diet Agent 新版 PRD 框架文档，并保留精确回滚说明。

本次操作不修改旧版《Relty 指标计算框架》，仅新增文件。

### 本次新增文件

1. `/Users/maxgao/Documents/dietagent交接/Diet Agent 新版PRD框架.md`
   - 用途：承载 Diet Agent 当前阶段的整合版 PRD 框架
   - 范围：整合旧版《Relty 指标计算框架》与当前阶段推进结果
   - 重点：`Balance`、`Goal`、`Meal Timing`、Goal 创建机制、主界面展示方向、与旧框架的映射关系

2. `/Users/maxgao/Documents/dietagent交接/CHANGELOG_Diet_Agent_新版PRD框架.md`
   - 用途：记录本次新增操作
   - 目的：便于后续继续修改或精确回滚

### 追加说明

本次并非只生成提纲式文档，而是将 `Diet Agent 新版PRD框架.md` 扩写为完整整合版。

该文件当前承担的角色是：

- 不修改旧版框架原文
- 单独承接当前阶段对齐后的完整 Diet Agent 产品定义
- 允许后续继续增量修改，同时保持回滚简单明确

### 后续扩展说明

后续已继续将该文件扩展为更完整的全局整合版，补回了旧版框架中的其他 Agent 板块位置，包括：

- `Fitness Agent`
- `Activity Agent`
- `Focus Agent`
- `Relax Agent`
- `Rest Agent`
- `Commute Agent`

扩展原则为：

- 保留旧版框架中的整体结构
- 统一当前产品表达为 `Balance + Goal`
- 仅对已明确的 Diet Agent 部分做细化定义
- 对尚未定稿的其他 Agent，不擅自新增公式或产品规则

### 回滚方式

如果需要完整回滚本次操作，只需删除以下两个新增文件：

1. `/Users/maxgao/Documents/dietagent交接/Diet Agent 新版PRD框架.md`
2. `/Users/maxgao/Documents/dietagent交接/CHANGELOG_Diet_Agent_新版PRD框架.md`

### 回滚结果

删除上述两个文件后，工作区将回到“仅保留原始框架文档与既有进度文档”的状态。

由于本次未修改 `/Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md`，因此不需要对旧版框架执行额外恢复操作。
