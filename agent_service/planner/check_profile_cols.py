import psycopg2, psycopg2.extras, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666',
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'user_profile_long_term'
    ORDER BY ordinal_position
""")
print("user_profile_long_term 列:")
for r in cur.fetchall():
    print(f"  {r['column_name']:20s} {r['data_type']}")

# 也顺便看一下实际有什么数据
cur.execute("SELECT * FROM user_profile_long_term LIMIT 2")
rows = cur.fetchall()
if rows:
    print("\n数据样本:")
    for r in rows:
        print(dict(r))
conn.close()
