# Changelog

本文件记录 `Relty_PM` 产品资料的新增、调整、迁移和重要结论变更。

格式参考 Keep a Changelog；日期使用 `YYYY-MM-DD`。

## [2026-07-05]

### Corrected

- 修正资料同步方向：产品侧 Markdown 应复制到 `文稿/AI生成_PRD/`，而不是将 AI 生成文稿复制到 `Relty_PM/`。
- 删除此前误放入 `Relty_PM/` 的两份副本；`文稿/AI生成_PRD/` 中的原稿不受影响。

### Notes

- 产品侧文档原件继续保留在 `Relty_PM/`，目标目录保存同步副本。

## [2026-07-01]

### Added

- 创建 `Relty_PM/` 产品资料库及分层目录。
- 新增资料库说明和后续维护规则。

### Moved

- 将 `健身模块产品文档.md` 迁入 `01_PRD/`。
- 将 `agent_service/reports/HR_analysis.md` 迁入 `01_PRD/`，并重命名为 `训练报告需求草案.md`。
- 将 `PAI指标计算方式.md` 迁入 `02_指标设计/`。
- 将 `activity_algorithm_spec.md` 迁入 `02_指标设计/`，并采用中文文件名。
- 将 `运动训练健康评估指标_DeepResearch.md` 迁入 `03_产品研究/`。
- 将 `docs/ego_imu_research_handoff.md` 迁入 `03_产品研究/`，并采用更清晰的中文文件名。

### Notes

- 本次仅整理产品侧资料，不移动 API、前端、算法流程、提示词、实验结果和通用技术方案。
- 除为 `训练报告需求草案.md` 补充标题外，迁移过程中未改写原文内容。
