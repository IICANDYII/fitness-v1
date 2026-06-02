import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="fitness", user="postgres", password="666666")
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='equipment_state' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(r)
print("---")
cur.execute("SELECT * FROM equipment_state LIMIT 5")
for r in cur.fetchall():
    print(r)
conn.close()
