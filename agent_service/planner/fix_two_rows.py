import psycopg2, json, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666')
cur = conn.cursor()

rows = [
    {
        'exercise_id': 'ex_跑步机慢跑',
        'estimated_mets': 6.0,        # Compendium 02025: running 8km/h=8.3; jog ~6km/h=6.0
        'movement_pattern': 'locomotion',
        'equipment': ['跑步机'],
        'difficulty': 'beginner',
        'exercise_type': 'cardio',
        'training_goals': ['有氧耐力', '减脂'],
        'risk_level': 'low',
        'recommended_rep_range': {'min': 20, 'max': 60},
        'primary_muscles': ['quads', 'hamstrings', 'calves'],
        'secondary_muscles': ['glutes'],
        'fatigue_score': {'local': 2, 'systemic': 3},
    },
    {
        'exercise_id': 'ex_史密斯机深蹲',
        'estimated_mets': 5.5,
        'movement_pattern': 'squat',
        'equipment': ['史密斯架'],
        'difficulty': 'beginner',
        'exercise_type': 'compound',
        'training_goals': ['增肌', '力量提升'],
        'risk_level': 'low',
        'recommended_rep_range': {'min': 8, 'max': 15},
        'primary_muscles': ['quads', 'glutes'],
        'secondary_muscles': ['hamstrings'],
        'fatigue_score': {'local': 4, 'systemic': 3},
    },
]

for r in rows:
    eid = r['exercise_id']
    cur.execute("""UPDATE exercises SET
        estimated_mets=%s, movement_pattern=%s, equipment=%s::jsonb,
        difficulty=%s, exercise_type=%s, training_goals=%s::jsonb,
        risk_level=%s, recommended_rep_range=%s::jsonb,
        primary_muscles=%s::jsonb, secondary_muscles=%s::jsonb,
        fatigue_score=%s::jsonb
        WHERE exercise_id=%s""",
        (r['estimated_mets'], r['movement_pattern'],
         json.dumps(r['equipment'], ensure_ascii=False),
         r['difficulty'], r['exercise_type'],
         json.dumps(r['training_goals'], ensure_ascii=False),
         r['risk_level'],
         json.dumps(r['recommended_rep_range']),
         json.dumps(r['primary_muscles'], ensure_ascii=False),
         json.dumps(r['secondary_muscles'], ensure_ascii=False),
         json.dumps(r['fatigue_score']),
         eid))
    print(f"Updated {eid}: {cur.rowcount} row(s)")

conn.commit()
conn.close()
print("Done — all empty fields filled.")
