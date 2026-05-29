# -*- coding: utf-8 -*-
"""Print key unicode codepoints."""
import openpyxl, json, sys

wb = openpyxl.load_workbook("D:/WorkPath/fitness/agent_service/planner/workout_details.xlsx")
ws = wb.active

all_info = {}
for r in range(2, min(ws.max_row + 1, 50)):
    det = ws.cell(r, 4).value or "{}"
    d = json.loads(det)
    bi = d.get("basic_info", {})
    for k, v in bi.items():
        if v not in ["", None]:
            all_info.setdefault(k, set()).add(v)

# Write to a file to avoid encoding issues
with open("D:/WorkPath/fitness/agent_service/planner/key_dump.txt", "w", encoding="utf-8") as f:
    f.write("Keys and their values:\n")
    for k, vs in all_info.items():
        f.write(f"  key={k!r}  unicode={[hex(ord(c)) for c in k]}  values={sorted(vs)[:5]}\n")
print("Written to key_dump.txt")
