# Corrected Prediction Comparison

Comparison of Gemini predictions against user-corrected graph-level ground truth. Unmentioned actions keep base ground truth alignment; manual corrections override it. normalized_match uses alias map for obvious naming granularity differences.

Total evaluated: 63
Normalized matches: 24
Mismatches: 39

## By Folder

| folder | total | match | mismatch |
|---|---:|---:|---:|
| 3 | 11 | 6 | 5 |
| 4 | 10 | 3 | 7 |
| 8 | 9 | 2 | 7 |
| 健身-高孟琦 | 3 | 1 | 2 |
| 肩-秦紫渝 | 6 | 0 | 6 |
| 肩-背-秦紫渝 | 5 | 3 | 2 |
| 肩背-叶翔 | 11 | 4 | 7 |
| 腿-张开 | 8 | 5 | 3 |

## Mismatches

| folder | action | ground truth | prediction | conf | normalized GT | normalized pred | correction status |
|---|---|---|---|---:|---|---|---|
| 3 | 动作7 | 上斜 30 度哑铃卧推 | 史密斯机 / 史密斯卧推 | 0.85 | 哑铃卧推 | 史密斯卧推 | base_ground_truth_kept |
| 3 | 动作8 | 哑铃卧推 | 龙门架 / 绳索下压 | 0.85 | 哑铃卧推 | 绳索下压 | base_ground_truth_kept |
| 3 | 动作9 | 上斜史密斯卧推 | 高位下拉机 / 高位下拉 | 0.95 | 史密斯卧推 | 高位下拉 | base_ground_truth_kept |
| 3 | 动作10 | 绳索下拉 | 龙门架 / 绳索下压 | 0.95 | 绳索下拉 | 绳索下压 | corrected_by_user |
| 3 | 动作11 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 绳索下拉 | 绳索下压 | corrected_by_user |
| 4 | 动作1 | 宽距高位下拉 | 高位下拉机 / 高位下拉 | 0.95 | 宽距高位下拉 | 高位下拉 | base_ground_truth_kept |
| 4 | 动作3 | 反握器械高位下拉 | 龙门架 / 绳索夹胸 | 0.75 | 高位下拉 | 夹胸 | corrected_by_user |
| 4 | 动作5 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.95 | 绳索锤式弯举 | 绳索下压 | corrected_by_user |
| 4 | 动作6 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.9 | 绳索锤式弯举 | 绳索下压 | corrected_by_user |
| 4 | 动作8 | 杠铃弯举 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | 杠铃弯举 | 未知动作 | corrected_by_user |
| 4 | 动作9 | 哑铃弯举 | 哑铃 / 哑铃侧平举 | 0.85 | 哑铃弯举 | 哑铃侧举 | corrected_by_user |
| 4 | 动作10 | 哑铃弯举 | 哑铃 / 哑铃罗马尼亚硬拉 | 0.85 | 哑铃弯举 | 哑铃罗马尼亚硬拉 | corrected_by_user |
| 8 | 动作3 | 爬楼 | 固定器械坐姿划船机 / 固定器械坐姿划船 | 0.85 | 爬楼机 | 划船 | base_ground_truth_kept |
| 8 | 动作4 | 史密斯卧推 | 高位下拉机 / 高位下拉 | 0.9 | 史密斯卧推 | 高位下拉 | corrected_by_user |
| 8 | 动作5 | 史密斯卧推 | 高位下拉机 / 高位下拉 | 0.92 | 史密斯卧推 | 高位下拉 | corrected_by_user |
| 8 | 动作6 | 杠铃弯举 | 龙门架 / 绳索下压 | 0.85 | 杠铃弯举 | 绳索下压 | base_ground_truth_kept |
| 8 | 动作7 | 史密斯卧推 | 高位下拉机 / 高位下拉 | 0.95 | 史密斯卧推 | 高位下拉 | base_ground_truth_kept |
| 8 | 动作8 | 划船 | 跑步机 / 跑步机 | 0.95 | 划船 | 跑步 | corrected_by_user |
| 8 | 动作9 | 夹胸 | 固定器械推胸机 / 固定器械推胸 | 0.85 | 夹胸 | 推胸 | corrected_by_user |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | 哑铃深蹲 | 未知动作 | corrected_by_user |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | 史密斯机 / 史密斯卧推 | 0.9 | 高位下拉 | 史密斯卧推 | corrected_by_user |
| 肩-秦紫渝 | 动作1 | 跑步 | 登阶机/爬楼机 / 登阶机/爬楼机 | 0.95 | 跑步 | 爬楼机 | base_ground_truth_kept |
| 肩-秦紫渝 | 动作2 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 绳索下拉 | 绳索下压 | base_ground_truth_kept |
| 肩-秦紫渝 | 动作3 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 绳索下拉 | 绳索下压 | base_ground_truth_kept |
| 肩-秦紫渝 | 动作4 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 单臂绳索下拉 | 绳索下压 | corrected_by_user |
| 肩-秦紫渝 | 动作5 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 单臂绳索下拉 | 绳索下压 | corrected_by_user |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 绳索下拉 | 绳索下压 | base_ground_truth_kept |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | 龙门架 / 绳索下压 | 0.95 | 划船 | 绳索下压 | corrected_by_user |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | 登阶机 / 登阶机/爬楼机 | 0.95 | 拉伸/跑步机 | 爬楼机 | corrected_by_user |
| 肩背-叶翔 | 动作3 | 直杆高位下拉 | 龙门架 / 绳索下压 | 0.8 | 高位下拉 | 绳索下压 | corrected_by_user |
| 肩背-叶翔 | 动作4 | 直杆高位下拉 | 龙门架 / 绳索下压 | 0.85 | 高位下拉 | 绳索下压 | corrected_by_user |
| 肩背-叶翔 | 动作5 | 直杆高位下拉 | 龙门架 / 绳索弯举 | 0.85 | 高位下拉 | 绳索锤式弯举 | corrected_by_user |
| 肩背-叶翔 | 动作6 | 绳索面拉 | 龙门架 / 绳索下压 | 0.85 | 面拉 | 绳索下压 | corrected_by_user |
| 肩背-叶翔 | 动作7 | 绳索面拉 | 龙门架 / 绳索下压 | 0.55 | 面拉 | 绳索下压 | corrected_by_user |
| 肩背-叶翔 | 动作8 | 绳索面拉 | 龙门架 / 绳索下压 | 0.92 | 面拉 | 绳索下压 | corrected_by_user |
| 肩背-叶翔 | 动作9 | 绳索面拉 | 龙门架 / 绳索下压 | 0.85 | 面拉 | 绳索下压 | corrected_by_user |
| 腿-张开 | 动作1 | 跑步机 | 椭圆机 / 椭圆机 | 0.85 | 跑步 | 椭圆机 | corrected_by_user |
| 腿-张开 | 动作2 | 杠铃深蹲 | 史密斯机 / 史密斯深蹲 | 0.95 | 杠铃深蹲 | 史密斯深蹲 | corrected_by_user |
| 腿-张开 | 动作8 | 未知动作 | 龙门架 / 绳索夹胸 | 0.75 | 未知动作 | 夹胸 | corrected_by_user |

## All Rows

| folder | action | ground truth | prediction | conf | status | correction status |
|---|---|---|---|---:|---|---|
| 3 | 动作1 | 史密斯卧推 | 史密斯机 / 史密斯卧推 | 0.9 | match | corrected_by_user |
| 3 | 动作2 | 史密斯卧推 | 史密斯机 / 史密斯卧推 | 0.95 | match | corrected_by_user |
| 3 | 动作3 | 水平哑铃卧推 | 哑铃 / 哑铃卧推 | 0.85 | match | base_ground_truth_kept |
| 3 | 动作4 | 水平哑铃卧推 | 哑铃 / 哑铃卧推 | 0.85 | match | base_ground_truth_kept |
| 3 | 动作5 | 哑铃卧推 | 哑铃 / 哑铃卧推 | 0.85 | match | corrected_by_user |
| 3 | 动作6 | 哑铃卧推 | 哑铃 / 哑铃卧推 | 0.85 | match | corrected_by_user |
| 3 | 动作7 | 上斜 30 度哑铃卧推 | 史密斯机 / 史密斯卧推 | 0.85 | mismatch | base_ground_truth_kept |
| 3 | 动作8 | 哑铃卧推 | 龙门架 / 绳索下压 | 0.85 | mismatch | base_ground_truth_kept |
| 3 | 动作9 | 上斜史密斯卧推 | 高位下拉机 / 高位下拉 | 0.95 | mismatch | base_ground_truth_kept |
| 3 | 动作10 | 绳索下拉 | 龙门架 / 绳索下压 | 0.95 | mismatch | corrected_by_user |
| 3 | 动作11 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | corrected_by_user |
| 4 | 动作1 | 宽距高位下拉 | 高位下拉机 / 高位下拉 | 0.95 | mismatch | base_ground_truth_kept |
| 4 | 动作2 | 坐姿划船 | 坐姿划船机 / 坐姿绳索划船 | 0.9 | match | base_ground_truth_kept |
| 4 | 动作3 | 反握器械高位下拉 | 龙门架 / 绳索夹胸 | 0.75 | mismatch | corrected_by_user |
| 4 | 动作4 | 反握器械高位下拉 | 龙门架 / 高位下拉 | 0.85 | match | corrected_by_user |
| 4 | 动作5 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.95 | mismatch | corrected_by_user |
| 4 | 动作6 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.9 | mismatch | corrected_by_user |
| 4 | 动作7 | 杠铃弯举 | 杠铃 / 杠铃弯举 | 0.9 | match | corrected_by_user |
| 4 | 动作8 | 杠铃弯举 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | mismatch | corrected_by_user |
| 4 | 动作9 | 哑铃弯举 | 哑铃 / 哑铃侧平举 | 0.85 | mismatch | corrected_by_user |
| 4 | 动作10 | 哑铃弯举 | 哑铃 / 哑铃罗马尼亚硬拉 | 0.85 | mismatch | corrected_by_user |
| 8 | 动作1 | 跑步 | 跑步机 / 跑步机 | 0.95 | match | base_ground_truth_kept |
| 8 | 动作2 | 跑步 | 跑步机 / 跑步机 | 0.85 | match | base_ground_truth_kept |
| 8 | 动作3 | 爬楼 | 固定器械坐姿划船机 / 固定器械坐姿划船 | 0.85 | mismatch | base_ground_truth_kept |
| 8 | 动作4 | 史密斯卧推 | 高位下拉机 / 高位下拉 | 0.9 | mismatch | corrected_by_user |
| 8 | 动作5 | 史密斯卧推 | 高位下拉机 / 高位下拉 | 0.92 | mismatch | corrected_by_user |
| 8 | 动作6 | 杠铃弯举 | 龙门架 / 绳索下压 | 0.85 | mismatch | base_ground_truth_kept |
| 8 | 动作7 | 史密斯卧推 | 高位下拉机 / 高位下拉 | 0.95 | mismatch | base_ground_truth_kept |
| 8 | 动作8 | 划船 | 跑步机 / 跑步机 | 0.95 | mismatch | corrected_by_user |
| 8 | 动作9 | 夹胸 | 固定器械推胸机 / 固定器械推胸 | 0.85 | mismatch | corrected_by_user |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | mismatch | corrected_by_user |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | 史密斯机 / 史密斯卧推 | 0.9 | mismatch | corrected_by_user |
| 健身-高孟琦 | 动作3 | 绳索下压 | 龙门架 / 绳索下压 | 0.95 | match | corrected_by_user |
| 肩-秦紫渝 | 动作1 | 跑步 | 登阶机/爬楼机 / 登阶机/爬楼机 | 0.95 | mismatch | base_ground_truth_kept |
| 肩-秦紫渝 | 动作2 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | base_ground_truth_kept |
| 肩-秦紫渝 | 动作3 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | base_ground_truth_kept |
| 肩-秦紫渝 | 动作4 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | corrected_by_user |
| 肩-秦紫渝 | 动作5 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | corrected_by_user |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | base_ground_truth_kept |
| 肩-背-秦紫渝 | 动作1 | 热身（跑步机） | 跑步机 / 跑步机 | 0.95 | match | base_ground_truth_kept |
| 肩-背-秦紫渝 | 动作2 | 高位下拉 | 高位下拉机 / 高位下拉 | 0.95 | match | base_ground_truth_kept |
| 肩-背-秦紫渝 | 动作3 | 高位下拉 | 高位下拉机 / 高位下拉 | 0.85 | match | base_ground_truth_kept |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | 龙门架 / 绳索下压 | 0.95 | mismatch | corrected_by_user |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | 登阶机 / 登阶机/爬楼机 | 0.95 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作1 | 爬楼机 | 登阶机 / 登阶机/爬楼机 | 0.85 | match | base_ground_truth_kept |
| 肩背-叶翔 | 动作2 | 直杆高位下拉 | 高位下拉机 / 高位下拉 | 0.95 | match | corrected_by_user |
| 肩背-叶翔 | 动作3 | 直杆高位下拉 | 龙门架 / 绳索下压 | 0.8 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作4 | 直杆高位下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作5 | 直杆高位下拉 | 龙门架 / 绳索弯举 | 0.85 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作6 | 绳索面拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作7 | 绳索面拉 | 龙门架 / 绳索下压 | 0.55 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作8 | 绳索面拉 | 龙门架 / 绳索下压 | 0.92 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作9 | 绳索面拉 | 龙门架 / 绳索下压 | 0.85 | mismatch | corrected_by_user |
| 肩背-叶翔 | 动作10 | 坐姿划船 | 龙门架 / 坐姿绳索划船 | 0.95 | match | corrected_by_user |
| 肩背-叶翔 | 动作11 | 坐姿划船 | 龙门架 / 坐姿绳索划船 | 0.95 | match | corrected_by_user |
| 腿-张开 | 动作1 | 跑步机 | 椭圆机 / 椭圆机 | 0.85 | mismatch | corrected_by_user |
| 腿-张开 | 动作2 | 杠铃深蹲 | 史密斯机 / 史密斯深蹲 | 0.95 | mismatch | corrected_by_user |
| 腿-张开 | 动作3 | 杠铃深蹲 | 杠铃 / 杠铃深蹲 | 0.95 | match | corrected_by_user |
| 腿-张开 | 动作4 | 杠铃深蹲 | 杠铃 / 杠铃深蹲 | 0.95 | match | corrected_by_user |
| 腿-张开 | 动作5 | 坐姿腿屈伸 | 坐姿腿屈伸机 / 坐姿腿屈伸 | 0.92 | match | corrected_by_user |
| 腿-张开 | 动作6 | 未知动作 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.45 | match | corrected_by_user |
| 腿-张开 | 动作7 | 倒蹬机 | 腿举机 / 腿举 | 0.95 | match | corrected_by_user |
| 腿-张开 | 动作8 | 未知动作 | 龙门架 / 绳索夹胸 | 0.75 | mismatch | corrected_by_user |
