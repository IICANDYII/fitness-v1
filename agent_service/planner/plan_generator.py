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
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
llm_client = OpenAI(api_key=_GEMINI_KEY, base_url="https://nextrouter.cc/v1", timeout=180.0)

_LLM_MAX_RETRIES = 3
_LLM_RETRY_DELAY = 30


def _llm_chat_with_retry(**kwargs) -> object:
    """带重试的 LLM 调用，应对 524 超时等瞬时错误。"""
    import openai
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            return llm_client.chat.completions.create(**kwargs)
        except (openai.APITimeoutError, openai.InternalServerError, openai.APIConnectionError) as e:
            if attempt == _LLM_MAX_RETRIES:
                raise
            wait = _LLM_RETRY_DELAY * attempt
            print(f"   ⚠ LLM 请求失败 (第{attempt}次): {type(e).__name__}, {wait}s 后重试...")
            time.sleep(wait)

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
# JSON 提取辅助（兼容 reasoning 模型：raw 文本可能含思考内容）
# ═══════════════════════════════════════════════════════════════

def _extract_json(raw: str, resp=None) -> dict:
    """从 LLM raw 输出中提取第一个完整 JSON 对象。"""
    if not raw:
        detail = ""
        if resp:
            choice = resp.choices[0] if resp.choices else None
            finish = choice.finish_reason if choice else "no_choice"
            model  = getattr(resp, "model", "unknown")
            usage  = getattr(resp, "usage", None)
            detail = (
                f" [model={model}, finish_reason={finish}"
                f", prompt_tokens={getattr(usage, 'prompt_tokens', '?')}"
                f", completion_tokens={getattr(usage, 'completion_tokens', '?')}]"
            )
        raise ValueError(f"LLM returned empty content{detail}")
    raw = raw.strip()
    # 直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 找 ```json ... ``` 代码块
    import re
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # 找第一个 { ... 最后一个 }
    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end > start:
        return json.loads(raw[start: end + 1])
    raise ValueError(f"No JSON object found in LLM response (len={len(raw)})")


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
# Step 2b (V3): 粗筛 + 近似动作分天排布
# ═══════════════════════════════════════════════════════════════

_DAY_MUSCLE_THEMES: dict[int, list[dict]] = {
    2: [
        {"theme": "推/上肢",  "keywords": ["胸大肌", "三角肌", "肱三头肌"]},
        {"theme": "拉/下肢",  "keywords": ["背阔肌", "股四头肌", "腘绳肌", "臀大肌"]},
    ],
    3: [
        {"theme": "推",       "keywords": ["胸大肌", "三角肌前束", "肱三头肌"]},
        {"theme": "拉",       "keywords": ["背阔肌", "斜方肌", "肱二头肌"]},
        {"theme": "腿/臀",    "keywords": ["股四头肌", "腘绳肌", "臀大肌", "腓肠肌"]},
    ],
    4: [
        {"theme": "胸肩",     "keywords": ["胸大肌", "三角肌", "肱三头肌"]},
        {"theme": "背臂",     "keywords": ["背阔肌", "斜方肌", "肱二头肌", "菱形肌"]},
        {"theme": "腿臀",     "keywords": ["股四头肌", "腘绳肌", "臀大肌", "腓肠肌"]},
        {"theme": "全身核心", "keywords": ["腹直肌", "竖脊肌", "腹斜肌"]},
    ],
    5: [
        {"theme": "胸",       "keywords": ["胸大肌"]},
        {"theme": "背",       "keywords": ["背阔肌", "斜方肌", "菱形肌"]},
        {"theme": "腿",       "keywords": ["股四头肌", "腘绳肌", "腓肠肌"]},
        {"theme": "肩",       "keywords": ["三角肌", "三角肌前束", "三角肌后束"]},
        {"theme": "臂/核心",  "keywords": ["肱二头肌", "肱三头肌", "腹直肌"]},
    ],
}


def rough_assign_to_days(exercises: list[dict], days_per_week: int) -> list[dict]:
    """
    V3 Step 2b: 按肌群主题将候选动作粗分到各训练日。
    返回可直接注入 prompt 的结构化列表（每个元素是一天的候选集合）。
    """
    available = sorted(_DAY_MUSCLE_THEMES.keys())
    clamp = min(available, key=lambda k: abs(k - days_per_week))
    themes = _DAY_MUSCLE_THEMES[clamp]

    day_buckets: list[list[dict]] = [[] for _ in themes]
    unassigned: list[dict] = []

    for ex in exercises:
        primary_str = " ".join(_jsonb_to_list(ex.get("primary_muscles")))
        placed = False
        for i, t in enumerate(themes):
            if any(kw in primary_str for kw in t["keywords"]):
                day_buckets[i].append(ex)
                placed = True
                break
        if not placed:
            unassigned.append(ex)

    # 未分配动作轮流补入各日
    for i, ex in enumerate(unassigned):
        day_buckets[i % len(themes)].append(ex)

    result = []
    for idx, bucket in enumerate(day_buckets):
        rep_range = {}
        entries = []
        for ex in bucket:
            rep_range = ex.get("recommended_rep_range") or {}
            if isinstance(rep_range, str):
                rep_range = json.loads(rep_range)
            entries.append({
                "id":        ex["exercise_id"],
                "name":      ex.get("name_cn") or ex["name"],
                "muscles":   _jsonb_to_list(ex.get("primary_muscles")),
                "pattern":   ex.get("movement_pattern"),
                "type":      ex.get("exercise_type"),
                "difficulty": ex.get("difficulty"),
                "goals":     _jsonb_to_list(ex.get("training_goals")),
                "rep_range": rep_range,
            })
        result.append({
            "suggested_day": idx + 1,
            "theme_hint":    themes[idx]["theme"],
            "candidates":    entries,
        })
    return result


# ═══════════════════════════════════════════════════════════════
# Step 4 (V3): LLM 规则校验器  (check_plan_islegal_v1.yaml)
# ═══════════════════════════════════════════════════════════════

def _phase_key(phase: str) -> str:
    p = (phase or "").lower()
    if "热身" in p or "warm" in p:
        return "warmup"
    if "拉伸" in p or "stretch" in p or "恢复" in p:
        return "stretch"
    return "main"


def validate_plan_llm(plan: dict, profile: dict, prior_issues: list[str] | None = None) -> dict:
    """
    调用 check_plan_islegal_v1 prompt，对生成的周计划做 LLM 规则校验。

    Returns dict:
      {
        "is_valid": bool,
        "score":    int,
        "issues":   list[str],
        "suggestions": str,
      }
    """
    schedule = profile.get("available_schedule") or {}
    prior_text = (
        "\n".join(f"- {i}" for i in prior_issues)
        if prior_issues else "（无）"
    )

    # 只传计划骨架给校验器，去掉 notes 等长文本以节省 token
    plan_slim = {
        "weekly_schedule": [
            {
                "day":   d.get("day"),
                "theme": d.get("theme"),
                "exercises": [
                    {k: e.get(k) for k in
                     ("phase", "name", "sets", "reps_or_duration", "rest_sec", "superset_group")}
                    for e in d.get("exercises", [])
                ],
            }
            for d in plan.get("weekly_schedule", [])
        ],
        "coaching_notes": plan.get("coaching_notes"),
    }

    system_msg, user_msg = load_prompt(
        "check_plan_islegal_v1",
        experience_level = profile.get("experience_level", ""),
        days_per_week    = schedule.get("days_per_week", 4),
        duration_min     = schedule.get("daily_duration_min", 60),
        fitness_goal     = profile.get("fitness_goal", ""),
        prior_issues     = prior_text,
        plan_json        = json.dumps(plan_slim, ensure_ascii=False, indent=2),
    )

    resp = _llm_chat_with_retry(
        model    = _GEMINI_MODEL,
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature = 0.1,
        max_tokens  = 4096,
    )
    try:
        result = _extract_json(resp.choices[0].message.content or "", resp)
        return {
            "is_valid":    bool(result.get("is_valid", True)),
            "score":       int(result.get("score", 7)),
            "issues":      result.get("issues") or [],
            "suggestions": result.get("suggestions", ""),
        }
    except Exception as e:
        print(f"   校验结果解析失败: {e}")
        return {"is_valid": True, "score": 7, "issues": [], "suggestions": ""}


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
        exercise_list_json  = json.dumps(ex_summaries, ensure_ascii=False),
        user_id             = str(profile.get("user_id") or DEFAULT_USER_ID),
    )

    print(f"   调用 {_GEMINI_MODEL} 生成计划...")
    resp = _llm_chat_with_retry(
        model=_GEMINI_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=32768,
    )

    return _extract_json(resp.choices[0].message.content or "", resp)


# ═══════════════════════════════════════════════════════════════
# V3 Pipeline: 分天排布 → 规则库 → LLM → LLM校验器(+重试)
# ═══════════════════════════════════════════════════════════════

def _call_v3_llm(
    day_assignments: list[dict],
    profile: dict,
    dynamic: dict | None,
    extra_context: str = "",
) -> dict:
    """调用 workout_plan_generator_v3，返回原始计划 JSON。"""
    schedule     = profile.get("available_schedule") or {}
    days_per_wk  = schedule.get("days_per_week", 4)
    duration_min = schedule.get("daily_duration_min", 60)
    total_cands  = sum(len(d["candidates"]) for d in day_assignments)

    fatigue_note = ""
    if dynamic:
        fatigue_note = (
            f"\n当前状态 — 疲劳: {dynamic.get('fatigue_level', '未知')}, "
            f"准备度: {dynamic.get('today_readiness', '未知')}/10, "
            f"近期训练负荷: {dynamic.get('last_training_load', '未知')}"
        )
    if extra_context:
        fatigue_note += f"\n\n⚠️ 上一次生成的计划存在以下问题，请务必修正：\n{extra_context}"

    meta = prompt_meta("workout_plan_generator_v3")
    print(f"   加载 prompt: workout_plan_generator_v3 v{meta.get('version', '?')}")
    system_msg, user_msg = load_prompt(
        "workout_plan_generator_v3",
        gender                = profile.get("gender", ""),
        age                   = profile.get("age", ""),
        weight                = profile.get("weight", ""),
        height                = profile.get("height", ""),
        fitness_goal          = profile.get("fitness_goal", ""),
        experience_level      = profile.get("experience_level", ""),
        preferred_styles      = ", ".join(profile.get("preferred_training_style") or []),
        days_per_week         = days_per_wk,
        duration_min          = duration_min,
        available_equipment   = ", ".join(profile.get("available_equipment") or []),
        accept_high_intensity = profile.get("accept_high_intensity", ""),
        need_variety          = profile.get("need_variety", ""),
        fatigue_note          = fatigue_note,
        exercise_count        = total_cands,
        exercise_list_json    = json.dumps(day_assignments, ensure_ascii=False),
        user_id               = str(profile.get("user_id") or DEFAULT_USER_ID),
    )
    resp = _llm_chat_with_retry(
        model             = _GEMINI_MODEL,
        messages          = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature       = 0.3,
        max_tokens        = 32768,
    )
    return _extract_json(resp.choices[0].message.content or "", resp)


def generate_plan_v3(
    exercises: list[dict],
    profile: dict,
    dynamic: dict | None,
) -> dict:
    """
    V3 Pipeline:
      Step 1  粗筛 + 近似动作分天排布
      Step 2  规则库作为前置知识（内嵌于 v3 prompt）
      Step 3  大模型解释与个性化表达
      Step 4  LLM 规则校验器审核（check_plan_islegal_v1）
              → 不合规时将问题反馈给模型，重新生成一次
    """
    schedule    = profile.get("available_schedule") or {}
    days_per_wk = schedule.get("days_per_week", 4)

    # ── Step 1 ──────────────────────────────────────────────────
    print(f"   [V3] 粗筛 + 近似动作分天排布 (days={days_per_wk})...")
    day_assignments  = rough_assign_to_days(exercises, days_per_wk)
    total_candidates = sum(len(d["candidates"]) for d in day_assignments)
    print(f"   [V3] 分天完成: {len(day_assignments)} 天 / {total_candidates} 个候选动作")

    # ── Step 2 & 3: 规则库 + LLM 首次生成 ────────────────────
    print(f"   [V3] 调用 {_GEMINI_MODEL} 生成计划 (第1次)...")
    plan = _call_v3_llm(day_assignments, profile, dynamic)

    # ── Step 4: LLM 校验器 ───────────────────────────────────
    print("   [V3] LLM 规则校验器审核 (check_plan_islegal_v1)...")
    validation = validate_plan_llm(plan, profile)
    print(f"   [V3] 校验分数: {validation['score']}/10  合规: {validation['is_valid']}")

    if not validation["is_valid"] and validation["issues"]:
        issues_text = "\n".join(f"- {i}" for i in validation["issues"])
        print(f"   [V3] 发现 {len(validation['issues'])} 条违规，重新生成...")
        for issue in validation["issues"]:
            print(f"      - {issue}")

        # ── Step 3b: 携带问题列表重新生成（仅一次）───────────
        print(f"   [V3] 调用 {_GEMINI_MODEL} 重新生成计划 (第2次)...")
        plan = _call_v3_llm(day_assignments, profile, dynamic, extra_context=issues_text)

        # 重新校验（记录结果但不再重试）
        print("   [V3] 重新校验...")
        validation = validate_plan_llm(plan, profile, prior_issues=validation["issues"])
        print(f"   [V3] 最终校验分数: {validation['score']}/10  合规: {validation['is_valid']}")
    else:
        print("   [V3] 规则校验通过 ✓")

    plan["_pipeline_version"] = "v3"
    plan["_validation"]       = validation
    return plan


# ═══════════════════════════════════════════════════════════════
# V4 Pipeline: 分天排布 → LLM(含替代动作池) → LLM校验器(+重试)
# ═══════════════════════════════════════════════════════════════

def _call_v4_llm(
    day_assignments: list[dict],
    profile: dict,
    dynamic: dict | None,
    extra_context: str = "",
) -> dict:
    """调用 workout_plan_generator_v4，返回含 replacement_pool 的计划 JSON。"""
    schedule     = profile.get("available_schedule") or {}
    days_per_wk  = schedule.get("days_per_week", 4)
    duration_min = schedule.get("daily_duration_min", 60)
    total_cands  = sum(len(d["candidates"]) for d in day_assignments)

    fatigue_note = ""
    if dynamic:
        fatigue_note = (
            f"\n当前状态 — 疲劳: {dynamic.get('fatigue_level', '未知')}, "
            f"准备度: {dynamic.get('today_readiness', '未知')}/10, "
            f"近期训练负荷: {dynamic.get('last_training_load', '未知')}"
        )
    if extra_context:
        fatigue_note += f"\n\n⚠️ 上一次生成的计划存在以下问题，请务必修正：\n{extra_context}"

    meta = prompt_meta("workout_plan_generator_v4")
    print(f"   加载 prompt: workout_plan_generator_v4 v{meta.get('version', '?')}")
    system_msg, user_msg = load_prompt(
        "workout_plan_generator_v4",
        gender                = profile.get("gender", ""),
        age                   = profile.get("age", ""),
        weight                = profile.get("weight", ""),
        height                = profile.get("height", ""),
        fitness_goal          = profile.get("fitness_goal", ""),
        experience_level      = profile.get("experience_level", ""),
        preferred_styles      = ", ".join(profile.get("preferred_training_style") or []),
        days_per_week         = days_per_wk,
        duration_min          = duration_min,
        available_equipment   = ", ".join(profile.get("available_equipment") or []),
        accept_high_intensity = profile.get("accept_high_intensity", ""),
        need_variety          = profile.get("need_variety", ""),
        fatigue_note          = fatigue_note,
        exercise_count        = total_cands,
        exercise_list_json    = json.dumps(day_assignments, ensure_ascii=False),
        user_id               = str(profile.get("user_id") or DEFAULT_USER_ID),
    )
    resp = _llm_chat_with_retry(
        model             = _GEMINI_MODEL,
        messages          = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature       = 0.3,
        max_tokens        = 32768,
    )
    return _extract_json(resp.choices[0].message.content or "", resp)


def generate_plan_v4(
    exercises: list[dict],
    profile: dict,
    dynamic: dict | None,
) -> dict:
    """
    V4 Pipeline (基于 V3，增加动作冗余池):
      Step 1  粗筛 + 近似动作分天排布
      Step 2  规则库作为前置知识（内嵌于 v4 prompt）
      Step 3  大模型生成含 replacement_pool 的周计划
      Step 4  LLM 规则校验器审核
    """
    schedule    = profile.get("available_schedule") or {}
    days_per_wk = schedule.get("days_per_week", 4)

    print(f"   [V4] 粗筛 + 近似动作分天排布 (days={days_per_wk})...")
    day_assignments  = rough_assign_to_days(exercises, days_per_wk)
    total_candidates = sum(len(d["candidates"]) for d in day_assignments)
    print(f"   [V4] 分天完成: {len(day_assignments)} 天 / {total_candidates} 个候选动作")

    print(f"   [V4] 调用 {_GEMINI_MODEL} 生成计划 (第1次)...")
    plan = _call_v4_llm(day_assignments, profile, dynamic)

    print("   [V4] LLM 规则校验器审核 (check_plan_islegal_v1)...")
    validation = validate_plan_llm(plan, profile)
    print(f"   [V4] 校验分数: {validation['score']}/10  合规: {validation['is_valid']}")

    if not validation["is_valid"] and validation["issues"]:
        issues_text = "\n".join(f"- {i}" for i in validation["issues"])
        print(f"   [V4] 发现 {len(validation['issues'])} 条违规，重新生成...")
        for issue in validation["issues"]:
            print(f"      - {issue}")

        print(f"   [V4] 调用 {_GEMINI_MODEL} 重新生成计划 (第2次)...")
        plan = _call_v4_llm(day_assignments, profile, dynamic, extra_context=issues_text)

        print("   [V4] 重新校验...")
        validation = validate_plan_llm(plan, profile, prior_issues=validation["issues"])
        print(f"   [V4] 最终校验分数: {validation['score']}/10  合规: {validation['is_valid']}")
    else:
        print("   [V4] 规则校验通过 ✓")

    plan["_pipeline_version"] = "v4"
    plan["_validation"]       = validation
    return plan


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
# 文件缓存 — 每个用户每个版本存一份最新计划 JSON
# ═══════════════════════════════════════════════════════════════

_CACHE_DIR = Path(__file__).parent / "plan_cache"


def _cache_path(user_id: str, version: str) -> Path:
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR / f"{version}_{user_id}.json"


def save_plan_cache(user_id: str, version: str, plan: dict) -> None:
    """将计划持久化到文件缓存（version=v2|v3）。"""
    from datetime import datetime as _dt
    payload = {
        "version":      version,
        "generated_at": _dt.now().isoformat(timespec="seconds"),
        "plan":         plan,
    }
    _cache_path(user_id, version).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   缓存已写入: plan_cache/{version}_{user_id}.json")


def load_plan_cache(user_id: str, version: str) -> dict | None:
    """读取文件缓存，若不存在返回 None。"""
    p = _cache_path(user_id, version)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("plan")
    except Exception:
        return None


def plan_cache_meta(user_id: str, version: str) -> dict | None:
    """返回缓存元信息 {version, generated_at}，不含计划主体。"""
    p = _cache_path(user_id, version)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"version": data.get("version"), "generated_at": data.get("generated_at")}
    except Exception:
        return None


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

    # ── Step 3 (V4 Pipeline) ────────────────────────────────
    print("④ [V4] 分天排布 → LLM 生成(含替代池) → LLM 校验...")
    plan = generate_plan_v4(ranked, profile, dynamic)
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
