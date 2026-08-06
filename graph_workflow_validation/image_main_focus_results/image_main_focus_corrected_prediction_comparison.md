# Image Main Focus Prediction Comparison

Prompt mode: `image-main-focus`
Total evaluated: 39
Matches: 6
Mismatches: 33
API errors: 0

## By Folder

| folder | total | match | mismatch | api_error |
|---|---:|---:|---:|---:|
| 3 | 5 | 0 | 5 | 0 |
| 4 | 7 | 2 | 5 | 0 |
| 8 | 7 | 0 | 7 | 0 |
| 健身-高孟琦 | 2 | 0 | 2 | 0 |
| 肩-秦紫渝 | 6 | 1 | 5 | 0 |
| 肩-背-秦紫渝 | 2 | 0 | 2 | 0 |
| 肩背-叶翔 | 7 | 1 | 6 | 0 |
| 腿-张开 | 3 | 2 | 1 | 0 |

## Rows

| folder | action | ground truth | prediction | conf | normalized GT | normalized pred | status |
|---|---|---|---|---:|---|---|---|
| 3 | 动作7 | 上斜 30 度哑铃卧推 | 史密斯机 / 史密斯卧推 | 0.85 | 哑铃卧推 | 史密斯卧推 | mismatch |
| 3 | 动作8 | 哑铃卧推 | 龙门架 / 绳索夹胸 | 0.85 | 哑铃卧推 | 夹胸 | mismatch |
| 3 | 动作9 | 上斜史密斯卧推 | 龙门架 / 高位下拉 | 0.95 | 史密斯卧推 | 高位下拉 | mismatch |
| 3 | 动作10 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 绳索下拉 | 绳索下压 | mismatch |
| 3 | 动作11 | 绳索下拉 | 龙门架 / 绳索下压 | 0.65 | 绳索下拉 | 绳索下压 | mismatch |
| 4 | 动作1 | 宽距高位下拉 | 龙门架 / 高位下拉 | 0.95 | 高位下拉 | 高位下拉 | match |
| 4 | 动作3 | 反握器械高位下拉 | 龙门架 / cable_chest_fly | 0.65 | 高位下拉 | 夹胸 | mismatch |
| 4 | 动作5 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.85 | 绳索锤式弯举 | 绳索下压 | mismatch |
| 4 | 动作6 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.92 | 绳索锤式弯举 | 绳索下压 | mismatch |
| 4 | 动作8 | 杠铃弯举 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.3 | 杠铃弯举 | 未知动作 | mismatch |
| 4 | 动作9 | 哑铃弯举 | 哑铃 / 哑铃弯举 | 0.92 | 哑铃弯举 | 哑铃弯举 | match |
| 4 | 动作10 | 哑铃弯举 | 哑铃 / dumbbell_lateral_raise | 0.65 | 哑铃弯举 | 哑铃侧举 | mismatch |
| 8 | 动作3 | 爬楼 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | 爬楼机 | 未知动作 | mismatch |
| 8 | 动作4 | 史密斯卧推 | 龙门架 / cable_lat_pulldown | 0.85 | 史密斯卧推 | 高位下拉 | mismatch |
| 8 | 动作5 | 史密斯卧推 | 龙门架 / cable_lat_pulldown | 0.92 | 史密斯卧推 | 高位下拉 | mismatch |
| 8 | 动作6 | 杠铃弯举 | 龙门架 / 绳索下压 | 0.65 | 杠铃弯举 | 绳索下压 | mismatch |
| 8 | 动作7 | 史密斯卧推 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.1 | 史密斯卧推 | 未知动作 | mismatch |
| 8 | 动作8 | 划船 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | 划船 | 未知动作 | mismatch |
| 8 | 动作9 | 夹胸 | 固定器械 / 固定器械推胸 | 0.85 | 夹胸 | 推胸 | mismatch |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | 哑铃深蹲 | 未知动作 | mismatch |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | 史密斯机 / smith_bench_press | 0.85 | 高位下拉 | 史密斯卧推 | mismatch |
| 肩-秦紫渝 | 动作1 | 跑步 | 跑步机 / 跑步机 | 0.95 | 跑步 | 跑步 | match |
| 肩-秦紫渝 | 动作2 | 绳索下拉 | 龙门架 / 绳索下压 | 0.9 | 绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作3 | 绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作4 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 单臂绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作5 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 单臂绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | 龙门架 / 绳索侧平举 | 0.65 | 绳索下拉 | 绳索侧举 | mismatch |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | 龙门架 / 绳索下压 | 0.92 | 绳索划船 | 绳索下压 | mismatch |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | 跑步机 / 跑步机 | 0.95 | 拉伸/跑步机 | 跑步 | mismatch |
| 肩背-叶翔 | 动作3 | 直杆高位下拉 | 龙门架 / cable_triceps_pushdown | 0.85 | 高位下拉 | 绳索下压 | mismatch |
| 肩背-叶翔 | 动作4 | 直杆高位下拉 | 龙门架 / 高位下拉 | 0.92 | 高位下拉 | 高位下拉 | match |
| 肩背-叶翔 | 动作5 | 直杆高位下拉 | 龙门架 / 绳索弯举 | 0.92 | 高位下拉 | 绳索锤式弯举 | mismatch |
| 肩背-叶翔 | 动作6 | 绳索面拉 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.3 | 面拉 | 未知动作 | mismatch |
| 肩背-叶翔 | 动作7 | 绳索面拉 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.3 | 面拉 | 未知动作 | mismatch |
| 肩背-叶翔 | 动作8 | 绳索面拉 | 龙门架 / UNKNOWN_ACTION | 0.6 | 面拉 | 未知动作 | mismatch |
| 肩背-叶翔 | 动作9 | 绳索面拉 | 龙门架 / cable_triceps_pushdown | 0.85 | 面拉 | 绳索下压 | mismatch |
| 腿-张开 | 动作1 | 跑步机 | 登阶机/爬楼机 / stepmill | 0.85 | 跑步 | 爬楼机 | mismatch |
| 腿-张开 | 动作2 | 杠铃深蹲 | 杠铃 / barbell_squat | 0.85 | 杠铃深蹲 | 杠铃深蹲 | match |
| 腿-张开 | 动作8 | 未知动作 | 固定器械 / UNKNOWN_ACTION | 0.5 | 未知动作 | 未知动作 | match |
