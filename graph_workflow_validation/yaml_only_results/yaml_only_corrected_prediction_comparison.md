# YAML-Only Corrected Prediction Comparison

YAML-only prompt comparison against user-corrected graph-level ground truth. recognizer.py dynamic prompt was not injected. One API error remains if present.

Total evaluated: 63
Normalized matches: 23
Mismatches: 39
API errors: 1

## By Folder

| folder | total | match | mismatch | api_error |
|---|---:|---:|---:|---:|
| 3 | 11 | 5 | 6 | 0 |
| 4 | 10 | 2 | 8 | 0 |
| 8 | 9 | 2 | 7 | 0 |
| 健身-高孟琦 | 3 | 1 | 2 | 0 |
| 肩-秦紫渝 | 6 | 1 | 5 | 0 |
| 肩-背-秦紫渝 | 5 | 2 | 3 | 0 |
| 肩背-叶翔 | 11 | 5 | 5 | 1 |
| 腿-张开 | 8 | 5 | 3 | 0 |

## Mismatches / API Errors

| folder | action | ground truth | prediction | conf | normalized GT | normalized pred | status |
|---|---|---|---|---:|---|---|---|
| 3 | 动作5 | 哑铃卧推 | 哑铃 / UNKNOWN_ACTION | 0.85 | 哑铃卧推 | 未知动作 | mismatch |
| 3 | 动作7 | 上斜 30 度哑铃卧推 | 引体向上架 / 引体向上 | 0.9 | 哑铃卧推 | 引体向上 | mismatch |
| 3 | 动作8 | 哑铃卧推 | 龙门架 / cable_chest_fly | 0.85 | 哑铃卧推 | 夹胸 | mismatch |
| 3 | 动作9 | 上斜史密斯卧推 | 龙门架 / 高位下拉 | 0.95 | 史密斯卧推 | 高位下拉 | mismatch |
| 3 | 动作10 | 绳索下拉 | 龙门架 / 绳索下压 | 0.92 | 绳索下拉 | 绳索下压 | mismatch |
| 3 | 动作11 | 绳索下拉 | 龙门架 / cable_triceps_pushdown | 0.85 | 绳索下拉 | 绳索下压 | mismatch |
| 4 | 动作2 | 坐姿划船 | 龙门架 / cable_lat_pulldown | 0.95 | 划船 | 高位下拉 | mismatch |
| 4 | 动作3 | 反握器械高位下拉 | 龙门架 / 绳索夹胸 | 0.75 | 高位下拉 | 夹胸 | mismatch |
| 4 | 动作4 | 反握器械高位下拉 | 龙门架 / 绳索夹胸 | 0.95 | 高位下拉 | 夹胸 | mismatch |
| 4 | 动作5 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.92 | 绳索锤式弯举 | 绳索下压 | mismatch |
| 4 | 动作6 | 绳索锤式弯举 | 龙门架 / cable_chest_fly | 0.85 | 绳索锤式弯举 | 夹胸 | mismatch |
| 4 | 动作8 | 杠铃弯举 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | 杠铃弯举 | 未知动作 | mismatch |
| 4 | 动作9 | 哑铃弯举 | 哑铃 / 哑铃侧平举 | 0.95 | 哑铃弯举 | 哑铃侧举 | mismatch |
| 4 | 动作10 | 哑铃弯举 | 哑铃 / 哑铃推肩 | 0.5 | 哑铃弯举 | 哑铃推肩 | mismatch |
| 8 | 动作2 | 跑步 | 健身车 / 健身车 | 0.95 | 跑步 | 健身车 | mismatch |
| 8 | 动作3 | 爬楼 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.1 | 爬楼机 | 未知动作 | mismatch |
| 8 | 动作4 | 史密斯卧推 | 杠铃 / barbell_bench_press | 0.68 | 史密斯卧推 | 杠铃卧推 | mismatch |
| 8 | 动作5 | 史密斯卧推 | 杠铃 / barbell_bench_press | 0.6 | 史密斯卧推 | 杠铃卧推 | mismatch |
| 8 | 动作6 | 杠铃弯举 | 龙门架 / 高位下拉 | 0.85 | 杠铃弯举 | 高位下拉 | mismatch |
| 8 | 动作7 | 史密斯卧推 | 龙门架 / 绳索下压 | 0.65 | 史密斯卧推 | 绳索下压 | mismatch |
| 8 | 动作8 | 划船 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.2 | 划船 | 未知动作 | mismatch |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.2 | 哑铃深蹲 | 未知动作 | mismatch |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | 史密斯机 / 史密斯卧推 | 0.85 | 高位下拉 | 史密斯卧推 | mismatch |
| 肩-秦紫渝 | 动作2 | 绳索下拉 | 龙门架 / 绳索下压 | 0.9 | 绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作3 | 绳索下拉 | 龙门架 / UNKNOWN_ACTION | 0.7 | 绳索下拉 | 未知动作 | mismatch |
| 肩-秦紫渝 | 动作4 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 单臂绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作5 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | 单臂绳索下拉 | 绳索下压 | mismatch |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | 龙门架 / 绳索下压 | 0.65 | 绳索下拉 | 绳索下压 | mismatch |
| 肩-背-秦紫渝 | 动作3 | 高位下拉 | 龙门架 / 绳索下压 | 0.85 | 高位下拉 | 绳索下压 | mismatch |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | 龙门架 / 绳索下压 | 0.85 | 划船 | 绳索下压 | mismatch |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | 跑步机 / 跑步机 | 0.95 | 拉伸/跑步机 | 跑步 | mismatch |
| 肩背-叶翔 | 动作1 | 爬楼机 | 跑步机 / 跑步机 | 0.95 | 爬楼机 | 跑步 | mismatch |
| 肩背-叶翔 | 动作5 | 直杆高位下拉 | 龙门架 / 绳索下压 | 0.92 | 高位下拉 | 绳索下压 | mismatch |
| 肩背-叶翔 | 动作6 | 绳索面拉 | 龙门架 / 坐姿绳索划船 | 0.88 | 面拉 | 划船 | mismatch |
| 肩背-叶翔 | 动作7 | 绳索面拉 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.1 | 面拉 | 未知动作 | mismatch |
| 肩背-叶翔 | 动作8 | 绳索面拉 | API_ERROR |  | 面拉 | API_ERROR | api_error |
| 肩背-叶翔 | 动作9 | 绳索面拉 | 龙门架 / 绳索下压 | 0.85 | 面拉 | 绳索下压 | mismatch |
| 腿-张开 | 动作1 | 跑步机 | 爬楼机 / 登阶机/爬楼机 | 0.95 | 跑步 | 爬楼机 | mismatch |
| 腿-张开 | 动作4 | 杠铃深蹲 | 史密斯机 / 史密斯深蹲 | 0.95 | 杠铃深蹲 | 史密斯深蹲 | mismatch |
| 腿-张开 | 动作5 | 坐姿腿屈伸 | 固定器械 / UNKNOWN_ACTION | 0.9 | 坐姿腿屈伸 | 未知动作 | mismatch |

## All Rows

| folder | action | ground truth | prediction | conf | status |
|---|---|---|---|---:|---|
| 3 | 动作1 | 史密斯卧推 | 史密斯机 / 史密斯卧推 | 0.9 | match |
| 3 | 动作2 | 史密斯卧推 | 史密斯机 / 史密斯卧推 | 0.85 | match |
| 3 | 动作3 | 水平哑铃卧推 | 哑铃 / 哑铃卧推 | 0.85 | match |
| 3 | 动作4 | 水平哑铃卧推 | 哑铃 / 哑铃卧推 | 0.85 | match |
| 3 | 动作5 | 哑铃卧推 | 哑铃 / UNKNOWN_ACTION | 0.85 | mismatch |
| 3 | 动作6 | 哑铃卧推 | 哑铃 / dumbbell_bench_press | 0.65 | match |
| 3 | 动作7 | 上斜 30 度哑铃卧推 | 引体向上架 / 引体向上 | 0.9 | mismatch |
| 3 | 动作8 | 哑铃卧推 | 龙门架 / cable_chest_fly | 0.85 | mismatch |
| 3 | 动作9 | 上斜史密斯卧推 | 龙门架 / 高位下拉 | 0.95 | mismatch |
| 3 | 动作10 | 绳索下拉 | 龙门架 / 绳索下压 | 0.92 | mismatch |
| 3 | 动作11 | 绳索下拉 | 龙门架 / cable_triceps_pushdown | 0.85 | mismatch |
| 4 | 动作1 | 宽距高位下拉 | 龙门架 / 高位下拉 | 0.95 | match |
| 4 | 动作2 | 坐姿划船 | 龙门架 / cable_lat_pulldown | 0.95 | mismatch |
| 4 | 动作3 | 反握器械高位下拉 | 龙门架 / 绳索夹胸 | 0.75 | mismatch |
| 4 | 动作4 | 反握器械高位下拉 | 龙门架 / 绳索夹胸 | 0.95 | mismatch |
| 4 | 动作5 | 绳索锤式弯举 | 龙门架 / 绳索下压 | 0.92 | mismatch |
| 4 | 动作6 | 绳索锤式弯举 | 龙门架 / cable_chest_fly | 0.85 | mismatch |
| 4 | 动作7 | 杠铃弯举 | 杠铃 / barbell_biceps_curl | 0.85 | match |
| 4 | 动作8 | 杠铃弯举 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.1 | mismatch |
| 4 | 动作9 | 哑铃弯举 | 哑铃 / 哑铃侧平举 | 0.95 | mismatch |
| 4 | 动作10 | 哑铃弯举 | 哑铃 / 哑铃推肩 | 0.5 | mismatch |
| 8 | 动作1 | 跑步 | 跑步机 / 跑步机 | 0.95 | match |
| 8 | 动作2 | 跑步 | 健身车 / 健身车 | 0.95 | mismatch |
| 8 | 动作3 | 爬楼 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.1 | mismatch |
| 8 | 动作4 | 史密斯卧推 | 杠铃 / barbell_bench_press | 0.68 | mismatch |
| 8 | 动作5 | 史密斯卧推 | 杠铃 / barbell_bench_press | 0.6 | mismatch |
| 8 | 动作6 | 杠铃弯举 | 龙门架 / 高位下拉 | 0.85 | mismatch |
| 8 | 动作7 | 史密斯卧推 | 龙门架 / 绳索下压 | 0.65 | mismatch |
| 8 | 动作8 | 划船 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.2 | mismatch |
| 8 | 动作9 | 夹胸 | 蝴蝶机 / 蝴蝶机夹胸 | 0.92 | match |
| 健身-高孟琦 | 动作1 | 哑铃深蹲 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.2 | mismatch |
| 健身-高孟琦 | 动作2 | 高位直杆下拉 | 史密斯机 / 史密斯卧推 | 0.85 | mismatch |
| 健身-高孟琦 | 动作3 | 绳索下压 | 龙门架 / 绳索下压 | 0.95 | match |
| 肩-秦紫渝 | 动作1 | 跑步 | 跑步机 / 跑步机 | 0.95 | match |
| 肩-秦紫渝 | 动作2 | 绳索下拉 | 龙门架 / 绳索下压 | 0.9 | mismatch |
| 肩-秦紫渝 | 动作3 | 绳索下拉 | 龙门架 / UNKNOWN_ACTION | 0.7 | mismatch |
| 肩-秦紫渝 | 动作4 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch |
| 肩-秦紫渝 | 动作5 | 单臂绳索下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch |
| 肩-秦紫渝 | 动作6 | 绳索下拉 | 龙门架 / 绳索下压 | 0.65 | mismatch |
| 肩-背-秦紫渝 | 动作1 | 热身（跑步机） | 跑步机 / 跑步机 | 0.95 | match |
| 肩-背-秦紫渝 | 动作2 | 高位下拉 | 龙门架 / 高位下拉 | 0.95 | match |
| 肩-背-秦紫渝 | 动作3 | 高位下拉 | 龙门架 / 绳索下压 | 0.85 | mismatch |
| 肩-背-秦紫渝 | 动作4 | 绳索划船 | 龙门架 / 绳索下压 | 0.85 | mismatch |
| 肩-背-秦紫渝 | 动作5 | 拉伸/跑步机 | 跑步机 / 跑步机 | 0.95 | mismatch |
| 肩背-叶翔 | 动作1 | 爬楼机 | 跑步机 / 跑步机 | 0.95 | mismatch |
| 肩背-叶翔 | 动作2 | 直杆高位下拉 | 龙门架 / 高位下拉 | 0.95 | match |
| 肩背-叶翔 | 动作3 | 直杆高位下拉 | 龙门架 / 高位下拉 | 0.8 | match |
| 肩背-叶翔 | 动作4 | 直杆高位下拉 | 龙门架 / 高位下拉 | 0.95 | match |
| 肩背-叶翔 | 动作5 | 直杆高位下拉 | 龙门架 / 绳索下压 | 0.92 | mismatch |
| 肩背-叶翔 | 动作6 | 绳索面拉 | 龙门架 / 坐姿绳索划船 | 0.88 | mismatch |
| 肩背-叶翔 | 动作7 | 绳索面拉 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.1 | mismatch |
| 肩背-叶翔 | 动作8 | 绳索面拉 | API_ERROR |  | api_error |
| 肩背-叶翔 | 动作9 | 绳索面拉 | 龙门架 / 绳索下压 | 0.85 | mismatch |
| 肩背-叶翔 | 动作10 | 坐姿划船 | 龙门架 / cable_seated_row | 0.95 | match |
| 肩背-叶翔 | 动作11 | 坐姿划船 | 龙门架 / 坐姿绳索划船 | 0.95 | match |
| 腿-张开 | 动作1 | 跑步机 | 爬楼机 / 登阶机/爬楼机 | 0.95 | mismatch |
| 腿-张开 | 动作2 | 杠铃深蹲 | 杠铃 / barbell_squat | 0.85 | match |
| 腿-张开 | 动作3 | 杠铃深蹲 | 杠铃 / 杠铃深蹲 | 0.92 | match |
| 腿-张开 | 动作4 | 杠铃深蹲 | 史密斯机 / 史密斯深蹲 | 0.95 | mismatch |
| 腿-张开 | 动作5 | 坐姿腿屈伸 | 固定器械 / UNKNOWN_ACTION | 0.9 | mismatch |
| 腿-张开 | 动作6 | 未知动作 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.4 | match |
| 腿-张开 | 动作7 | 倒蹬机 | 腿举机 / 腿举 | 0.98 | match |
| 腿-张开 | 动作8 | 未知动作 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.35 | match |
