# Relty 第一人称健身动作数据库 v1
## 数据来源
- 原始仓库：https://github.com/hasaneyldrm/exercises-dataset
- 原始数据文件：https://raw.githubusercontent.com/hasaneyldrm/exercises-dataset/main/data/exercises.json
- 说明：本文件是按 Relty 胸前第一人称设备场景进行的人工规则筛选版本，不是原库全量导出。原库 README 声明 data/exercises.json 为 1,324 条动作的主数据文件。

## 筛选结果
- 主白名单源动作数量：75
- 标准动作数量：49
- 需要复核/暂不进入主库数量：13

## 按标准器械统计
- cable: 14
- dumbbell: 14
- fixed_machine: 12
- barbell: 10
- smith_machine: 8
- no_equipment: 7
- assisted_machine: 4
- cardio_bike: 3
- cardio_elliptical: 1
- cardio_stepmill: 1
- cardio_treadmill: 1

## 按训练部位统计
- 胸: 14
- 腿: 14
- 背: 13
- 手臂: 11
- 肩: 11
- 有氧: 6
- 腿/臀: 3
- 胸/手臂: 3

## 按第一人称可识别等级统计
- A: 50
- B: 25

## 前 30 个标准动作聚合数量
- cable_lat_pulldown / 高位下拉: 3
- cable_seated_row / 坐姿绳索划船: 3
- dumbbell_biceps_curl / 哑铃弯举: 3
- dumbbell_shoulder_press / 哑铃推肩: 3
- smith_bench_press / 史密斯卧推: 3
- assisted_dip / 辅助双杠臂屈伸: 2
- assisted_pullup / 辅助引体向上: 2
- barbell_bent_over_row / 杠铃俯身划船: 2
- barbell_biceps_curl / 杠铃弯举: 2
- barbell_squat / 杠铃深蹲: 2
- cable_biceps_curl / 绳索弯举: 2
- cable_chest_fly / 绳索夹胸: 2
- cable_overhead_triceps_extension / 绳索过顶臂屈伸: 2
- dumbbell_bench_press / 哑铃卧推: 2
- machine_chest_press / 固定器械推胸: 2
- machine_leg_press / 腿举: 2
- machine_shoulder_press / 固定器械推肩: 2
- pullup / 引体向上: 2
- pushup / 俯卧撑: 2
- smith_shoulder_press / 史密斯推肩: 2
- stationary_bike / 健身车/动感单车: 2
- barbell_bench_press / 杠铃卧推: 1
- barbell_deadlift / 杠铃硬拉: 1
- barbell_incline_bench_press / 杠铃上斜卧推: 1
- barbell_overhead_press / 杠铃推举: 1
- bodyweight_dip / 双杠臂屈伸: 1
- bodyweight_lunge / 箭步蹲: 1
- bodyweight_squat / 自重深蹲: 1
- cable_lateral_raise / 绳索侧平举: 1
- cable_triceps_pushdown / 绳索下压: 1

## 使用建议
- 第一版员工录制素材建议优先覆盖 mvp_priority=1 且 first_person_level=A 的动作。
- first_person_level=B 的动作可以保留在计划生成中，但识别结果需要结合训练计划、时间轴和用户轻确认。
- review_needed_v1.csv 中的动作不建议进入第一阶段员工通用训练计划。
- 后续如果拿到完整本地仓库，可以用脚本把 `source_id` 对应的真实 image/gif 文件名进一步补全；当前文件里 image/gif_url 字段仅保留了 ID 占位和源仓库路径。
