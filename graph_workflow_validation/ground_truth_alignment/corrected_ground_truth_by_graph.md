# Corrected Ground Truth By Graph Image

这份文件按用户人工审阅结果修正 ground truth。人工提到的图覆盖原标注；未提到的图沿用原始/合并后的 ground truth 对齐结果；明确删除的图才标记为 `deleted_by_user`。

## Grouped View

| folder | graph actions | corrected ground truth | status | model predictions |
|---|---|---|---|---|
| 3 | 动作1+动作2 | 史密斯卧推 | corrected_by_user | 史密斯卧推(0.9)<br>史密斯卧推(0.95) |
| 3 | 动作3+动作4 | 水平哑铃卧推 | base_ground_truth_kept | 哑铃卧推(0.85)<br>哑铃卧推(0.85) |
| 3 | 动作5+动作6 | 哑铃卧推 | corrected_by_user | 哑铃卧推(0.85)<br>哑铃卧推(0.85) |
| 3 | 动作7 | 上斜 30 度哑铃卧推 | base_ground_truth_kept | 史密斯卧推(0.85) |
| 3 | 动作8 | 哑铃卧推 | base_ground_truth_kept | 绳索下压(0.85) |
| 3 | 动作9 | 上斜史密斯卧推 | base_ground_truth_kept | 高位下拉(0.95) |
| 3 | 动作10+动作11 | 绳索下拉 | corrected_by_user | 绳索下压(0.95)<br>绳索下压(0.85) |
| 4 | 动作1 | 宽距高位下拉 | base_ground_truth_kept | 高位下拉(0.95) |
| 4 | 动作2 | 坐姿划船 | base_ground_truth_kept | 坐姿绳索划船(0.9) |
| 4 | 动作3+动作4 | 反握器械高位下拉 | corrected_by_user | 绳索夹胸(0.75)<br>高位下拉(0.85) |
| 4 | 动作5+动作6 | 绳索锤式弯举 | corrected_by_user | 绳索下压(0.95)<br>绳索下压(0.9) |
| 4 | 动作7+动作8 | 杠铃弯举 | corrected_by_user | 杠铃弯举(0.9)<br>UNKNOWN_ACTION(0.2) |
| 4 | 动作9+动作10 | 哑铃弯举 | corrected_by_user | 哑铃侧平举(0.85)<br>哑铃罗马尼亚硬拉(0.85) |
| 8 | 动作1+动作2 | 跑步 | base_ground_truth_kept | 跑步机(0.95)<br>跑步机(0.85) |
| 8 | 动作3 | 爬楼 | base_ground_truth_kept | 固定器械坐姿划船(0.85) |
| 8 | 动作4+动作5 | 史密斯卧推 | corrected_by_user | 高位下拉(0.9)<br>高位下拉(0.92) |
| 8 | 动作6 | 杠铃弯举 | base_ground_truth_kept | 绳索下压(0.85) |
| 8 | 动作7 | 史密斯卧推 | base_ground_truth_kept | 高位下拉(0.95) |
| 8 | 动作8 | 划船 | corrected_by_user | 跑步机(0.95) |
| 8 | 动作9 | 夹胸 | corrected_by_user | 固定器械推胸(0.85) |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | corrected_by_user | UNKNOWN_ACTION(0.1) |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | corrected_by_user | 史密斯卧推(0.9) |
| 健身-高孟琦 | 动作3 | 绳索下压 | corrected_by_user | 绳索下压(0.95) |
| 肩-秦紫渝 | 动作1 | 跑步 | base_ground_truth_kept | 登阶机/爬楼机(0.95) |
| 肩-秦紫渝 | 动作2+动作3 | 绳索下拉 | base_ground_truth_kept | 绳索下压(0.85)<br>绳索下压(0.85) |
| 肩-秦紫渝 | 动作4+动作5 | 单臂绳索下拉 | corrected_by_user | 绳索下压(0.85)<br>绳索下压(0.85) |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | base_ground_truth_kept | 绳索下压(0.85) |
| 肩-背-秦紫渝 | 动作1 | 热身（跑步机） | base_ground_truth_kept | 跑步机(0.95) |
| 肩-背-秦紫渝 | 动作2+动作3 | 高位下拉 | base_ground_truth_kept | 高位下拉(0.95)<br>高位下拉(0.85) |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | corrected_by_user | 绳索下压(0.95) |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | corrected_by_user | 登阶机/爬楼机(0.95) |
| 肩背-叶翔 | 动作1 | 爬楼机 | base_ground_truth_kept | 登阶机/爬楼机(0.85) |
| 肩背-叶翔 | 动作2+动作3+动作4+动作5 | 直杆高位下拉 | corrected_by_user | 高位下拉(0.95)<br>绳索下压(0.8)<br>绳索下压(0.85)<br>绳索弯举(0.85) |
| 肩背-叶翔 | 动作6+动作7+动作8+动作9 | 绳索面拉 | corrected_by_user | 绳索下压(0.85)<br>绳索下压(0.55)<br>绳索下压(0.92)<br>绳索下压(0.85) |
| 肩背-叶翔 | 动作10+动作11 | 坐姿划船 | corrected_by_user | 坐姿绳索划船(0.95)<br>坐姿绳索划船(0.95) |
| 腿-张开 | 动作1 | 跑步机 | corrected_by_user | 椭圆机(0.85) |
| 腿-张开 | 动作2+动作3+动作4 | 杠铃深蹲 | corrected_by_user | 史密斯深蹲(0.95)<br>杠铃深蹲(0.95)<br>杠铃深蹲(0.95) |
| 腿-张开 | 动作5 | 坐姿腿屈伸 | corrected_by_user | 坐姿腿屈伸(0.92) |
| 腿-张开 | 动作6 | 未知动作 | corrected_by_user | UNKNOWN_ACTION(0.45) |
| 腿-张开 | 动作7 | 倒蹬机 | corrected_by_user | 腿举(0.95) |
| 腿-张开 | 动作8 | 未知动作 | corrected_by_user | 绳索夹胸(0.75) |

## Action-Level View

| folder | action | corrected ground truth | status | prediction | conf |
|---|---|---|---|---|---:|
| 3 | 动作1 | 史密斯卧推 | corrected_by_user | 史密斯机 / 史密斯卧推 | 0.9 |
| 3 | 动作2 | 史密斯卧推 | corrected_by_user | 史密斯机 / 史密斯卧推 | 0.95 |
| 3 | 动作3 | 水平哑铃卧推 | base_ground_truth_kept | 哑铃 / 哑铃卧推 | 0.85 |
| 3 | 动作4 | 水平哑铃卧推 | base_ground_truth_kept | 哑铃 / 哑铃卧推 | 0.85 |
| 3 | 动作5 | 哑铃卧推 | corrected_by_user | 哑铃 / 哑铃卧推 | 0.85 |
| 3 | 动作6 | 哑铃卧推 | corrected_by_user | 哑铃 / 哑铃卧推 | 0.85 |
| 3 | 动作7 | 上斜 30 度哑铃卧推 | base_ground_truth_kept | 史密斯机 / 史密斯卧推 | 0.85 |
| 3 | 动作8 | 哑铃卧推 | base_ground_truth_kept | 龙门架 / 绳索下压 | 0.85 |
| 3 | 动作9 | 上斜史密斯卧推 | base_ground_truth_kept | 高位下拉机 / 高位下拉 | 0.95 |
| 3 | 动作10 | 绳索下拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.95 |
| 3 | 动作11 | 绳索下拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.85 |
| 4 | 动作1 | 宽距高位下拉 | base_ground_truth_kept | 高位下拉机 / 高位下拉 | 0.95 |
| 4 | 动作2 | 坐姿划船 | base_ground_truth_kept | 坐姿划船机 / 坐姿绳索划船 | 0.9 |
| 4 | 动作3 | 反握器械高位下拉 | corrected_by_user | 龙门架 / 绳索夹胸 | 0.75 |
| 4 | 动作4 | 反握器械高位下拉 | corrected_by_user | 龙门架 / 高位下拉 | 0.85 |
| 4 | 动作5 | 绳索锤式弯举 | corrected_by_user | 龙门架 / 绳索下压 | 0.95 |
| 4 | 动作6 | 绳索锤式弯举 | corrected_by_user | 龙门架 / 绳索下压 | 0.9 |
| 4 | 动作7 | 杠铃弯举 | corrected_by_user | 杠铃 / 杠铃弯举 | 0.9 |
| 4 | 动作8 | 杠铃弯举 | corrected_by_user | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 |
| 4 | 动作9 | 哑铃弯举 | corrected_by_user | 哑铃 / 哑铃侧平举 | 0.85 |
| 4 | 动作10 | 哑铃弯举 | corrected_by_user | 哑铃 / 哑铃罗马尼亚硬拉 | 0.85 |
| 8 | 动作1 | 跑步 | base_ground_truth_kept | 跑步机 / 跑步机 | 0.95 |
| 8 | 动作2 | 跑步 | base_ground_truth_kept | 跑步机 / 跑步机 | 0.85 |
| 8 | 动作3 | 爬楼 | base_ground_truth_kept | 固定器械坐姿划船机 / 固定器械坐姿划船 | 0.85 |
| 8 | 动作4 | 史密斯卧推 | corrected_by_user | 高位下拉机 / 高位下拉 | 0.9 |
| 8 | 动作5 | 史密斯卧推 | corrected_by_user | 高位下拉机 / 高位下拉 | 0.92 |
| 8 | 动作6 | 杠铃弯举 | base_ground_truth_kept | 龙门架 / 绳索下压 | 0.85 |
| 8 | 动作7 | 史密斯卧推 | base_ground_truth_kept | 高位下拉机 / 高位下拉 | 0.95 |
| 8 | 动作8 | 划船 | corrected_by_user | 跑步机 / 跑步机 | 0.95 |
| 8 | 动作9 | 夹胸 | corrected_by_user | 固定器械推胸机 / 固定器械推胸 | 0.85 |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | corrected_by_user | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | corrected_by_user | 史密斯机 / 史密斯卧推 | 0.9 |
| 健身-高孟琦 | 动作3 | 绳索下压 | corrected_by_user | 龙门架 / 绳索下压 | 0.95 |
| 肩-秦紫渝 | 动作1 | 跑步 | base_ground_truth_kept | 登阶机/爬楼机 / 登阶机/爬楼机 | 0.95 |
| 肩-秦紫渝 | 动作2 | 绳索下拉 | base_ground_truth_kept | 龙门架 / 绳索下压 | 0.85 |
| 肩-秦紫渝 | 动作3 | 绳索下拉 | base_ground_truth_kept | 龙门架 / 绳索下压 | 0.85 |
| 肩-秦紫渝 | 动作4 | 单臂绳索下拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.85 |
| 肩-秦紫渝 | 动作5 | 单臂绳索下拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.85 |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | base_ground_truth_kept | 龙门架 / 绳索下压 | 0.85 |
| 肩-背-秦紫渝 | 动作1 | 热身（跑步机） | base_ground_truth_kept | 跑步机 / 跑步机 | 0.95 |
| 肩-背-秦紫渝 | 动作2 | 高位下拉 | base_ground_truth_kept | 高位下拉机 / 高位下拉 | 0.95 |
| 肩-背-秦紫渝 | 动作3 | 高位下拉 | base_ground_truth_kept | 高位下拉机 / 高位下拉 | 0.85 |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | corrected_by_user | 龙门架 / 绳索下压 | 0.95 |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | corrected_by_user | 登阶机 / 登阶机/爬楼机 | 0.95 |
| 肩背-叶翔 | 动作1 | 爬楼机 | base_ground_truth_kept | 登阶机 / 登阶机/爬楼机 | 0.85 |
| 肩背-叶翔 | 动作2 | 直杆高位下拉 | corrected_by_user | 高位下拉机 / 高位下拉 | 0.95 |
| 肩背-叶翔 | 动作3 | 直杆高位下拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.8 |
| 肩背-叶翔 | 动作4 | 直杆高位下拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.85 |
| 肩背-叶翔 | 动作5 | 直杆高位下拉 | corrected_by_user | 龙门架 / 绳索弯举 | 0.85 |
| 肩背-叶翔 | 动作6 | 绳索面拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.85 |
| 肩背-叶翔 | 动作7 | 绳索面拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.55 |
| 肩背-叶翔 | 动作8 | 绳索面拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.92 |
| 肩背-叶翔 | 动作9 | 绳索面拉 | corrected_by_user | 龙门架 / 绳索下压 | 0.85 |
| 肩背-叶翔 | 动作10 | 坐姿划船 | corrected_by_user | 龙门架 / 坐姿绳索划船 | 0.95 |
| 肩背-叶翔 | 动作11 | 坐姿划船 | corrected_by_user | 龙门架 / 坐姿绳索划船 | 0.95 |
| 腿-张开 | 动作1 | 跑步机 | corrected_by_user | 椭圆机 / 椭圆机 | 0.85 |
| 腿-张开 | 动作2 | 杠铃深蹲 | corrected_by_user | 史密斯机 / 史密斯深蹲 | 0.95 |
| 腿-张开 | 动作3 | 杠铃深蹲 | corrected_by_user | 杠铃 / 杠铃深蹲 | 0.95 |
| 腿-张开 | 动作4 | 杠铃深蹲 | corrected_by_user | 杠铃 / 杠铃深蹲 | 0.95 |
| 腿-张开 | 动作5 | 坐姿腿屈伸 | corrected_by_user | 坐姿腿屈伸机 / 坐姿腿屈伸 | 0.92 |
| 腿-张开 | 动作6 | 未知动作 | corrected_by_user | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.45 |
| 腿-张开 | 动作7 | 倒蹬机 | corrected_by_user | 腿举机 / 腿举 | 0.95 |
| 腿-张开 | 动作8 | 未知动作 | corrected_by_user | 龙门架 / 绳索夹胸 | 0.75 |
