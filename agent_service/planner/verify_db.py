# -*- coding: utf-8 -*-
"""Verify exercises table data quality."""
import json
import psycopg2, psycopg2.extras

conn = psycopg2.connect(host="localhost", port=5432,
                        user="postgres", password="666666", dbname="fitness")
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# ── Summary stats ──────────────────────────────
cur.execute("SELECT COUNT(*) AS total FROM exercises")
print("Total rows:", cur.fetchone()["total"])

cur.execute("""
    SELECT difficulty, COUNT(*) AS cnt
    FROM exercises GROUP BY difficulty ORDER BY cnt DESC
""")
print("\nBy difficulty:", {r["difficulty"]: r["cnt"] for r in cur.fetchall()})

cur.execute("""
    SELECT movement_pattern, COUNT(*) AS cnt
    FROM exercises GROUP BY movement_pattern ORDER BY cnt DESC
""")
print("By movement:", {r["movement_pattern"]: r["cnt"] for r in cur.fetchall()})

cur.execute("""
    SELECT exercise_type, COUNT(*) AS cnt
    FROM exercises GROUP BY exercise_type ORDER BY cnt DESC
""")
print("By type:", {r["exercise_type"]: r["cnt"] for r in cur.fetchall()})

cur.execute("""
    SELECT risk_level, COUNT(*) AS cnt
    FROM exercises GROUP BY risk_level ORDER BY cnt DESC
""")
print("By risk:", {r["risk_level"]: r["cnt"] for r in cur.fetchall()})

# ── Sample full records ────────────────────────
print("\n" + "="*60)
print("SAMPLE RECORDS (3 exercises):")
print("="*60)
cur.execute("""
    SELECT exercise_id, name, name_cn, primary_muscles, secondary_muscles,
           movement_pattern, equipment, difficulty, training_goals,
           exercise_type, recommended_rep_range, risk_level,
           common_mistakes, safety_tips, estimated_mets,
           fatigue_score, contraindications
    FROM exercises
    ORDER BY exercise_id
    LIMIT 3
""")
for row in cur.fetchall():
    print(f"\nexercise_id: {row['exercise_id']}")
    print(f"  name       : {row['name']}")
    print(f"  name_cn    : {row['name_cn']}")
    print(f"  primary_m  : {row['primary_muscles']}")
    print(f"  secondary_m: {row['secondary_muscles']}")
    print(f"  movement   : {row['movement_pattern']}")
    print(f"  equipment  : {row['equipment']}")
    print(f"  difficulty : {row['difficulty']}")
    print(f"  goals      : {row['training_goals']}")
    print(f"  type       : {row['exercise_type']}")
    print(f"  rep_range  : {row['recommended_rep_range']}")
    print(f"  risk       : {row['risk_level']}")
    print(f"  mistakes   : {row['common_mistakes']}")
    print(f"  tips       : {row['safety_tips']}")
    print(f"  mets       : {row['estimated_mets']}")
    print(f"  fatigue    : {row['fatigue_score']}")
    print(f"  contraind  : {row['contraindications']}")

# ── Data quality checks ───────────────────────
print("\n" + "="*60)
print("DATA QUALITY:")
cur.execute("SELECT COUNT(*) FROM exercises WHERE name_cn IS NULL OR name_cn=''")
print(f"  Missing name_cn: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM exercises WHERE jsonb_array_length(primary_muscles)=0")
print(f"  Empty primary muscles: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM exercises WHERE jsonb_array_length(common_mistakes)=0")
print(f"  Empty common_mistakes: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM exercises WHERE jsonb_array_length(safety_tips)=0")
print(f"  Empty safety_tips: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM exercises WHERE fatigue_score='{}'::jsonb")
print(f"  Empty fatigue_score: {cur.fetchone()[0]}")

conn.close()
