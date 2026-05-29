#!/usr/bin/env python3
"""
embed_exercises.py — 为 exercises 表中 embedding IS NULL 的动作批量生成并持久化向量。

Usage:
    python embed_exercises.py          # 只处理 embedding 为 NULL 的行
    python embed_exercises.py --all    # 强制重新生成所有动作的 embedding
"""

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parents[2]))

# ── 配置（与 plan_generator 保持一致）───────────────────────────
DB_KWARGS = dict(host="localhost", port=5432, dbname="fitness",
                 user="postgres", password="666666")

_ZCHAT_KEY = os.environ.get("ZCHAT_API_KEY",
    "sk-G90J2FGkwO4sEPBNmaJs8XwzNCuFLat372D95AbuEQSpIhqS")
embed_client = OpenAI(api_key=_ZCHAT_KEY, base_url="https://api.zchat.tech/v1")

EMBED_MODEL  = "text-embedding-3-small"
BATCH_SIZE   = 100   # embedding API 单次最大条数


# ── 工具函数（与 plan_generator 完全一致，避免 import 副作用）──

def _jsonb_to_list(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return json.loads(val)
    return []


def _exercise_to_text(ex: dict) -> str:
    muscles = _jsonb_to_list(ex.get("primary_muscles"))
    goals   = _jsonb_to_list(ex.get("training_goals"))
    equip   = _jsonb_to_list(ex.get("equipment"))
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


def _embed_batch(texts: list[str]) -> list[list[float]]:
    results = []
    for i in range(0, len(texts), BATCH_SIZE):
        resp = embed_client.embeddings.create(
            model=EMBED_MODEL,
            input=texts[i: i + BATCH_SIZE],
        )
        results.extend(item.embedding for item in resp.data)
    return results


# ── 主逻辑 ────────────────────────────────────────────────────

def fetch_exercises(force_all: bool) -> list[dict]:
    sql = """
        SELECT exercise_id, name, name_cn,
               primary_muscles, secondary_muscles,
               movement_pattern, equipment, difficulty,
               training_goals, exercise_type, estimated_mets
        FROM exercises
    """
    if not force_all:
        sql += " WHERE embedding IS NULL"
    sql += " ORDER BY exercise_id"

    with psycopg2.connect(**DB_KWARGS,
                          cursor_factory=psycopg2.extras.RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]


def save_embeddings(rows: list[tuple[str, list[float]]]):
    """rows: [(exercise_id, embedding_vector), ...]"""
    sql = """
        UPDATE exercises
           SET embedding = %s::vector
         WHERE exercise_id = %s
    """
    with psycopg2.connect(**DB_KWARGS) as conn:
        with conn.cursor() as cur:
            for exercise_id, vec in rows:
                # pgvector 接受 Python list 直接转为文本格式
                cur.execute(sql, (vec, exercise_id))
        conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                        help="重新生成所有动作的 embedding（包括已有的）")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  exercises → pgvector embedding 填充")
    print(f"  模式: {'全量重新生成' if args.all else '仅处理 NULL 行'}")
    print(f"{'='*60}\n")

    exercises = fetch_exercises(force_all=args.all)
    if not exercises:
        print("✓ 没有需要处理的动作，退出。")
        return

    print(f"共 {len(exercises)} 个动作需要 embedding，分批调用 API...\n")

    texts = [_exercise_to_text(ex) for ex in exercises]
    vecs  = _embed_batch(texts)

    rows = [(ex["exercise_id"], vec) for ex, vec in zip(exercises, vecs)]
    save_embeddings(rows)

    print(f"OK: 已写入 {len(rows)} 条 embedding 到 exercises.embedding\n")


if __name__ == "__main__":
    main()
