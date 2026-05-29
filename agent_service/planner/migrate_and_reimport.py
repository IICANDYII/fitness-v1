# -*- coding: utf-8 -*-
"""
Migration: extend exercises table + reimport all 473 rows from xlsx.

Steps:
  1. ALTER TABLE  – drop unique(exercise_id), add plan_name + sets_reps
  2. Load existing LLM-enrichment from current 211 DB rows into a cache
  3. Truncate table
  4. Read all 473 rows from xlsx
  5. For each row, merge deterministic fields + cached LLM enrichment
  6. Call LLM only for exercises NOT already in the cache (should be 0)
  7. Bulk upsert all rows
"""

import json, re, sys, time
from pathlib import Path
import openpyxl
import psycopg2, psycopg2.extras
from openai import OpenAI

# ── Config ──────────────────────────────────────────────────────
BASE_DIR  = Path("D:/WorkPath/fitness/agent_service/planner")
XLSX_PATH = BASE_DIR / "workout_details.xlsx"

DB_CFG = dict(host="localhost", port=5432,
              user="postgres", password="666666", dbname="fitness")

GEMINI_BASE_URL = "https://nextrouter.cc/v1"
GEMINI_API_KEY  = "sk-gxBoLiZEqsQnwPweg2mlV6AWz0gpQJzlbtFz2rzRBYova4Fc"
GEMINI_MODEL    = "gemini-3.5-flash"
BATCH_SIZE      = 5

# ── Lookup tables (same as import_exercises.py) ──────────────────
MUSCLE_ZH = {
    "quads":           "股四头肌",  "glutes":         "臀大肌",
    "hamstrings":      "腘绳肌",    "calves":         "腓肠肌",
    "chest":           "胸大肌",    "triceps":        "肱三头肌",
    "biceps":          "肱二头肌",  "lats":           "背阔肌",
    "traps":           "斜方肌",    "traps-middle":   "斜方肌中部",
    "abdominals":      "腹直肌",    "obliques":       "腹斜肌",
    "forearms":        "前臂肌群",  "hands":          "手部肌群",
    "front-shoulders": "三角肌前束","rear-shoulders": "三角肌后束",
    "shoulders":       "三角肌中束","lowerback":      "竖脊肌",
    "shins":           "胫骨前肌",  "neck":           "颈部肌群",
}
DIFFICULTY_MAP = {"Novice":"beginner","Beginner":"beginner",
                  "Intermediate":"intermediate","Advanced":"advanced"}
MOVEMENT_MAP   = {"Push":"push","Pull":"pull","Hold":"hold"}
TYPE_MAP       = {"Compound":"compound","Isolation":"isolation"}
EQUIPMENT_KW   = [
    ("dumbbell","哑铃"),("barbell","杠铃"),("ez bar","EZ杠"),
    ("trap bar","六角杠"),("cable","缆绳机"),("smith","史密斯架"),
    ("kettlebell","壶铃"),("band","弹力带"),("machine","器械"),
    ("pull up","单杠"),("pull-up","单杠"),("pullup","单杠"),
    ("chin up","单杠"),("chin-up","单杠"),("dip","双杠"),
    ("suspension","悬吊绳"),("bosu","波速球"),
    ("stability ball","瑞士球"),("foam","泡沫轴"),
]
BW_KW     = ["plank","push up","push-up","pushup","burpee","crunch",
             "sit up","sit-up","leg raise","mountain climber",
             "jumping jack","squat jump","glute bridge","hip bridge",
             "superman","bird dog","dead bug"]
BENCH_KW  = ["bench","incline","decline","flat"," fly","flye","press"]

def detect_equipment(name):
    nl = name.lower()
    equip = []
    for kw, zh in EQUIPMENT_KW:
        if kw in nl and zh not in equip:
            equip.append(zh)
    if not equip or any(kw in nl for kw in BW_KW):
        if "自重" not in equip:
            equip.insert(0, "自重")
    if "杠铃" in equip or "哑铃" in equip:
        if any(kw in nl for kw in BENCH_KW):
            equip.append("训练凳")
    elif any(kw in nl for kw in ["bench","incline","decline","flat"]):
        equip.append("训练凳")
    return list(dict.fromkeys(equip))

def derive_risk(name, difficulty, equip, ex_type):
    if difficulty == "advanced" and "杠铃" in equip: return "high"
    if "杠铃" in equip or ex_type == "compound":     return "medium"
    if "器械" in equip:                              return "low"
    if difficulty == "advanced":                     return "medium"
    return "low"

def derive_mets(ex_type, difficulty, equip):
    base  = 5.0 if ex_type == "compound" else 3.5
    bonus = {"beginner":0,"intermediate":0.5,"advanced":1.5}.get(difficulty,0)
    if "杠铃" in equip: bonus += 1.0
    return round(base + bonus, 1)

def derive_goals(movement, ex_type, difficulty):
    if movement == "hold":             return ["核心稳定","耐力提升"]
    if ex_type == "compound":
        return ["力量提升","增肌"] if difficulty=="advanced" else ["增肌","力量提升"]
    return ["增肌","塑形"]

def get_primary_muscles(muscles_dict):
    red = []
    for side in ["frontBodyMap","backBodyMap"]:
        for mid in muscles_dict.get(side,{}).get("text-mw-red",[]):
            zh = MUSCLE_ZH.get(mid)
            if zh and zh not in red:
                red.append(zh)
    return red or ["腹直肌"]   # fallback for Situp etc.

def make_exercise_id(name):
    return re.sub(r"[^a-z0-9]+","_", name.lower()).strip("_")[:60]

def extract_sets_reps(bi: dict) -> str:
    """Return sets×reps string from basic_info, e.g. '3x10', '3x15s'."""
    for v in bi.values():
        if v and re.match(r"\d+x[\d\-s]+", str(v)):
            return str(v)
    return ""

# ── Step 1: ALTER TABLE ─────────────────────────────────────────
ALTER_SQL = """
-- 1. Drop unique constraint on exercise_id
ALTER TABLE exercises
    DROP CONSTRAINT IF EXISTS exercises_exercise_id_key;

-- 2. Add plan_name column (if not exists)
ALTER TABLE exercises
    ADD COLUMN IF NOT EXISTS plan_name VARCHAR(200);

-- 3. Add sets_reps column (if not exists)
ALTER TABLE exercises
    ADD COLUMN IF NOT EXISTS sets_reps VARCHAR(30);

-- 4. Add unique constraint on (plan_name, exercise_id) instead
--    (allows same exercise in different plans; duplicate plan+exercise kept by id)
DROP INDEX IF EXISTS idx_exercises_plan_exercise;
CREATE UNIQUE INDEX IF NOT EXISTS idx_exercises_plan_exercise
    ON exercises (plan_name, exercise_id)
    WHERE plan_name IS NOT NULL;
"""

# ── Step 2: LLM (for any exercises not yet in cache) ──────────────
LLM_SYSTEM = "你是专业健身教练兼运动科学专家。只返回 JSON 数组，不含任何其他内容。"
LLM_TMPL   = """\
为以下 {n} 个动作生成 JSON 数组（顺序与输入一致）：

每个对象格式：
{{"name_cn":"中文名","secondary_muscles":["次要肌1","次要肌2"],\
"common_mistakes":["错误1","错误2","错误3"],\
"safety_tips":["提示1","提示2"],\
"contraindications":["禁忌1","禁忌2"],\
"estimated_mets":6.0,\
"fatigue_score":{{"目标肌群":8,"中枢神经":5}}}}

注意：fatigue_score 的 key 用中文肌群名，值 1-10；中枢神经复合动作 6-8，孤立 2-4；estimated_mets 范围 2-12。

动作列表：
{block}

只返回 JSON 数组。"""

def call_llm(client, batch):
    lines = [
        f"{i}. 动作名={ex['name']}  主要肌群={','.join(ex['primary_muscles']) or '未知'}  "
        f"动作模式={ex.get('movement_pattern','push')}  "
        f"难度={ex.get('difficulty','beginner')}  类型={ex.get('exercise_type','compound')}"
        for i, ex in enumerate(batch, 1)
    ]
    prompt = LLM_TMPL.format(n=len(batch), block="\n".join(lines))
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=[{"role":"system","content":LLM_SYSTEM},
                           {"role":"user","content":prompt}],
                temperature=0.3, timeout=60,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*","",raw)
            raw = re.sub(r"\s*```$","",raw)
            data = json.loads(raw)
            if isinstance(data,list) and len(data)==len(batch):
                return data
        except Exception as e:
            print(f"  [LLM] Attempt {attempt+1}: {e}")
            time.sleep(2)
    return [{}]*len(batch)

# ── Upsert SQL ───────────────────────────────────────────────────
UPSERT_SQL = """
INSERT INTO exercises (
    exercise_id, plan_name, name, name_cn,
    primary_muscles, secondary_muscles,
    movement_pattern, equipment, difficulty,
    training_goals, exercise_type,
    recommended_rep_range, risk_level,
    common_mistakes, safety_tips,
    estimated_mets, fatigue_score,
    contraindications, sets_reps, source_data
) VALUES (
    %(exercise_id)s, %(plan_name)s, %(name)s, %(name_cn)s,
    %(primary_muscles)s::jsonb, %(secondary_muscles)s::jsonb,
    %(movement_pattern)s, %(equipment)s::jsonb, %(difficulty)s,
    %(training_goals)s::jsonb, %(exercise_type)s,
    %(recommended_rep_range)s::jsonb, %(risk_level)s,
    %(common_mistakes)s::jsonb, %(safety_tips)s::jsonb,
    %(estimated_mets)s, %(fatigue_score)s::jsonb,
    %(contraindications)s::jsonb, %(sets_reps)s, %(source_data)s::jsonb
)
ON CONFLICT (plan_name, exercise_id)
  WHERE plan_name IS NOT NULL
DO UPDATE SET
    name_cn              = EXCLUDED.name_cn,
    primary_muscles      = EXCLUDED.primary_muscles,
    secondary_muscles    = EXCLUDED.secondary_muscles,
    movement_pattern     = EXCLUDED.movement_pattern,
    equipment            = EXCLUDED.equipment,
    difficulty           = EXCLUDED.difficulty,
    training_goals       = EXCLUDED.training_goals,
    exercise_type        = EXCLUDED.exercise_type,
    recommended_rep_range= EXCLUDED.recommended_rep_range,
    risk_level           = EXCLUDED.risk_level,
    common_mistakes      = EXCLUDED.common_mistakes,
    safety_tips          = EXCLUDED.safety_tips,
    estimated_mets       = EXCLUDED.estimated_mets,
    fatigue_score        = EXCLUDED.fatigue_score,
    contraindications    = EXCLUDED.contraindications,
    sets_reps            = EXCLUDED.sets_reps,
    source_data          = EXCLUDED.source_data,
    updated_at           = NOW()
"""

# ── Main ─────────────────────────────────────────────────────────
def main():
    conn = psycopg2.connect(**DB_CFG)

    # 1. Migrate schema
    print("Step 1: Altering table schema …")
    with conn.cursor() as cur:
        cur.execute(ALTER_SQL)
    conn.commit()
    print("  Schema updated.")

    # 2. Load existing enrichment cache from DB (keyed by exercise name)
    print("\nStep 2: Loading existing enrichment cache from DB …")
    enrich_cache = {}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (name)
                name, name_cn, secondary_muscles, common_mistakes,
                safety_tips, contraindications, estimated_mets, fatigue_score
            FROM exercises
            ORDER BY name, id
        """)
        for row in cur.fetchall():
            enrich_cache[row["name"]] = dict(row)
    print(f"  Cached {len(enrich_cache)} unique exercises.")

    # 3. Truncate table
    print("\nStep 3: Truncating exercises table …")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE exercises RESTART IDENTITY")
    conn.commit()
    print("  Table truncated.")

    # 4. Read xlsx
    print("\nStep 4: Reading xlsx …")
    wb   = openpyxl.load_workbook(XLSX_PATH)
    ws   = wb.active
    xlsx_rows = []
    for r in range(2, ws.max_row + 1):
        plan    = (ws.cell(r, 1).value or "").strip()
        name    = (ws.cell(r, 2).value or "").strip()
        steps   = (ws.cell(r, 3).value or "").strip()
        details = ws.cell(r, 4).value or "{}"
        if name:
            xlsx_rows.append({"plan": plan, "name": name,
                               "steps": steps,
                               "details": json.loads(details)})
    print(f"  Loaded {len(xlsx_rows)} rows.")

    # 5. Build records
    print("\nStep 5: Building records + enrichment …")
    llm    = OpenAI(base_url=GEMINI_BASE_URL, api_key=GEMINI_API_KEY)
    records = []
    need_llm = []   # exercises not in cache

    REC_RANGE = {"strength":"3-6","hypertrophy":"8-12","endurance":"15-20"}

    for row in xlsx_rows:
        bi   = row["details"].get("basic_info", {})
        mmap = row["details"].get("muscles",    {})

        difficulty_raw = movement_raw = ex_type_raw = ""
        for v in bi.values():
            if v in DIFFICULTY_MAP: difficulty_raw = v
            elif v in MOVEMENT_MAP: movement_raw   = v
            elif v in TYPE_MAP:     ex_type_raw    = v

        difficulty = DIFFICULTY_MAP.get(difficulty_raw, "beginner")
        movement   = MOVEMENT_MAP.get(movement_raw,     "push")
        ex_type    = TYPE_MAP.get(ex_type_raw,          "compound")
        primary_zh = get_primary_muscles(mmap)
        equip      = detect_equipment(row["name"])
        risk       = derive_risk(row["name"], difficulty, equip, ex_type)
        mets       = derive_mets(ex_type, difficulty, equip)
        goals      = derive_goals(movement, ex_type, difficulty)
        sets_reps  = extract_sets_reps(bi)
        ex_id      = make_exercise_id(row["name"])

        rec = {
            "exercise_id":    ex_id,
            "plan_name":      row["plan"],
            "name":           row["name"],
            "primary_muscles": primary_zh,
            "movement_pattern": movement,
            "equipment":       equip,
            "difficulty":      difficulty,
            "training_goals":  goals,
            "exercise_type":   ex_type,
            "risk_level":      risk,
            "estimated_mets":  mets,
            "sets_reps":       sets_reps,
            "recommended_rep_range": REC_RANGE,
            # LLM fields – fill from cache or mark for LLM
            "name_cn":           "",
            "secondary_muscles": [],
            "common_mistakes":   [],
            "safety_tips":       [],
            "contraindications": [],
            "fatigue_score":     {},
            "source_data": row["details"],
        }

        cached = enrich_cache.get(row["name"])
        if cached:
            rec["name_cn"]           = cached.get("name_cn") or row["name"]
            rec["secondary_muscles"] = cached.get("secondary_muscles") or []
            rec["common_mistakes"]   = cached.get("common_mistakes")   or []
            rec["safety_tips"]       = cached.get("safety_tips")       or []
            rec["contraindications"] = cached.get("contraindications") or []
            rec["estimated_mets"]    = cached.get("estimated_mets")    or mets
            rec["fatigue_score"]     = cached.get("fatigue_score")     or {}
        else:
            need_llm.append(rec)

        records.append(rec)

    print(f"  Built {len(records)} records. "
          f"Cache hits: {len(records)-len(need_llm)}, "
          f"Need LLM: {len(need_llm)}")

    # 6. LLM for uncached exercises
    if need_llm:
        unique_need = {r["name"]: r for r in need_llm}
        print(f"\nStep 6: LLM enrichment for {len(unique_need)} new exercises …")
        unique_list = list(unique_need.values())
        for start in range(0, len(unique_list), BATCH_SIZE):
            batch = unique_list[start:start+BATCH_SIZE]
            pct   = (start+len(batch)) / len(unique_list) * 100
            print(f"  [{start+len(batch):3d}/{len(unique_list)}] ({pct:.0f}%)  "
                  f"{', '.join(e['name'] for e in batch)[:60]}")
            enrichments = call_llm(llm, batch)
            for ex, enr in zip(batch, enrichments):
                enrich_cache[ex["name"]] = enr
                ex["name_cn"]           = enr.get("name_cn")           or ex["name"]
                ex["secondary_muscles"] = enr.get("secondary_muscles") or []
                ex["common_mistakes"]   = enr.get("common_mistakes")   or []
                ex["safety_tips"]       = enr.get("safety_tips")       or []
                ex["contraindications"] = enr.get("contraindications") or []
                ex["estimated_mets"]    = enr.get("estimated_mets")    or ex["estimated_mets"]
                ex["fatigue_score"]     = enr.get("fatigue_score")     or {}
            time.sleep(0.3)
        # Apply cache to all records that needed LLM
        for rec in records:
            if not rec["name_cn"] and rec["name"] in enrich_cache:
                enr = enrich_cache[rec["name"]]
                rec["name_cn"]           = enr.get("name_cn")           or rec["name"]
                rec["secondary_muscles"] = enr.get("secondary_muscles") or []
                rec["common_mistakes"]   = enr.get("common_mistakes")   or []
                rec["safety_tips"]       = enr.get("safety_tips")       or []
                rec["contraindications"] = enr.get("contraindications") or []
                rec["estimated_mets"]    = enr.get("estimated_mets")    or rec["estimated_mets"]
                rec["fatigue_score"]     = enr.get("fatigue_score")     or {}
    else:
        print("\nStep 6: Skipped (all exercises in cache).")

    # 7. Bulk insert
    print("\nStep 7: Inserting 473 rows into PostgreSQL …")
    ok = err = 0
    with conn.cursor() as cur:
        for rec in records:
            try:
                params = {
                    k: json.dumps(v, ensure_ascii=False)
                       if isinstance(v, (dict, list)) else v
                    for k, v in rec.items()
                }
                cur.execute(UPSERT_SQL, params)
                ok += 1
            except Exception as e:
                print(f"  [DB ERR] {rec['plan_name']} / {rec['name']}: {e}")
                conn.rollback()
                err += 1
                continue
        conn.commit()

    conn.close()
    print(f"\nDone!  Inserted: {ok}  Errors: {err}")

    # 8. Quick verify
    conn2 = psycopg2.connect(**DB_CFG)
    with conn2.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM exercises")
        total = cur.fetchone()[0]
        cur.execute("""
            SELECT plan_name, COUNT(*) cnt
            FROM exercises
            GROUP BY plan_name
            ORDER BY cnt DESC LIMIT 5
        """)
        top_plans = cur.fetchall()
        cur.execute("""
            SELECT name, COUNT(*) cnt
            FROM exercises
            GROUP BY name
            ORDER BY cnt DESC LIMIT 5
        """)
        top_exs = cur.fetchall()
    conn2.close()

    print(f"\nTotal rows in exercises: {total}")
    print("Top plans by exercise count:")
    for p, c in top_plans:
        print(f"  {p}: {c}")
    print("Top repeated exercises:")
    for n, c in top_exs:
        print(f"  {n}: {c} plans")

if __name__ == "__main__":
    main()
