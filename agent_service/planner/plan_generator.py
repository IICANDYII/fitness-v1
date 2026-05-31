#!/usr/bin/env python3
"""
运动计划生成器 - 三步流水线:
  Step 1: 规则初筛 (SQL, 基于器械 + 难度偏好)
  Step 2: 向量语义排序 (embedding cosine similarity)
  Step 3: LLM最终筛选与排序, 生成周计划

Usage:
  python plan_generator.py [user_id]
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import psycopg2
import psycopg2.extras
from openai import OpenAI

# prompt loader — 路径相对于项目根目录
sys.path.insert(0, str(Path(__file__).parents[2]))
from prompts.prompt_loader import load_prompt, prompt_meta

# ── 默认目标用户 ────────────────────────────────────────────────
DEFAULT_USER_ID = "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12"

# ── 数据库 ──────────────────────────────────────────────────────
DB_KWARGS = dict(host="localhost", port=5432, dbname="fitness", user="postgres", password="666666")


def get_conn(dict_cursor: bool = True):
    factory = psycopg2.extras.RealDictCursor if dict_cursor else None
    return psycopg2.connect(**DB_KWARGS, cursor_factory=factory)


# ── Embedding 客户端 (zchat.tech, 支持 text-embedding-3-small) ─
_ZCHAT_KEY = os.environ.get("ZCHAT_API_KEY", "sk-G90J2FGkwO4sEPBNmaJs8XwzNCuFLat372D95AbuEQSpIhqS")
embed_client = OpenAI(api_key=_ZCHAT_KEY, base_url="https://api.zchat.tech/v1")

# ── LLM 客户端 (nextrouter.cc → Gemini, 与 import_exercises 一致) ─
_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "sk-gxBoLiZEqsQnwPweg2mlV6AWz0gpQJzlbtFz2rzRBYova4Fc")
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
llm_client = OpenAI(api_key=_GEMINI_KEY, base_url="https://nextrouter.cc/v1")

# 器械名称映射: 用户画像中的器械 → exercises 表中的 equipment 值
EQUIPMENT_MAP = {
    "哑铃": "哑铃",
    "弹力带": "弹力带",
    "瑜伽垫": "自重",   # 瑜伽垫对应自重训练
    "杠铃": "杠铃",
    "壶铃": "壶铃",
    "单杠": "单杠",
    "双杠": "双杠",
}

# 经验水平 → 优先难度顺序
DIFFICULTY_PREFERENCE = {
    "beginner":     ["beginner", "intermediate"],
    "intermediate": ["intermediate", "advanced"],
    "advanced":     ["advanced", "intermediate"],
}


# ═══════════════════════════════════════════════════════════════
# 数据获取
# ═══════════════════════════════════════════════════════════════

def fetch_user_profile(user_id: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM user_profile_long_term WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
    if not row:
        raise ValueError(f"用户 {user_id} 不存在于 user_profile_long_term")
    return dict(row)


def fetch_dynamic_state(user_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM user_profile_dynamic
                WHERE user_id = %s
                ORDER BY record_date DESC LIMIT 1
                """,
                (user_id,)
            )
            row = cur.fetchone()
    return dict(row) if row else None


def fetch_history_plans(user_id: str, limit: int = 3) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, goal, plan_json FROM workout_plan
                WHERE user_id = %s
                ORDER BY date DESC LIMIT %s
                """,
                (user_id, limit)
            )
            return [dict(r) for r in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
# Step 1: 规则初筛
# ═══════════════════════════════════════════════════════════════

def filter_exercises_by_rules(profile: dict) -> list[dict]:
    """
    基于用户拥有的器械 + 经验水平进行SQL初筛。
    intermediate用户优先推荐 intermediate/advanced 难度动作。
    """
    available = profile.get("available_equipment") or []
    db_equipment = list({EQUIPMENT_MAP.get(e, e) for e in available})

    experience = profile.get("experience_level", "beginner")
    difficulties = DIFFICULTY_PREFERENCE.get(experience, ["beginner", "intermediate"])

    if not db_equipment:
        # 无器械信息则只筛自重
        db_equipment = ["自重"]

    # 动态构建 OR 条件 (每个器械类型一个 @> 检查)
    eq_clauses = " OR ".join(
        f"equipment @> '[{json.dumps(eq, ensure_ascii=False)}]'::jsonb"
        for eq in db_equipment
    )

    sql = f"""
        SELECT
            exercise_id, name, name_cn,
            primary_muscles, secondary_muscles,
            movement_pattern, equipment,
            difficulty, training_goals, exercise_type,
            recommended_rep_range, risk_level,
            estimated_mets, fatigue_score,
            embedding
        FROM exercises
        WHERE ({eq_clauses})
          AND difficulty = ANY(%s)
        ORDER BY
            CASE difficulty
                WHEN 'advanced'     THEN 1
                WHEN 'intermediate' THEN 2
                ELSE 3
            END,
            estimated_mets DESC NULLS LAST
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (difficulties,))
            return [dict(r) for r in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
# Step 2: 向量语义排序
# ═══════════════════════════════════════════════════════════════

def _jsonb_to_list(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return json.loads(val)
    return []


def _exercise_to_text(ex: dict) -> str:
    muscles  = _jsonb_to_list(ex.get("primary_muscles"))
    goals    = _jsonb_to_list(ex.get("training_goals"))
    equip    = _jsonb_to_list(ex.get("equipment"))
    return (
        f"{ex['name']} {ex.get('name_cn', '')} "
        f"主要肌群: {' '.join(muscles)} "
        f"训练目标: {' '.join(goals)} "
        f"器械: {' '.join(equip)} "
        f"动作模式: {ex.get('movement_pattern', '')} "
        f"类型: {ex.get('exercise_type', '')} "
        f"难度: {ex.get('difficulty', '')} "
        f"代谢当量MET: {ex.get('estimated_mets', 0)}"
    )


def _user_to_query(profile: dict, dynamic: dict | None, history: list[dict]) -> str:
    styles   = profile.get("preferred_training_style") or []
    equip    = profile.get("available_equipment") or []
    schedule = profile.get("available_schedule") or {}

    parts = [
        f"用户: {profile.get('gender', '')} {profile.get('age', '')}岁",
        f"身高{profile.get('height', '')}cm 体重{profile.get('weight', '')}kg",
        f"健身目标: {profile.get('fitness_goal', '')}",
        f"训练水平: {profile.get('experience_level', '')}",
        f"训练风格偏好: {' '.join(styles)}",
        f"可用器械: {' '.join(equip)}",
        f"每周{schedule.get('days_per_week', 4)}天 每次{schedule.get('daily_duration_min', 60)}分钟",
        f"睡眠: {profile.get('sleep_hours', 7)}小时",
    ]

    if dynamic:
        parts += [
            f"今日疲劳: {dynamic.get('fatigue_level', '未知')}",
            f"今日准备度: {dynamic.get('today_readiness', '未知')}/10",
            f"最近训练负荷: {dynamic.get('last_training_load', '未知')}",
        ]

    if history:
        recent_goals = [h.get("goal", "") for h in history if h.get("goal")]
        if recent_goals:
            parts.append(f"历史训练目标: {' '.join(recent_goals)}")

    return " | ".join(parts)


def _cosine(a: list[float], b: list[float]) -> float:
    a, b = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / (norm + 1e-9))


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """调用 embedding API, 每批最多 100 条。"""
    results = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        resp = embed_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts[i: i + batch_size]
        )
        results.extend(item.embedding for item in resp.data)
    return results


def _parse_pg_vector(text: str) -> list[float]:
    """将 pgvector 返回的文本格式 '[0.1,0.2,...]' 解析为 float list。"""
    return [float(x) for x in text.strip("[]").split(",")]


def _save_embeddings_to_db(pairs: list[tuple[str, list[float]]]):
    """将 (exercise_id, vector) 写回 exercises.embedding。"""
    if not pairs:
        return
    with get_conn(dict_cursor=False) as conn:
        with conn.cursor() as cur:
            for exercise_id, vec in pairs:
                import json as _json
                cur.execute(
                    "UPDATE exercises SET embedding = %s WHERE exercise_id = %s",
                    (_json.dumps(vec), exercise_id),
                )
        conn.commit()


def _resolve_embeddings(exercises: list[dict]) -> list[list[float]]:
    """
    为每个动作返回 embedding 向量。
    - 若 exercises[i]['embedding'] 非空（Step 1 从 DB 取到），直接解析
    - 否则调 embedding API 补全，并异步写回 DB
    返回与 exercises 等长的向量列表。
    """
    vecs: list[list[float] | None] = []
    missing_idx: list[int] = []

    for i, ex in enumerate(exercises):
        raw = ex.get("embedding")
        if raw:
            vecs.append(_parse_pg_vector(raw))
        else:
            vecs.append(None)
            missing_idx.append(i)

    if missing_idx:
        print(f"   {len(missing_idx)} 个动作 embedding 缺失，调用 API 补全并写回 DB...")
        texts       = [_exercise_to_text(exercises[i]) for i in missing_idx]
        new_vecs    = _embed_batch(texts)
        write_pairs = []
        for idx, vec in zip(missing_idx, new_vecs):
            vecs[idx] = vec
            write_pairs.append((exercises[idx]["exercise_id"], vec))
        _save_embeddings_to_db(write_pairs)
    else:
        print(f"   全部 {len(exercises)} 个动作命中 DB embedding，跳过 API 调用")

    return vecs  # type: ignore[return-value]


def _mmr_select(
    candidates: list[tuple[float, dict, list[float]]],
    top_k: int,
    lambda_: float = 0.6,
) -> list[dict]:
    """
    Maximum Marginal Relevance 多样性选择。
    candidates: [(relevance_score, exercise_dict, embedding_vector), ...]
    lambda_: 相关性权重 (1-lambda_ 为多样性权重)
    保证选出的动作池语义分散，避免同类动作扎堆。
    """
    selected_vecs: list[list[float]] = []
    selected_exs:  list[dict]        = []
    remaining = list(candidates)

    while len(selected_exs) < top_k and remaining:
        best_score = -1e9
        best_idx   = 0

        for i, (rel, _, vec) in enumerate(remaining):
            if not selected_vecs:
                mmr = rel
            else:
                # 与已选集合中最相似的那个的相似度（惩罚项）
                max_sim_to_selected = max(
                    _cosine(vec, sv) for sv in selected_vecs
                )
                mmr = lambda_ * rel - (1 - lambda_) * max_sim_to_selected

            if mmr > best_score:
                best_score = mmr
                best_idx   = i

        _, ex, vec = remaining.pop(best_idx)
        selected_exs.append(ex)
        selected_vecs.append(vec)

    return selected_exs


def rank_by_vector(
    exercises: list[dict],
    profile: dict,
    dynamic: dict | None,
    history: list[dict],
    top_k: int = 40,
    mmr_lambda: float = 0.6,
) -> list[dict]:
    """
    为用户画像生成 embedding，使用 DB 持久化向量（命中则免 API），
    按 cosine 相似度打分后用 MMR 去重。

    流程:
      1. _resolve_embeddings: 优先读 DB，缺失时调 API 并写回
      2. 计算所有动作的相关性得分 (cosine + boost)
      3. 取前 top_k * 3 作为候选池（保留足够动作供 MMR 选择）
      4. MMR 迭代选出 top_k 个动作，保证既相关又互相语义分散

    额外 boost:
      - 目标契合度 (减脂/塑形/耐力相关动作 +0.05)
      - 复合动作 (+0.03, 减脂更高效)
      - MET boost (代谢当量越高加分越多, 上限 +0.05)
    """
    print(f"   正在生成用户 query embedding...")
    user_query = _user_to_query(profile, dynamic, history)
    user_vec   = _embed_batch([user_query])[0]

    # 优先使用 DB 已存 embedding，对缺失的动作调 API 补全并写回
    ex_vecs = _resolve_embeddings(exercises)

    fat_loss_goals = {"减脂", "塑形", "耐力提升", "心肺功能"}

    scored = []
    for ex, vec in zip(exercises, ex_vecs):
        sim = _cosine(user_vec, vec)

        goals = set(_jsonb_to_list(ex.get("training_goals")))
        goal_boost     = 0.05 if goals & fat_loss_goals else 0.0
        compound_boost = 0.03 if ex.get("exercise_type") == "compound" else 0.0
        met_boost      = min(float(ex.get("estimated_mets") or 5) / 100, 0.05)

        scored.append((sim + goal_boost + compound_boost + met_boost, ex, vec))

    # 先按相关性降序，截取候选池（MMR 从中选取多样化子集）
    scored.sort(key=lambda x: x[0], reverse=True)
    pool_size = min(top_k * 3, len(scored))
    pool = scored[:pool_size]

    print(f"   MMR 多样性选择: 从 {pool_size} 个候选中选 {top_k} 个 (λ={mmr_lambda})...")
    return _mmr_select(pool, top_k=top_k, lambda_=mmr_lambda)


# ═══════════════════════════════════════════════════════════════
# Step 3: LLM 生成周计划
# ═══════════════════════════════════════════════════════════════

def generate_plan_with_llm(
    exercises: list[dict],
    profile: dict,
    dynamic: dict | None,
) -> dict:
    """
    将 Top-K 动作和用户信息发送给 GPT-4o, 返回结构化周计划 JSON。
    """
    schedule     = profile.get("available_schedule") or {}
    days_per_wk  = schedule.get("days_per_week", 4)
    duration_min = schedule.get("daily_duration_min", 60)

    # 格式化动作列表供 LLM 阅读
    ex_summaries = []
    for ex in exercises:
        rep_range = ex.get("recommended_rep_range") or {}
        if isinstance(rep_range, str):
            rep_range = json.loads(rep_range)
        ex_summaries.append({
            "id":         ex["exercise_id"],
            "name":       ex.get("name_cn") or ex["name"],
            "name_en":    ex["name"],
            "muscles":    _jsonb_to_list(ex.get("primary_muscles")),
            "sec_muscles":_jsonb_to_list(ex.get("secondary_muscles")),
            "pattern":    ex.get("movement_pattern"),
            "type":       ex.get("exercise_type"),
            "difficulty": ex.get("difficulty"),
            "goals":      _jsonb_to_list(ex.get("training_goals")),
            "rep_range":  rep_range,
            "mets":       ex.get("estimated_mets"),
            "risk":       ex.get("risk_level"),
        })

    # 动态状态注释
    fatigue_note = ""
    if dynamic:
        fatigue_note = (
            f"\n当前状态 — 疲劳: {dynamic.get('fatigue_level', '未知')}, "
            f"准备度: {dynamic.get('today_readiness', '未知')}/10, "
            f"近期训练负荷: {dynamic.get('last_training_load', '未知')}"
        )

    # 从 prompts/workout_plan_generator.yaml 读取最新版本 prompt
    meta = prompt_meta("workout_plan_generator")
    print(f"   加载 prompt: workout_plan_generator v{meta.get('version', '?')}")
    system_msg, user_msg = load_prompt(
        "workout_plan_generator",
        gender              = profile.get("gender", ""),
        age                 = profile.get("age", ""),
        weight              = profile.get("weight", ""),
        height              = profile.get("height", ""),
        fitness_goal        = profile.get("fitness_goal", ""),
        experience_level    = profile.get("experience_level", ""),
        preferred_styles    = ", ".join(profile.get("preferred_training_style") or []),
        days_per_week       = days_per_wk,
        duration_min        = duration_min,
        available_equipment = ", ".join(profile.get("available_equipment") or []),
        accept_high_intensity = profile.get("accept_high_intensity", ""),
        need_variety        = profile.get("need_variety", ""),
        fatigue_note        = fatigue_note,
        exercise_count      = len(ex_summaries),
        exercise_list_json  = json.dumps(ex_summaries, ensure_ascii=False, indent=2),
        user_id             = str(profile.get("user_id") or DEFAULT_USER_ID),
    )

    print(f"   调用 {_GEMINI_MODEL} 生成计划...")
    resp = llm_client.chat.completions.create(
        model=_GEMINI_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    return json.loads(resp.choices[0].message.content)


# ═══════════════════════════════════════════════════════════════
# 持久化
# ═══════════════════════════════════════════════════════════════

def _ensure_user_in_profile(user_id: str, profile: dict):
    """workout_plan 有 FK 到 user_profile, 若不存在则插入最小记录。"""
    with get_conn(dict_cursor=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM user_profile WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO user_profile
                        (user_id, height, weight, age, gender, fitness_level, goals)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (
                        user_id,
                        profile.get("height"),
                        profile.get("weight"),
                        profile.get("age"),
                        profile.get("gender"),
                        profile.get("experience_level"),
                        profile.get("fitness_goal"),
                    ),
                )
        conn.commit()


def save_workout_plan(user_id: str, goal: str, plan_json: dict) -> str:
    with get_conn(dict_cursor=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workout_plan (user_id, date, goal, plan_json)
                VALUES (%s, %s, %s, %s)
                RETURNING plan_id
                """,
                (user_id, date.today(), goal, json.dumps(plan_json, ensure_ascii=False)),
            )
            plan_id = cur.fetchone()[0]
        conn.commit()
    return str(plan_id)


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    start_time = time.perf_counter()
    user_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER_ID
    print(f"\n{'='*60}")
    print(f"  运动计划生成器")
    print(f"  用户 ID: {user_id}")
    print(f"{'='*60}\n")

    # ── 获取数据 ──────────────────────────────────────────────
    print("① 获取用户画像...")
    profile = fetch_user_profile(user_id)
    dynamic = fetch_dynamic_state(user_id)
    history = fetch_history_plans(user_id)
    print(f"   目标={profile['fitness_goal']}  水平={profile['experience_level']}")
    print(f"   器械={profile['available_equipment']}")
    print(f"   动态状态={'有' if dynamic else '无'}  历史计划={len(history)}条\n")

    # ── Step 1 ────────────────────────────────────────────────
    print("② [Step 1] 规则初筛...")
    filtered = filter_exercises_by_rules(profile)
    print(f"   OK 筛出 {len(filtered)} 个动作\n")

    if not filtered:
        print("ERR 未筛出任何动作, 请检查器械配置")
        sys.exit(1)

    # ── Step 2 ────────────────────────────────────────────────
    print("③ [Step 2] 向量语义排序...")
    ranked = rank_by_vector(filtered, profile, dynamic, history, top_k=40)
    print(f"   OK 取 Top-{len(ranked)} 语义最相关动作\n")

    # ── Step 3 ────────────────────────────────────────────────
    print("④ [Step 3] LLM 生成周训练计划...")
    plan = generate_plan_with_llm(ranked, profile, dynamic)
    print(f"   OK 计划生成: {plan.get('plan_name', '(无名称)')}\n")

    # ── 保存 ──────────────────────────────────────────────────
    print("⑤ 持久化到数据库...")
    _ensure_user_in_profile(user_id, profile)
    plan_id = save_workout_plan(user_id, profile["fitness_goal"], plan)
    print(f"   OK plan_id = {plan_id}\n")

    # ── 输出结果 ──────────────────────────────────────────────
    print("=" * 60)
    print("  生成的训练计划")
    print("=" * 60)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    elapsed = time.perf_counter() - start_time
    print(f"\n总用时: {elapsed:.2f}s")

    return plan


if __name__ == "__main__":
    main()
