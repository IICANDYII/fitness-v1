# -*- coding: utf-8 -*-
import psycopg2, json, collections, openpyxl

# ---- DB check with correct credentials ----
conn = psycopg2.connect(host="localhost", port=5432,
                        user="postgres", password="666666", dbname="fitness")
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
tables = [t[0] for t in cur.fetchall()]
print("Existing tables:", tables)
conn.close()

# ---- Unique exercise analysis ----
wb = openpyxl.load_workbook("D:/WorkPath/fitness/agent_service/planner/workout_details.xlsx")
ws = wb.active

seen = {}   # name -> first row data
for r in range(2, ws.max_row + 1):
    name    = ws.cell(r, 2).value or ""
    plan    = ws.cell(r, 1).value or ""
    details = ws.cell(r, 4).value or "{}"
    if name and name not in seen:
        seen[name] = {"plan": plan, "details": json.loads(details)}

print(f"\nTotal rows: {ws.max_row - 1}")
print(f"Unique exercises: {len(seen)}")

# Sample 5 exercises
print("\nSample unique exercises:")
for i, (name, data) in enumerate(list(seen.items())[:5]):
    bi = data["details"].get("basic_info", {})
    mf = data["details"].get("muscles", {}).get("frontBodyMap", {})
    mb = data["details"].get("muscles", {}).get("backBodyMap", {})
    red_f = mf.get("text-mw-red", [])
    red_b = mb.get("text-mw-red", [])
    print(f"  {name}: red_muscles={red_f + red_b}, info={bi}")
