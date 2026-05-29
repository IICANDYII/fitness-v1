# -*- coding: utf-8 -*-
import json, psycopg2, psycopg2.extras

conn = psycopg2.connect(host="localhost", port=5432,
                        user="postgres", password="666666", dbname="fitness")
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

out = {}

# Stats
cur.execute("SELECT COUNT(*) AS n FROM exercises"); out["total"] = cur.fetchone()["n"]
cur.execute("SELECT difficulty, COUNT(*) n FROM exercises GROUP BY difficulty ORDER BY n DESC")
out["by_difficulty"] = {r["difficulty"]: r["n"] for r in cur.fetchall()}
cur.execute("SELECT movement_pattern, COUNT(*) n FROM exercises GROUP BY movement_pattern ORDER BY n DESC")
out["by_movement"] = {r["movement_pattern"]: r["n"] for r in cur.fetchall()}
cur.execute("SELECT risk_level, COUNT(*) n FROM exercises GROUP BY risk_level ORDER BY n DESC")
out["by_risk"] = {r["risk_level"]: r["n"] for r in cur.fetchall()}

# Empty primary muscles
cur.execute("SELECT exercise_id, name, name_cn FROM exercises WHERE jsonb_array_length(primary_muscles)=0")
out["empty_primary_muscles"] = [dict(r) for r in cur.fetchall()]

# Sample records
for ex_name in ["Barbell Bench Press", "Dumbbell Curl", "Machine Pulldown", "Forearm Plank", "Barbell Deadlift"]:
    cur.execute("""
        SELECT exercise_id, name, name_cn, primary_muscles, secondary_muscles,
               movement_pattern, equipment, difficulty, training_goals,
               exercise_type, recommended_rep_range, risk_level,
               common_mistakes, safety_tips, estimated_mets,
               fatigue_score, contraindications
        FROM exercises WHERE name ILIKE %s LIMIT 1
    """, (f"%{ex_name}%",))
    row = cur.fetchone()
    if row:
        out.setdefault("samples", {})[ex_name] = dict(row)

conn.close()

with open("D:/WorkPath/fitness/agent_service/planner/db_verify.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("Written to db_verify.json")
