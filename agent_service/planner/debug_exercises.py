import psycopg2, psycopg2.extras, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666',
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# 最近一条 session
cur.execute("""
    SELECT session_id, DATE(start_time) AS day, start_time
    FROM workout_session
    ORDER BY start_time DESC LIMIT 1
""")
s = cur.fetchone()
print(f"最新 session: {s['session_id']}  日期: {s['day']}")

# 该 session 的所有 exercise_execution 行
cur.execute("""
    SELECT exercise_name, sets, reps, timestamp, end_time, duration_sec
    FROM exercise_execution
    WHERE session_id = %s
    ORDER BY timestamp
""", (s['session_id'],))
rows = cur.fetchall()
print(f"\nexercise_execution 共 {len(rows)} 行:")
for r in rows:
    print(f"  {r['exercise_name']:15s}  sets={r['sets']}  reps={r['reps']}  "
          f"start={str(r['timestamp'])[:19]}  dur={r['duration_sec']:.0f}s")

conn.close()
