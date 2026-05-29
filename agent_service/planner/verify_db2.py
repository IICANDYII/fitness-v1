# -*- coding: utf-8 -*-
"""Final verification: check empty-muscles exercise + pretty-print a sample JSON."""
import json, sys
import psycopg2, psycopg2.extras

conn = psycopg2.connect(host="localhost", port=5432,
                        user="postgres", password="666666", dbname="fitness")
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ─── 1. Find exercise with no primary muscles ───
cur.execute("""
    SELECT exercise_id, name, name_cn, primary_muscles
    FROM exercises WHERE jsonb_array_length(primary_muscles) = 0
""")
rows = cur.fetchall()
print("Exercises with empty primary_muscles:")
for r in rows:
    print(f"  {r['exercise_id']} | {r['name']} | {r['name_cn']}")

# ─── 2. Pretty-print full record as JSON ────────
print("\n" + "="*60)
print("FULL RECORD EXAMPLE (Barbell Bench Press):")
print("="*60)
cur.execute("""
    SELECT exercise_id, name, name_cn,
           primary_muscles, secondary_muscles,
           movement_pattern, equipment, difficulty,
           training_goals, exercise_type,
           recommended_rep_range, risk_level,
           common_mistakes, safety_tips,
           estimated_mets, fatigue_score, contraindications
    FROM exercises
    WHERE name ILIKE '%barbell bench press%'
    LIMIT 1
""")
row = cur.fetchone()
if row:
    doc = dict(row)
    print(json.dumps(doc, ensure_ascii=False, indent=2))
else:
    # Fallback: any compound barbell exercise
    cur.execute("""
        SELECT exercise_id, name, name_cn,
               primary_muscles, secondary_muscles,
               movement_pattern, equipment, difficulty,
               training_goals, exercise_type,
               recommended_rep_range, risk_level,
               common_mistakes, safety_tips,
               estimated_mets, fatigue_score, contraindications
        FROM exercises
        WHERE '杠铃' = ANY(SELECT jsonb_array_elements_text(equipment))
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        print(json.dumps(dict(row), ensure_ascii=False, indent=2))

# ─── 3. Another sample: Dumbbell Curl ────────────
print("\n" + "="*60)
print("FULL RECORD EXAMPLE (Dumbbell Curl):")
print("="*60)
cur.execute("""
    SELECT exercise_id, name, name_cn,
           primary_muscles, secondary_muscles,
           movement_pattern, equipment, difficulty,
           training_goals, exercise_type,
           recommended_rep_range, risk_level,
           common_mistakes, safety_tips,
           estimated_mets, fatigue_score, contraindications
    FROM exercises
    WHERE name ILIKE '%dumbbell curl%'
    ORDER BY exercise_id LIMIT 1
""")
row = cur.fetchone()
if row:
    print(json.dumps(dict(row), ensure_ascii=False, indent=2))

conn.close()
