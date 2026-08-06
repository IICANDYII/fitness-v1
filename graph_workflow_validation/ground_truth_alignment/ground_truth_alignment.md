# Graph Ground Truth Alignment

先把相邻且高置信、同预测动作的 graph 图片合并成一个 group，再按每个 `shared/<folder>/ground_truth.json` 中 `type=exercise` 的顺序对齐。数量不一致的 folder 标记为 `count_mismatch`。

## Folder Summary

| folder | ground truth exercises | raw graph actions | merged graph groups | raw status | merged status |
|---|---:|---:|---:|---|---|
| 1 | 3 | 3 | 3 | ok | ok |
| 2 | 8 | 8 | 8 | ok | ok |
| 3 | 8 | 11 | 6 | count_mismatch | count_mismatch |
| 4 | 6 | 10 | 9 | count_mismatch | count_mismatch |
| 8 | 8 | 9 | 7 | count_mismatch | count_mismatch |
| 9 | 5 | 6 | 5 | count_mismatch | ok |
| 健身-高孟琦 | 4 | 3 | 3 | count_mismatch | count_mismatch |
| 张靖义-2026.06.11 | 9 | 9 | 9 | ok | ok |
| 手臂-胸-杨博宇 | 6 | 6 | 6 | ok | ok |
| 肩-秦紫渝 | 4 | 6 | 2 | count_mismatch | count_mismatch |
| 肩-背-秦紫渝 | 6 | 5 | 4 | count_mismatch | count_mismatch |
| 肩背-叶翔 | 5 | 11 | 8 | count_mismatch | count_mismatch |
| 腿-张开 | 9 | 8 | 7 | count_mismatch | count_mismatch |

## Row Alignment

| folder | seq | graph group | ground truth | reps | prediction | conf | status | merge | notes |
|---|---:|---|---|---|---|---:|---|---|---|
| 1 | 1 | 动作1 | 跑步 |  | 跑步机 / 跑步机 | 0.65 | ok |  |
| 1 | 2 | 动作2 | 史密斯机深蹲 | 7 | 史密斯机 / 史密斯深蹲 | 0.95 | ok |  |
| 1 | 3 | 动作3 | 悬垂举腿 | 7 | 引体向上架 / 引体向上 | 0.85 | ok |  |
| 2 | 1 | 动作1 | 卧推 | 8 | 史密斯机 / 史密斯卧推 | 0.95 | ok |  |
| 2 | 2 | 动作2 | 高位宽距下拉 | 3 10 | 高位下拉机 / 高位下拉 | 0.95 | ok |  |
| 2 | 3 | 动作3 | 高位V把下拉 | 11 | 高位下拉机 / 高位下拉 | 0.85 | ok |  |
| 2 | 4 | 动作4 | 绳索直杆下压·1 |  | 高位下拉机 / 高位下拉 | 0.9 | ok |  |
| 2 | 5 | 动作5 | 绳索直杆下压·2 | 10 6  | 龙门架 / 绳索下压 | 0.95 | ok |  |
| 2 | 6 | 动作6 | 绳索直杆下压·3 | 10 | 高位下拉机 / 高位下拉 | 0.85 | ok |  |
| 2 | 7 | 动作7 | 划船 | 11 | 悍马机 / 固定器械推肩 | 0.85 | ok |  |
| 2 | 8 | 动作8 | 上斜推胸 | 9 | 高位下拉机 / 高位下拉 | 0.85 | ok |  |
| 3 | 1 | 动作1+动作2 | 史密斯卧推 | 10 10 | 史密斯机 / 史密斯卧推 | 0.9 | count_mismatch |  |
| 3 | 2 | 动作3+动作4+动作5+动作6 | 水平哑铃卧推 | 12 10 11 | 哑铃 / 哑铃卧推 | 0.85 | count_mismatch |  |
| 3 | 3 | 动作7 | 上斜 30 度哑铃卧推 | 14 | 史密斯机 / 史密斯卧推 | 0.85 | count_mismatch |  |
| 3 | 4 | 动作8 | 哑铃卧推 | 7 4 | 龙门架 / 绳索下压 | 0.85 | count_mismatch |  |
| 3 | 5 | 动作9 | 上斜史密斯卧推 | 8 | 高位下拉机 / 高位下拉 | 0.95 | count_mismatch |  |
| 3 | 6 | 动作10+动作11 | 器械夹胸 | 10 10 10 | 龙门架 / 绳索下压 | 0.85 | count_mismatch |  |
| 3 | 7 |  | 直杆绳索下压 | 10 10 10 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 3 | 8 |  | 绳索下拉 | 5 2 6 6 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 4 | 1 | 动作1 | 宽距高位下拉 | 10 10 10 | 高位下拉机 / 高位下拉 | 0.95 | count_mismatch |  |
| 4 | 2 | 动作2 | 坐姿划船 | 10 10 10 | 坐姿划船机 / 坐姿绳索划船 | 0.9 | count_mismatch |  |
| 4 | 3 | 动作3 | 反握器械高位下拉 | 8 10 10 | 龙门架 / 绳索夹胸 | 0.75 | count_mismatch |  |
| 4 | 4 | 动作4 | 绳索直臂下压 | 5 6 7 7 | 龙门架 / 高位下拉 | 0.85 | count_mismatch |  |
| 4 | 5 | 动作5+动作6 | 杠铃弯举 | 6 3 5 5 | 龙门架 / 绳索下压 | 0.9 | count_mismatch |  |
| 4 | 6 | 动作7 | 哑铃弯举 | 7 5 6 | 杠铃 / 杠铃弯举 | 0.9 | count_mismatch |  |
| 4 | 7 | 动作8 |  |  | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | count_mismatch | graph_image_extra_without_ground_truth |
| 4 | 8 | 动作9 |  |  | 哑铃 / 哑铃侧平举 | 0.85 | count_mismatch | graph_image_extra_without_ground_truth |
| 4 | 9 | 动作10 |  |  | 哑铃 / 哑铃罗马尼亚硬拉 | 0.85 | count_mismatch | graph_image_extra_without_ground_truth |
| 8 | 1 | 动作1+动作2 | 跑步 |  | 跑步机 / 跑步机 | 0.85 | count_mismatch |  |
| 8 | 2 | 动作3 | 爬楼 |  | 固定器械坐姿划船机 / 固定器械坐姿划船 | 0.85 | count_mismatch |  |
| 8 | 3 | 动作4+动作5 | 夹胸 | 15 | 高位下拉机 / 高位下拉 | 0.9 | count_mismatch |  |
| 8 | 4 | 动作6 | 杠铃弯举 | 4 | 龙门架 / 绳索下压 | 0.85 | count_mismatch |  |
| 8 | 5 | 动作7 | 史密斯卧推 | 2 5 5 | 高位下拉机 / 高位下拉 | 0.95 | count_mismatch |  |
| 8 | 6 | 动作8 | 举腿 | 7 4 | 跑步机 / 跑步机 | 0.95 | count_mismatch |  |
| 8 | 7 | 动作9 | 直杆高位下拉 | 10 | 固定器械推胸机 / 固定器械推胸 | 0.85 | count_mismatch |  |
| 8 | 8 |  | 划船 | 9 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 9 | 1 | 动作1 | 爬楼机 |  | 跑步机 / 跑步机 | 0.95 | ok |  |
| 9 | 2 | 动作2 | 直杆高位下拉 | 10 10 10 | 高位下拉机 / 高位下拉 | 0.92 | ok |  |
| 9 | 3 | 动作3 | 绳索上拉 | 9 11 10 | 龙门架 / 绳索下压 | 0.85 | ok |  |
| 9 | 4 | 动作4 | 坐姿划船（V型把手） | 10 11 10 | 龙门架 / 绳索夹胸 | 0.85 | ok |  |
| 9 | 5 | 动作5+动作6 | 绳索下拉 | 10 10 10 | 龙门架 / 绳索下压 | 0.85 | ok |  |
| 健身-高孟琦 | 1 | 动作1 | 哑铃侧举 | 10 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | count_mismatch |  |
| 健身-高孟琦 | 2 | 动作2 | 哑铃夹胸 | 3 | 史密斯机 / 史密斯卧推 | 0.9 | count_mismatch |  |
| 健身-高孟琦 | 3 | 动作3 | 杠铃卧推 | 2 | 龙门架 / 绳索下压 | 0.95 | count_mismatch |  |
| 健身-高孟琦 | 4 |  | 绳索下拉 | 11 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 张靖义-2026.06.11 | 1 | 动作1 | 热身 |  | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.0 | ok |  |
| 张靖义-2026.06.11 | 2 | 动作2 | 热身 |  | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | ok |  |
| 张靖义-2026.06.11 | 3 | 动作3 | 肩背练习 | 13 12 14 12 25 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.3 | ok |  |
| 张靖义-2026.06.11 | 4 | 动作4 | 提拉杠铃 | 13 14 | 杠铃 / 杠铃卧推 | 0.85 | ok |  |
| 张靖义-2026.06.11 | 5 | 动作5 | 举重 | 8 | 哑铃 / 哑铃弯举 | 0.85 | ok |  |
| 张靖义-2026.06.11 | 6 | 动作6 | 哑铃卧推 | 11 13 11 | 哑铃 / 哑铃卧推 | 0.65 | ok |  |
| 张靖义-2026.06.11 | 7 | 动作7 | 反向推肩 | 12 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | ok |  |
| 张靖义-2026.06.11 | 8 | 动作8 | 夹胸 | 9 10 12 | 龙门架 / 绳索夹胸 | 0.85 | ok |  |
| 张靖义-2026.06.11 | 9 | 动作9 | 拉伸 |  | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | ok |  |
| 手臂-胸-杨博宇 | 1 | 动作1 | 热身 |  | 跑步机 / 跑步机 | 0.95 | ok |  |
| 手臂-胸-杨博宇 | 2 | 动作2 | 杠铃弯举 | 5 5 | 杠铃 / 杠铃弯举 | 0.85 | ok |  |
| 手臂-胸-杨博宇 | 3 | 动作3 | 哑铃弯举 | 10 11 9 38 | 哑铃 / 哑铃卧推 | 0.85 | ok |  |
| 手臂-胸-杨博宇 | 4 | 动作4 | 蝴蝶机飞鸟 | 15 | 哑铃 / 哑铃弯举 | 0.95 | ok |  |
| 手臂-胸-杨博宇 | 5 | 动作5 | 器械弯举 | 2 | 哑铃 / 哑铃弯举 | 0.85 | ok |  |
| 手臂-胸-杨博宇 | 6 | 动作6 | 器械推胸 | 5 5 | 跑步机 / 跑步机 | 0.92 | ok |  |
| 肩-秦紫渝 | 1 | 动作1 | 跑步 |  | 登阶机/爬楼机 / 登阶机/爬楼机 | 0.95 | count_mismatch |  |
| 肩-秦紫渝 | 2 | 动作2+动作3+动作4+动作5+动作6 | 绳索下拉 | 10 10 10 10 | 龙门架 / 绳索下压 | 0.85 | count_mismatch |  |
| 肩-秦紫渝 | 3 |  | 绳索上拉 | 11 10 10 10 11 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 肩-秦紫渝 | 4 |  | 单臂绳索下拉 | 10 7 10 10 9 7 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 肩-背-秦紫渝 | 1 | 动作1 | 热身（跑步机） |  | 跑步机 / 跑步机 | 0.95 | count_mismatch |  |
| 肩-背-秦紫渝 | 2 | 动作2+动作3 | 高位下拉 | 11 11 11 | 高位下拉机 / 高位下拉 | 0.85 | count_mismatch |  |
| 肩-背-秦紫渝 | 3 | 动作4 | 坐姿划船 | 5 10 9 21 | 龙门架 / 绳索下压 | 0.95 | count_mismatch |  |
| 肩-背-秦紫渝 | 4 | 动作5 | 面拉 | 11 10 10 | 登阶机 / 登阶机/爬楼机 | 0.95 | count_mismatch |  |
| 肩-背-秦紫渝 | 5 |  | 蝴蝶机反向飞鸟 | 2 8 |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 肩-背-秦紫渝 | 6 |  | 拉伸（跑步机） |  |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 肩背-叶翔 | 1 | 动作1 | 爬楼机 |  | 登阶机 / 登阶机/爬楼机 | 0.85 | count_mismatch |  |
| 肩背-叶翔 | 2 | 动作2 | 直杆高位下拉 | 12 12 12 11 | 高位下拉机 / 高位下拉 | 0.95 | count_mismatch |  |
| 肩背-叶翔 | 3 | 动作3+动作4 | 绳索面拉 | 5 2 4 10 10 | 龙门架 / 绳索下压 | 0.8 | count_mismatch |  |
| 肩背-叶翔 | 4 | 动作5 | 坐姿划船 | 10 10 10 | 龙门架 / 绳索弯举 | 0.85 | count_mismatch |  |
| 肩背-叶翔 | 5 | 动作6 | 拉伸 |  | 龙门架 / 绳索下压 | 0.85 | count_mismatch |  |
| 肩背-叶翔 | 6 | 动作7 |  |  | 龙门架 / 绳索下压 | 0.55 | count_mismatch | graph_image_extra_without_ground_truth |
| 肩背-叶翔 | 7 | 动作8+动作9 |  |  | 龙门架 / 绳索下压 | 0.85 | count_mismatch | graph_image_extra_without_ground_truth |
| 肩背-叶翔 | 8 | 动作10+动作11 |  |  | 龙门架 / 坐姿绳索划船 | 0.95 | count_mismatch | graph_image_extra_without_ground_truth |
| 腿-张开 | 1 | 动作1 | 热身 |  | 椭圆机 / 椭圆机 | 0.85 | count_mismatch |  |
| 腿-张开 | 2 | 动作2 | 杠铃深蹲 | 6 5 5 | 史密斯机 / 史密斯深蹲 | 0.95 | count_mismatch |  |
| 腿-张开 | 3 | 动作3+动作4 | 坐姿腿屈伸 | 2 | 杠铃 / 杠铃深蹲 | 0.95 | count_mismatch |  |
| 腿-张开 | 4 | 动作5 | 未知动作（无器材 ） |  | 坐姿腿屈伸机 / 坐姿腿屈伸 | 0.92 | count_mismatch |  |
| 腿-张开 | 5 | 动作6 | 未知动作（无器材 ） |  | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.45 | count_mismatch |  |
| 腿-张开 | 6 | 动作7 | 腿举 | 9 8 | 腿举机 / 腿举 | 0.95 | count_mismatch |  |
| 腿-张开 | 7 | 动作8 | 推拉 | 3 | 龙门架 / 绳索夹胸 | 0.75 | count_mismatch |  |
| 腿-张开 | 8 |  | 反向推胸 |  |  |  | count_mismatch | ground_truth_extra_without_graph_group |
| 腿-张开 | 9 |  | 拉伸 |  |  |  | count_mismatch | ground_truth_extra_without_graph_group |
