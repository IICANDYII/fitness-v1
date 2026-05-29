# -*- coding: utf-8 -*-
"""Check current table schema and count xlsx rows."""
import json, openpyxl, psycopg2, psycopg2.extras

conn = psycopg2.connect(host="localhost", port=5432,
                        user="postgres", password="666666", dbname="fitness")
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Current columns
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='exercises'
    ORDER BY ordinal_position
""")
print("Current columns:")
for r in cur.fetchall():
    print(f"  {r['column_name']:30s} {r['data_type']:20s} nullable={r['is_nullable']}")

# Current constraints
cur.execute("""
    SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
    WHERE tc.table_name = 'exercises' AND tc.table_schema = 'public'
    ORDER BY tc.constraint_type, kcu.column_name
""")
print("\nConstraints:")
for r in cur.fetchall():
    print(f"  {r['constraint_type']:15s} {r['constraint_name']:40s} col={r['column_name']}")

conn.close()

# xlsx stats
wb = openpyxl.load_workbook("D:/WorkPath/fitness/agent_service/planner/workout_details.xlsx")
ws = wb.active
rows = ws.max_row - 1
print(f"\nxlsx total data rows: {rows}")

# Check how many unique (plan, exercise) pairs
pairs = set()
same_ex = {}  # exercise name -> count of plans
for r in range(2, ws.max_row + 1):
    plan = ws.cell(r, 1).value or ""
    name = ws.cell(r, 2).value or ""
    pairs.add((plan, name))
    same_ex[name] = same_ex.get(name, 0) + 1

print(f"Unique (plan, exercise) pairs: {len(pairs)}")
top_repeated = sorted(same_ex.items(), key=lambda x: -x[1])[:10]
print("Top repeated exercises across plans:")
for name, cnt in top_repeated:
    print(f"  {name}: {cnt} plans")
