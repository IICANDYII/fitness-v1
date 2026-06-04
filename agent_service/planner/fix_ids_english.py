"""把 id=212/213/214 的 exercise_id 和 name 改成英文格式，与其他行保持一致。"""
import psycopg2, psycopg2.extras, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666',
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# 检查候选 exercise_id 是否已被占用
def next_id(base: str) -> str:
    for i in range(1, 10):
        cand = f"{base}_{i:03d}"
        cur.execute("SELECT 1 FROM exercises WHERE exercise_id = %s", (cand,))
        if not cur.fetchone():
            return cand
    raise RuntimeError(f"No free id for {base}")

UPDATES = [
    # (current_exercise_id,  new_id_base,             new_name)
    ("ex_跑步机慢跑",  "treadmill_jog",         "Treadmill Jog"),
    ("ex_悬垂举腿",   "hanging_leg_raise",     "Hanging Leg Raise"),
    ("ex_史密斯机深蹲", "smith_machine_squat",   "Smith Machine Squat"),
]

for old_id, new_base, new_name in UPDATES:
    new_id = next_id(new_base)
    cur.execute(
        "UPDATE exercises SET exercise_id = %s, name = %s WHERE exercise_id = %s RETURNING id",
        (new_id, new_name, old_id)
    )
    row = cur.fetchone()
    if row:
        print(f"  id={row['id']}  {old_id:25s} -> {new_id}  /  name -> {new_name}")
    else:
        print(f"  [WARN] not found: {old_id}")

conn.commit()
conn.close()
print("Done.")
