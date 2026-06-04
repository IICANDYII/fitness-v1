import psycopg2, psycopg2.extras, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666',
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("SELECT * FROM exercises ORDER BY id LIMIT 3 OFFSET 211")
rows = cur.fetchall()
for r in rows:
    print(f"id={r['id']}  exercise_id={r['exercise_id']}")
    print(f"  name={r['name']}  name_cn={r['name_cn']}")
    print(f"  movement_pattern={r['movement_pattern']}  difficulty={r['difficulty']}")
    print(f"  exercise_type={r['exercise_type']}  risk_level={r['risk_level']}")
    print(f"  primary_muscles={r['primary_muscles']}")
    print(f"  secondary_muscles={r['secondary_muscles']}")
    print(f"  equipment={r['equipment']}")
    print(f"  training_goals={r['training_goals']}")
    print(f"  recommended_rep_range={r['recommended_rep_range']}")
    print(f"  estimated_mets={r['estimated_mets']}")
    print(f"  fatigue_score={r['fatigue_score']}")
    print()
conn.close()
