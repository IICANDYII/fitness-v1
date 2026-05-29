"""
根据 exercise_execution 中的锻炼数据，为 biometric_stream 生成每 10 分钟一次的心率等生理指标。

心率建模逻辑：
  - 热身阶段（session 前 15 min）：心率从静息值线性上升至热身水平
  - 训练中：以最近完成的动作为主要驱动，HR 随动作强度波动
  - 两个动作之间的过渡期：心率缓慢恢复，但仍保持高于静息
  - 结尾 15 min 冷却期：心率向 session 基准线衰减
  - 叠加高斯噪声（±4–6 bpm）模拟自然波动
"""

import psycopg2
import json
import random
import math
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
# 动作名称 → 心率目标映射（中文名称，UTF-8）
# 目标 HR 表示该动作高强度执行时的典型峰值心率（bpm）
# ──────────────────────────────────────────────
EXERCISE_HR_TARGET: dict[str, int] = {
    # 胸部
    "平板卧推":    140,   # flat bench press
    "上斜哑铃飞鸟": 128,  # incline dumbbell flyes
    # 背部
    "硬拉":        160,   # deadlift
    "杠铃划船":    142,   # barbell row
    "引体向上":    152,   # pull-ups
    # 肩部
    "站姿推举":    122,   # standing overhead press
    "侧平举":      110,   # lateral raise
    "面拉":        115,   # face pull
    # 手臂
    "绳索下压":    118,   # cable pushdown
    "杠铃弯举":    120,   # barbell curl
    # 腿部
    "深蹲":        165,   # squat
    "腿举":        148,   # leg press
    "罗马尼亚硬拉": 158,  # Romanian deadlift
    "腿弯举":      128,   # leg curl
    "腿伸展":      120,   # leg extension
    "提踵":        105,   # calf raise
}

DEFAULT_HR_TARGET = 130   # 未命中映射时的默认目标心率
RESTING_HR       = 67    # 25岁中级男性静息心率
MAX_HR           = 195   # 220 - 25岁


def get_exercise_hr(name: str) -> int:
    return EXERCISE_HR_TARGET.get(name, DEFAULT_HR_TARGET)


def hr_at_time(
    t: datetime,
    session_start: datetime,
    session_end: datetime,
    exercises: list[tuple],   # [(ts, name, hr_target, sets, reps), ...]
) -> int:
    """
    计算某时刻的心率。

    exercises 已按时间排序，每条：(timestamp, exercise_name, hr_target, sets, reps)
    """
    session_sec   = (session_end - session_start).total_seconds()
    elapsed_sec   = (t - session_start).total_seconds()
    progress      = elapsed_sec / session_sec            # 0→1

    # ── 1. session 基准线（热身曲线）──────────────────
    warmup_sec     = 15 * 60                             # 热身 15 min
    warmup_prog    = min(1.0, elapsed_sec / warmup_sec)
    baseline_peak  = RESTING_HR + 32                     # 热身结束后的持续基线
    session_base   = RESTING_HR + (baseline_peak - RESTING_HR) * warmup_prog

    # ── 2. 找最近的过去动作 ────────────────────────────
    past = [(ts, n, thr, s, r) for ts, n, thr, s, r in exercises if ts <= t]
    if not past:
        # 尚未开始第一个动作：纯热身
        target = session_base
        return int(max(RESTING_HR, min(MAX_HR, target + random.gauss(0, 4))))

    last_ts, last_name, last_thr, last_sets, last_reps = past[-1]
    time_since_sec = (t - last_ts).total_seconds()

    # 一个动作组的估计时长：sets × (执行 ~45s + 休息 ~150s)
    set_cycle_sec  = 45 + 150   # ≈3 min / set
    exercise_block_sec = last_sets * set_cycle_sec      # 典型 12–16 min

    # ── 3. 计算动作区段内的心率 ────────────────────────
    if time_since_sec <= exercise_block_sec:
        # 仍在本动作的组次/组间休息范围内
        frac  = time_since_sec / exercise_block_sec
        # 曲线：前 40% 接近峰值，之后略降（疲劳 + 休息拉低平均）
        peak_mod = 1.0 - 0.12 * frac
        target   = session_base + (last_thr - session_base) * peak_mod

    else:
        # 动作结束后的恢复期：指数衰减
        recovery_sec = time_since_sec - exercise_block_sec
        tau          = 9 * 60          # 恢复时间常数 9 min
        decay        = math.exp(-recovery_sec / tau)
        end_hr       = session_base + (last_thr - session_base) * 0.55
        target       = session_base + (end_hr - session_base) * decay

    # ── 4. 冷却期修正（最后 15 min）────────────────────
    remaining_sec = (session_end - t).total_seconds()
    if remaining_sec < 15 * 60:
        cooldown_frac = remaining_sec / (15 * 60)        # 1→0
        target = session_base + (target - session_base) * (0.25 + 0.75 * cooldown_frac)

    # ── 5. 加入自然噪声 ────────────────────────────────
    noise  = random.gauss(0, 5)
    hr     = int(max(RESTING_HR - 5, min(MAX_HR, target + noise)))
    return hr


def calc_hrv(hr: int) -> float:
    """HRV 与心率负相关（ms）。"""
    hr_range = MAX_HR - RESTING_HR
    ratio    = max(0.0, (hr - RESTING_HR) / hr_range)
    hrv      = 58.0 - ratio * 40.0          # 18–58 ms 范围
    return round(max(15.0, min(65.0, hrv + random.gauss(0, 1.8))), 1)


def calc_fatigue(elapsed_min: float, hr: int) -> float:
    """疲劳评分随时间与强度累积（0–10 分）。"""
    time_factor       = elapsed_min / 90.0 * 4.5        # 90 min 约累积 4.5 分
    intensity_factor  = max(0.0, (hr - RESTING_HR - 25) / 80.0) * 2.0
    score             = 3.0 + time_factor + intensity_factor
    return round(max(2.5, min(10.0, score + random.gauss(0, 0.12))), 2)


def calc_steps(elapsed_min: float, hr: int) -> int:
    """累计步数：力量训练以移动步数为主，约 35–80 步/min。"""
    activity_ratio = max(0.2, (hr - RESTING_HR) / 90.0)
    steps_per_min  = 30 + activity_ratio * 55
    total          = int(elapsed_min * steps_per_min)
    return max(0, total + random.randint(-45, 55))


def calc_imu(hr: int) -> dict:
    """生成 IMU 加速度计数据（g），活动越激烈噪声越大。"""
    activity    = max(0.0, (hr - RESTING_HR) / 100.0)
    noise_scale = 0.25 + activity * 1.6
    return {
        "acc_x": round(random.gauss(0.08,  noise_scale), 3),
        "acc_y": round(random.gauss(-0.04, noise_scale), 3),
        "acc_z": round(9.81 + random.gauss(0, noise_scale * 0.35), 3),
    }


# ══════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════
def main():
    random.seed(2026)

    conn = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="666666",
        dbname="fitness",
    )
    cur = conn.cursor()

    # 1. 查询所有 session ──────────────────────────────
    cur.execute(
        "SELECT session_id, user_id, start_time, end_time "
        "FROM workout_session ORDER BY start_time"
    )
    sessions = cur.fetchall()

    # 2. 查询所有 exercise_execution，按 session 分组
    cur.execute(
        "SELECT session_id, exercise_name, timestamp, sets, reps "
        "FROM exercise_execution ORDER BY timestamp"
    )
    raw_execs = cur.fetchall()

    session_exercises: dict[str, list] = {}
    for sid, name, ts, sets, reps in raw_execs:
        key = str(sid)
        if key not in session_exercises:
            session_exercises[key] = []
        session_exercises[key].append((ts, name, get_exercise_hr(name), sets, reps))

    # 3. 清除该用户现有的 biometric_stream ─────────────
    user_ids = list({str(s[1]) for s in sessions})
    for uid in user_ids:
        cur.execute("DELETE FROM biometric_stream WHERE user_id = %s", (uid,))
    deleted = sum(cur.rowcount for _ in user_ids)   # rowcount 已在循环中更新，取最后一次；用 COUNT 更准
    conn.commit()
    print(f"已清除旧 biometric_stream 记录（user_ids: {user_ids}）\n")

    # 4. 按 session 生成心率序列 ────────────────────────
    INSERT_SQL = (
        "INSERT INTO biometric_stream "
        "(user_id, timestamp, heart_rate, hrv, fatigue_score, steps, imu_data) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)"
    )

    total_inserted = 0

    for session_id, user_id, start_time, end_time in sessions:
        sid_key   = str(session_id)
        exercises = session_exercises.get(sid_key, [])
        uid_str   = str(user_id)

        duration_min = (end_time - start_time).total_seconds() / 60
        print(f"Session {sid_key[-8:]}  {start_time:%Y-%m-%d %H:%M} → {end_time:%H:%M}"
              f"  ({duration_min:.0f} min)  动作数={len(exercises)}")
        print(f"  {'时刻':5}  {'HR':>4}  {'HRV':>5}  {'疲劳':>5}  {'步数':>6}  动作状态")
        print(f"  {'─'*55}")

        t = start_time
        while t <= end_time:
            elapsed_min = (t - start_time).total_seconds() / 60

            hr      = hr_at_time(t, start_time, end_time, exercises)
            hrv     = calc_hrv(hr)
            fatigue = calc_fatigue(elapsed_min, hr)
            steps   = calc_steps(elapsed_min, hr)
            imu     = calc_imu(hr)

            # 判断当前所处动作阶段（仅用于打印说明）
            past = [e for e in exercises if e[0] <= t]
            if not past:
                phase = "热身"
            else:
                last_ts, last_name, last_thr, last_sets, _ = past[-1]
                block_sec = last_sets * (45 + 150)
                since_sec = (t - last_ts).total_seconds()
                if since_sec <= block_sec:
                    phase = f"[{last_name}] 训练中"
                else:
                    phase = f"[{last_name}] 恢复中"

            print(f"  {t:%H:%M}  {hr:>4}  {hrv:>5.1f}  {fatigue:>5.2f}  {steps:>6}  {phase}")

            cur.execute(INSERT_SQL, (
                uid_str, t, hr, hrv, fatigue, steps,
                json.dumps(imu),
            ))
            total_inserted += 1
            t += timedelta(minutes=10)

        print()

    conn.commit()
    print(f"[OK] 共插入 {total_inserted} 条 biometric_stream 记录")
    conn.close()


if __name__ == "__main__":
    main()
