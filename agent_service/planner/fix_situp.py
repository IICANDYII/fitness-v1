# -*- coding: utf-8 -*-
"""Fix Situp: primary muscle is 腹直肌 (not marked red in the body map)."""
import psycopg2, json

conn = psycopg2.connect(host="localhost", port=5432,
                        user="postgres", password="666666", dbname="fitness")
cur = conn.cursor()
cur.execute("""
    UPDATE exercises
    SET primary_muscles = '["腹直肌"]'::jsonb,
        updated_at = NOW()
    WHERE exercise_id = 'situp_001'
""")
conn.commit()
print(f"Updated: {cur.rowcount} row(s)")

cur.execute("SELECT name, name_cn, primary_muscles FROM exercises WHERE exercise_id='situp_001'")
r = cur.fetchone()
print(f"  name={r[0]}  name_cn={r[1]}  muscles={r[2]}")
conn.close()
