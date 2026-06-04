"""演示当前 session 肌群百分比的完整计算过程。"""
import psycopg2, psycopg2.extras, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

EXERCISE_ALIAS = {
    "平板卧推": "杠铃平卧推", "深蹲": "杠铃深蹲", "硬拉": "杠铃硬拉",
}
MAJOR_GROUPS = {
    "胸": ["chest"],
    "肩": ["shoulders", "front-shoulders", "rear-shoulders"],
    "臂": ["triceps", "biceps"],
    "背": ["lats", "traps", "traps-middle", "lowerback", "scapula"],
    "腿": ["quads", "hamstrings", "calves"],
    "臀": ["glutes", "hips"],
    "腹": ["abdominals", "obliques"],
}

conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666',
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# 最新 session
cur.execute("SELECT session_id FROM workout_session ORDER BY start_time DESC LIMIT 1")
sid = cur.fetchone()["session_id"]

cur.execute("SELECT exercise_name, sets, reps FROM exercise_execution WHERE session_id = %s", (sid,))
rows = cur.fetchall()

print("=== 第一步：exercise_execution 行 ===")
for r in rows:
    print(f"  {r['exercise_name']:15s}  sets={r['sets']}")

# 查 exercises.source_data
canonical_names = list({EXERCISE_ALIAS.get(r["exercise_name"], r["exercise_name"]) for r in rows})
cur.execute("""
    SELECT DISTINCT ON (name_cn) name_cn, source_data->'muscles' AS m
    FROM exercises WHERE name_cn = ANY(%s)
    ORDER BY name_cn, CASE WHEN exercise_id LIKE 'ex_%%' THEN 0 ELSE 1 END, exercise_id
""", (canonical_names,))
ex_map = {r["name_cn"]: (r["m"] or {}) for r in cur.fetchall()}

print("\n=== 第二步：从 exercises 读取肌群映射 ===")
for name, m in ex_map.items():
    fm = m.get("frontBodyMap", {})
    bm = m.get("backBodyMap", {})
    print(f"  {name}: 主={fm.get('text-mw-red',[])}  副={fm.get('text-mw-gray',[])} | "
          f"背主={bm.get('text-mw-red',[])}  背副={bm.get('text-mw-gray',[])}")

print("\n=== 第三步：计算各肌肉得分（sets × 权重） ===")
print("  权重规则: 主要肌群(text-mw-red) × 2,  辅助肌群(text-mw-gray) × 1")
svg_scores: dict[str, float] = defaultdict(float)
for row in rows:
    name = row["exercise_name"]
    canonical = EXERCISE_ALIAS.get(name, name)
    sets = float(row.get("sets") or 0)
    m = ex_map.get(canonical, {})
    fm = m.get("frontBodyMap", {})
    bm = m.get("backBodyMap", {})
    for muscle in fm.get("text-mw-red", []):
        svg_scores[muscle] += sets * 2
        print(f"  {name:12s} → {muscle:20s} += {sets}×2 = {sets*2}")
    for muscle in fm.get("text-mw-gray", []):
        svg_scores[muscle] += sets * 1
        print(f"  {name:12s} → {muscle:20s} += {sets}×1 = {sets*1}")
    for muscle in bm.get("text-mw-red", []):
        svg_scores["b-"+muscle] += sets * 2
        svg_scores[muscle] += sets * 2
        print(f"  {name:12s} → {muscle:20s} += {sets}×2 = {sets*2}  (背面)")
    for muscle in bm.get("text-mw-gray", []):
        svg_scores["b-"+muscle] += sets * 1
        svg_scores[muscle] += sets * 1
        print(f"  {name:12s} → {muscle:20s} += {sets}×1 = {sets*1}  (背面)")

print(f"\n  各肌肉得分: { {k:v for k,v in svg_scores.items() if not k.startswith('b-')} }")

print("\n=== 第四步：按大肌群取峰值 → 归一化到 0-100% ===")
max_score = max((v for k,v in svg_scores.items()), default=1)
print(f"  全局最高分: {max_score}")
for label, muscles in MAJOR_GROUPS.items():
    peak = max((max(svg_scores.get(m, 0), svg_scores.get("b-"+m, 0)) for m in muscles), default=0)
    pct = round(peak / max_score * 100) if peak > 0 else 0
    if pct > 0:
        print(f"  {label}: peak={peak}  → {peak}/{max_score} × 100 = {pct}%")

conn.close()
