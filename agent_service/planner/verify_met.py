import psycopg2, psycopg2.extras, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666',
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) as total, COUNT(estimated_mets) as has_met, "
            "MIN(estimated_mets) as mn, MAX(estimated_mets) as mx, "
            "ROUND(AVG(estimated_mets)::numeric,2) as avg FROM exercises")
r = cur.fetchone()
print(f"Total rows: {r['total']}  HasMET: {r['has_met']}  "
      f"Min:{r['mn']}  Max:{r['mx']}  Avg:{r['avg']}")

cur.execute("SELECT COUNT(*) as c FROM exercises WHERE movement_pattern IS NULL")
print(f"movement_pattern NULL: {cur.fetchone()['c']}")

cur.execute("SELECT COUNT(*) as c FROM exercises WHERE primary_muscles = '[]'::jsonb")
print(f"primary_muscles empty: {cur.fetchone()['c']}")

print("\n--- gym_analyzer 动作 (ex_ 前缀) ---")
cur.execute("SELECT name_cn, estimated_mets, movement_pattern, difficulty "
            "FROM exercises WHERE exercise_id LIKE 'ex_%' LIMIT 10")
for r in cur.fetchall():
    print(f"  {str(r['name_cn']):16s}  MET={r['estimated_mets']}  "
          f"{r['movement_pattern']}  {r['difficulty']}")

print("\n--- xlsx 英文动作 (sample) ---")
cur.execute("SELECT name, estimated_mets, difficulty, exercise_type "
            "FROM exercises WHERE exercise_id NOT LIKE 'ex_%' ORDER BY name LIMIT 8")
for r in cur.fetchall():
    print(f"  {str(r['name']):45s}  MET={r['estimated_mets']}  "
          f"{r['difficulty']}/{r['exercise_type']}")

conn.close()
