# Graph Action Recognition Round 1

| user | action | selected | conf | policy | top candidates | notes |
|---|---:|---|---:|---|---|---|
| 3 | 动作7 | 史密斯机 / 史密斯卧推 | 0.85 | single_clear | 史密斯卧推(0.85)<br>史密斯上斜卧推(0.6) | 无法通过拼图确定长凳的具体倾斜角度（平卧 vs 上斜），默认选择最基础的卧推。 |
| 3 | 动作8 | 龙门架 / 绳索夹胸 | 0.85 | single_clear | 绳索夹胸(0.85)<br>高位下拉(0.3) | 由于缺乏光流和IMU数据，无法精确判定动作的起始点和完整次数。 |
| 3 | 动作9 | 龙门架 / 高位下拉 | 0.95 | single_clear | 高位下拉(0.95) | 视觉证据非常充分，动作模式单一且清晰。 |
| 3 | 动作10 | 龙门架 / 绳索下压 | 0.85 | single_clear | 绳索下压(0.85)<br>高位下拉(0.3) | 中间部分帧（第5-7行）出现大面积遮挡（可能是手臂靠近镜头），导致中间次数判断不准。 |
| 3 | 动作11 | 龙门架 / 绳索下压 | 0.65 | multiple_close | 绳索下压(0.65)<br>面拉(0.25) | 视频大部分时间处于准备阶段，实际有效的动作行程较短，仅在最后几帧可见完整下压。 |
| 4 | 动作1 | 龙门架 / 高位下拉 | 0.95 | single_clear | 高位下拉(0.95) | 无 |
| 4 | 动作3 | 龙门架 / cable_chest_fly | 0.65 | multiple_close | cable_chest_fly(0.65)<br>cable_lat_pulldown(0.4)<br>cable_triceps_pushdown(0.3) | 动作持续时间极短（仅前两排），后续大部分时间为站立休息，导致动作特征捕捉不充分。 |
| 4 | 动作5 | 龙门架 / 绳索下压 | 0.85 | single_clear | 绳索下压(0.85)<br>高位下拉(0.1) | 仅凭拼图无法确定精确的负重重量，但动作轨迹非常典型。 |
| 4 | 动作6 | 龙门架 / 绳索下压 | 0.92 | single_clear | 绳索下压(0.92) | 仅凭抽帧拼图难以精确判断完整组数，但单次动作轨迹非常清晰。 |
| 4 | 动作8 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.3 | insufficient_evidence | UNKNOWN_ACTION(0.4) | 该片段主要记录了用户从健身房一处走到哑铃架并准备取哑铃的过程，尚未观察到任何有效的动作重复周期 |
| 4 | 动作9 | 哑铃 / 哑铃弯举 | 0.92 | single_clear | 哑铃弯举(0.92) | 无光流和IMU，但视觉特征极其典型，置信度高。 |
| 4 | 动作10 | 哑铃 / dumbbell_lateral_raise | 0.65 | multiple_close | dumbbell_lateral_raise(0.65)<br>dumbbell_shoulder_press(0.5) | 有效运动时间极短（仅前几帧），后续大部分时间为站立待机，难以判断完整组数和动作连贯性。 |
| 8 | 动作3 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | insufficient_evidence | UNKNOWN_ACTION(0.2)<br>barbell_bench_press(0.1) | 拼图中未观察到任何周期性的力量训练动作，主要为站立、调整设备或在器械间走动。 |
| 8 | 动作4 | 龙门架 / cable_lat_pulldown | 0.85 | single_clear | cable_lat_pulldown(0.85)<br>cable_triceps_pushdown(0.3) | 拼图中段（第2-3行）存在较多相机晃动和视角偏移，可能是组内调整或观察环境，导致次数统计存在一定模糊性。 |
| 8 | 动作5 | 龙门架 / cable_lat_pulldown | 0.92 | single_clear | cable_lat_pulldown(0.92)<br>pullup(0.15) | 无光流和IMU辅助，但视觉特征极其典型，不确定性极低。 |
| 8 | 动作6 | 龙门架 / 绳索下压 | 0.65 | multiple_close | 绳索下压(0.65)<br>绳索弯举(0.25) | 缺少光流和IMU数据，无法通过精确的力学方向和周期信号来百分之百确认是下压还是弯举，且手部运动幅度在第一人称视角下较局限。 |
| 8 | 动作7 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.1 | insufficient_evidence | UNKNOWN_ACTION(0.2) | 拼图中完全没有显示任何训练动作的往复周期，用户明显处于组间休息或准备阶段。 |
| 8 | 动作8 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | insufficient_evidence | treadmill_walk_run(0.15) | 视频内容主要为组间休息或转场走动，没有观察到任何连续、重复的抗阻力训练或有氧训练动作周期。 |
| 8 | 动作9 | 固定器械 / 固定器械推胸 | 0.85 | single_clear | 固定器械推胸(0.85)<br>蝴蝶机夹胸(0.4) | 仅凭拼图难以精确判断完整的重复次数，且部分帧存在运动模糊。 |
| 健身-高孟琦 | 动作1 | UNKNOWN_EQUIPMENT / UNKNOWN_ACTION | 0.2 | insufficient_evidence | 哑铃弯举(0.2)<br>哑铃侧平举(0.1) | 拼图中除第一帧外，其余帧均在行走或观察环境，未捕捉到任何有效的动作重复周期（Repetitions） |
| 健身-高孟琦 | 动作2 | 史密斯机 / smith_bench_press | 0.85 | single_clear | smith_bench_press(0.85)<br>barbell_bench_press(0.1) | 仅凭拼图难以完全排除微小倾角的上斜卧推，但从镜中视角看更接近平板卧推。 |
| 肩-秦紫渝 | 动作1 | 跑步机 / 跑步机 | 0.95 | single_clear | 跑步机(0.95) | 无 |
| 肩-秦紫渝 | 动作2 | 龙门架 / 绳索下压 | 0.9 | single_clear | 绳索下压(0.9) | 虽然文件夹名为‘肩’，但当前动作视觉特征完全符合肱三头肌的绳索下压；若为肩部训练，可能是面拉（Face Pull），但轨迹更偏向下而非向后，且面拉不在标准动作列表中。 |
| 肩-秦紫渝 | 动作3 | 龙门架 / 绳索下压 | 0.85 | single_clear | 绳索下压(0.85)<br>高位下拉(0.1) | 虽然文件夹名为‘肩’，但视觉证据（手部下压至腰部高度）更符合肱三头肌的绳索下压动作，而非典型的肩部动作（如面拉或侧平举）。 |
| 肩-秦紫渝 | 动作4 | 龙门架 / 绳索下压 | 0.85 | single_clear | 绳索下压(0.85)<br>高位下拉(0.3) | 仅凭拼图难以完全确认是否为面拉（Face Pull），但从手部下压的终点位置看，更符合下压动作。 |
| 肩-秦紫渝 | 动作5 | 龙门架 / 绳索下压 | 0.85 | single_clear | 绳索下压(0.85)<br>高位下拉(0.3) | 仅凭拼图难以判断精确的肘部固定情况，但绳索附件和下压轨迹非常典型。 |
| 肩-秦紫渝 | 动作6 | 龙门架 / 绳索侧平举 | 0.65 | multiple_close | 绳索侧平举(0.65)<br>绳索弯举(0.25) | 视频仅捕捉到动作的起始阶段（抓取把手并开始第一下提拉），缺乏完整的往复周期，导致置信度受限。 |
| 肩-背-秦紫渝 | 动作4 | 龙门架 / 绳索下压 | 0.92 | single_clear | 绳索下压(0.92)<br>面拉(0.15) | 无光流和IMU数据，但视觉特征极其典型，不确定性极低。 |
| 肩-背-秦紫渝 | 动作5 | 跑步机 / 跑步机 | 0.95 | single_clear | 跑步机(0.95) | 无 |
| 肩背-叶翔 | 动作3 | 龙门架 / cable_triceps_pushdown | 0.85 | single_clear | cable_triceps_pushdown(0.85)<br>cable_biceps_curl(0.1) | 仅凭拼图无法精确判断每组的呼吸和肌肉发力细节，但动作轨迹和器械非常明确。 |
| 肩背-叶翔 | 动作4 | 龙门架 / 高位下拉 | 0.92 | single_clear | 高位下拉(0.92) | 无光流和IMU，但视觉特征极其典型，不确定性极低。 |
| 肩背-叶翔 | 动作5 | 龙门架 / 绳索弯举 | 0.92 | single_clear | 绳索弯举(0.92)<br>绳索直立划船(0.3) | 无光流和IMU，但视觉证据（尤其是镜面反射）非常清晰，不确定性极低。 |
| 肩背-叶翔 | 动作6 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.3 | insufficient_evidence | cable_triceps_pushdown(0.4) | 整个片段主要记录了用户走向器械和准备抓握的过程，未观察到任何完整的动作重复周期（reps）。 |
| 肩背-叶翔 | 动作7 | UNKNOWN_EQUIPMENT / UNKNOWN_EXERCISE | 0.3 | insufficient_evidence | 绳索下压(0.4)<br>高位下拉(0.2) | 该片段绝大部分时间（帧3-16）处于组间休息状态，缺乏连续的动作周期，无法判定为完整的训练组。 |
| 肩背-叶翔 | 动作8 | 龙门架 / UNKNOWN_ACTION | 0.6 | multiple_close | cable_triceps_pushdown(0.4)<br>cable_lat_pulldown(0.2) | 该动作视觉上非常接近‘面拉 (Face Pull)’，但该动作不在标准动作列表中。若强行归类，最接近的绳索动作是绳索下压，但轨迹不符。 |
| 肩背-叶翔 | 动作9 | 龙门架 / cable_triceps_pushdown | 0.85 | single_clear | cable_triceps_pushdown(0.85)<br>cable_lat_pulldown(0.4) | 由于没有侧面视角，无法完全排除是直臂下压，但从手部动作看更像肘关节屈伸的绳索下压。 |
| 腿-张开 | 动作1 | 登阶机/爬楼机 / stepmill | 0.85 | single_clear | stepmill(0.85)<br>treadmill_walk_run(0.1) | 仅凭拼图较难区分极慢速跑步与登阶，但面板高度和扶手位置更符合登阶机。 |
| 腿-张开 | 动作2 | 杠铃 / barbell_squat | 0.85 | single_clear | barbell_squat(0.85)<br>smith_squat(0.4) | 仅凭图片难以百分之百确认杠铃是否完全自由（无隐蔽导轨），但从架子结构看自由杠铃概率极大。 |
| 腿-张开 | 动作8 | 固定器械 / UNKNOWN_ACTION | 0.5 | insufficient_evidence | machine_leg_press(0.4) | 文件夹名‘腿-张开’暗示可能是大腿外展机（Hip Abduction），但该动作不在标准动作列表中；且拼图主要记录了动作结束和离场过程，缺乏完整的重复周期。 |
