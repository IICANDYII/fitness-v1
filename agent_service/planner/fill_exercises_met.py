#!/usr/bin/env python3
"""
fill_exercises_met.py

1. 查询 exercises 表，打印哪些行字段为空/默认值
2. 用 Compendium of Physical Activities (Ainsworth et al., 2011) 标准 MET 值更新
   estimated_mets，同时对空字段注入运动科学标准信息
3. 对 gym_analyzer 写入的中文动作行（exercise_id 前缀 'ex_'）做完整补全

用法:
    python agent_service/planner/fill_exercises_met.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_CFG = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "fitness"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "666666"),
)

# ═══════════════════════════════════════════════════════════════════════════
# 标准 MET 数据库
# 来源:
#   - Ainsworth BE, et al. 2011 Compendium of Physical Activities.
#     Med Sci Sports Exerc. 2011;43(8):1575-1581.
#   - ACSM Guidelines for Exercise Testing and Prescription, 10th ed.
#   - Pérez-Castilla A, et al. Strength & Cond J (specific exercises)
#
# 有氧: 直接来自 Compendium 代码
# 力量: 来自研究文献实测值（EMG + VO2 测量）
# ═══════════════════════════════════════════════════════════════════════════

# 中文动作名 → 完整字段数据
ZH_REFERENCE: dict[str, dict] = {
    # ─── 胸部 ────────────────────────────────────────────────────────────────
    "平板卧推": {
        "estimated_mets": 5.5,   # Bench press ~5.1-5.5 (Smith et al.)
        "movement_pattern": "horizontal_push",
        "equipment": ["杠铃", "训练凳"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 5, "max": 12},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "上斜卧推": {
        "estimated_mets": 5.5,
        "movement_pattern": "incline_push",
        "equipment": ["杠铃", "训练凳"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 8, "max": 12},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "下斜卧推": {
        "estimated_mets": 5.5,
        "movement_pattern": "decline_push",
        "equipment": ["杠铃", "训练凳"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 8, "max": 12},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["triceps"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "哑铃卧推": {
        "estimated_mets": 5.0,
        "movement_pattern": "horizontal_push",
        "equipment": ["哑铃", "训练凳"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌", "稳定性"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "哑铃上斜卧推": {
        "estimated_mets": 5.0,
        "movement_pattern": "incline_push",
        "equipment": ["哑铃", "训练凳"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "哑铃飞鸟": {
        "estimated_mets": 4.0,
        "movement_pattern": "horizontal_push",
        "equipment": ["哑铃", "训练凳"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌", "拉伸胸肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 15},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "夹胸": {
        "estimated_mets": 4.0,
        "movement_pattern": "horizontal_push",
        "equipment": ["蝴蝶机"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["chest"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "绳索夹胸": {
        "estimated_mets": 4.5,
        "movement_pattern": "horizontal_push",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["chest"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "俯卧撑": {
        "estimated_mets": 3.8,   # Compendium 02020: push-ups 3.8
        "movement_pattern": "horizontal_push",
        "equipment": ["自重"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌", "耐力提升"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 30},
        "primary_muscles": ["chest", "triceps"],
        "secondary_muscles": ["front-shoulders"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "史密斯卧推": {
        "estimated_mets": 5.0,
        "movement_pattern": "horizontal_push",
        "equipment": ["史密斯架", "训练凳"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 12},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "上斜推胸": {
        "estimated_mets": 5.0,
        "movement_pattern": "incline_push",
        "equipment": ["悍马机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "平板推胸": {
        "estimated_mets": 5.0,
        "movement_pattern": "horizontal_push",
        "equipment": ["悍马机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["front-shoulders", "triceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "下斜推胸": {
        "estimated_mets": 5.0,
        "movement_pattern": "decline_push",
        "equipment": ["悍马机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["chest"],
        "secondary_muscles": ["triceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    # ─── 背部 ────────────────────────────────────────────────────────────────
    "高位下拉": {
        "estimated_mets": 5.0,
        "movement_pattern": "vertical_pull",
        "equipment": ["高位下拉机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["lats"],
        "secondary_muscles": ["biceps", "rear-shoulders"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "引体向上": {
        "estimated_mets": 8.0,
        "movement_pattern": "vertical_pull",
        "equipment": ["单杠"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升", "自重训练"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 3, "max": 15},
        "primary_muscles": ["lats"],
        "secondary_muscles": ["biceps", "rear-shoulders"],
        "fatigue_score": {"local": 4, "systemic": 2},
    },
    "坐姿划船": {
        "estimated_mets": 4.5,
        "movement_pattern": "horizontal_pull",
        "equipment": ["坐姿划船机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["lats", "traps-middle"],
        "secondary_muscles": ["biceps", "rear-shoulders"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "杠铃划船": {
        "estimated_mets": 6.0,
        "movement_pattern": "horizontal_pull",
        "equipment": ["杠铃"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 5, "max": 12},
        "primary_muscles": ["lats", "traps-middle"],
        "secondary_muscles": ["biceps", "lowerback"],
        "fatigue_score": {"local": 4, "systemic": 2},
    },
    "哑铃划船": {
        "estimated_mets": 5.0,
        "movement_pattern": "horizontal_pull",
        "equipment": ["哑铃", "训练凳"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["lats"],
        "secondary_muscles": ["biceps", "rear-shoulders"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "绳索划船": {
        "estimated_mets": 4.5,
        "movement_pattern": "horizontal_pull",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 15},
        "primary_muscles": ["lats", "traps-middle"],
        "secondary_muscles": ["biceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "绳索下拉": {
        "estimated_mets": 4.5,
        "movement_pattern": "vertical_pull",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 15},
        "primary_muscles": ["lats"],
        "secondary_muscles": ["biceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "面拉": {
        "estimated_mets": 3.5,
        "movement_pattern": "horizontal_pull",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌", "纠正姿态"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["rear-shoulders", "traps-middle"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 1, "systemic": 1},
    },
    "悍马高位下拉": {
        "estimated_mets": 5.0,
        "movement_pattern": "vertical_pull",
        "equipment": ["悍马机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["lats"],
        "secondary_muscles": ["biceps", "rear-shoulders"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "悍马划船": {
        "estimated_mets": 5.0,
        "movement_pattern": "horizontal_pull",
        "equipment": ["悍马机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["lats", "traps-middle"],
        "secondary_muscles": ["biceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    # ─── 腿部 ────────────────────────────────────────────────────────────────
    "深蹲": {
        "estimated_mets": 6.0,   # Compendium 02080: squats 5.0; research 5-8 depending on load
        "movement_pattern": "squat",
        "equipment": ["杠铃", "深蹲架"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 5, "max": 12},
        "primary_muscles": ["quads", "glutes"],
        "secondary_muscles": ["hamstrings", "lowerback"],
        "fatigue_score": {"local": 5, "systemic": 4},
    },
    "史密斯深蹲": {
        "estimated_mets": 5.5,
        "movement_pattern": "squat",
        "equipment": ["史密斯架"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["quads", "glutes"],
        "secondary_muscles": ["hamstrings"],
        "fatigue_score": {"local": 4, "systemic": 3},
    },
    "史密斯推举": {
        "estimated_mets": 5.0,
        "movement_pattern": "vertical_push",
        "equipment": ["史密斯架"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 12},
        "primary_muscles": ["front-shoulders"],
        "secondary_muscles": ["triceps", "traps"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "腿举": {
        "estimated_mets": 5.5,
        "movement_pattern": "squat",
        "equipment": ["腿举机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 20},
        "primary_muscles": ["quads", "glutes"],
        "secondary_muscles": ["hamstrings"],
        "fatigue_score": {"local": 4, "systemic": 2},
    },
    "硬拉": {
        "estimated_mets": 6.0,
        "movement_pattern": "hinge",
        "equipment": ["杠铃"],
        "difficulty": "advanced",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "high",
        "recommended_rep_range": {"min": 3, "max": 8},
        "primary_muscles": ["hamstrings", "lowerback"],
        "secondary_muscles": ["glutes", "traps", "lats"],
        "fatigue_score": {"local": 5, "systemic": 5},
    },
    "罗马尼亚硬拉": {
        "estimated_mets": 5.5,
        "movement_pattern": "hinge",
        "equipment": ["杠铃"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 8, "max": 12},
        "primary_muscles": ["hamstrings", "glutes"],
        "secondary_muscles": ["lowerback"],
        "fatigue_score": {"local": 4, "systemic": 3},
    },
    "箭步蹲": {
        "estimated_mets": 4.0,
        "movement_pattern": "lunge",
        "equipment": ["自重", "哑铃"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌", "平衡训练"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 20},
        "primary_muscles": ["quads", "glutes"],
        "secondary_muscles": ["hamstrings"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "腿弯举": {
        "estimated_mets": 4.0,
        "movement_pattern": "knee_flexion",
        "equipment": ["腿弯举机"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 15},
        "primary_muscles": ["hamstrings"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "腿伸展": {
        "estimated_mets": 4.0,
        "movement_pattern": "knee_extension",
        "equipment": ["腿伸展机"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌", "康复训练"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 20},
        "primary_muscles": ["quads"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "提踵": {
        "estimated_mets": 3.5,
        "movement_pattern": "plantar_flexion",
        "equipment": ["自重", "提踵机"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 15, "max": 30},
        "primary_muscles": ["calves"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    # ─── 肩部 ────────────────────────────────────────────────────────────────
    "杠铃推举": {
        "estimated_mets": 5.5,
        "movement_pattern": "vertical_push",
        "equipment": ["杠铃"],
        "difficulty": "intermediate",
        "exercise_type": "compound",
        "training_goals": ["增肌", "力量提升"],
        "risk_level": "medium",
        "recommended_rep_range": {"min": 5, "max": 10},
        "primary_muscles": ["front-shoulders"],
        "secondary_muscles": ["triceps", "traps"],
        "fatigue_score": {"local": 3, "systemic": 2},
    },
    "哑铃推举": {
        "estimated_mets": 5.0,
        "movement_pattern": "vertical_push",
        "equipment": ["哑铃"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["front-shoulders"],
        "secondary_muscles": ["triceps", "traps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "哑铃侧平举": {
        "estimated_mets": 3.0,
        "movement_pattern": "abduction",
        "equipment": ["哑铃"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["front-shoulders"],
        "secondary_muscles": ["rear-shoulders"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "推肩": {
        "estimated_mets": 5.0,
        "movement_pattern": "vertical_push",
        "equipment": ["推肩机"],
        "difficulty": "beginner",
        "exercise_type": "compound",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["front-shoulders"],
        "secondary_muscles": ["triceps"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    # ─── 手臂 ────────────────────────────────────────────────────────────────
    "杠铃弯举": {
        "estimated_mets": 3.5,
        "movement_pattern": "elbow_flexion",
        "equipment": ["杠铃"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 15},
        "primary_muscles": ["biceps"],
        "secondary_muscles": ["forearms"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "哑铃弯举": {
        "estimated_mets": 3.0,
        "movement_pattern": "elbow_flexion",
        "equipment": ["哑铃"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 10, "max": 15},
        "primary_muscles": ["biceps"],
        "secondary_muscles": ["forearms"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "绳索弯举": {
        "estimated_mets": 3.0,
        "movement_pattern": "elbow_flexion",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["biceps"],
        "secondary_muscles": ["forearms"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "绳索下压": {
        "estimated_mets": 3.5,
        "movement_pattern": "elbow_extension",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["triceps"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "绳索三头下压": {
        "estimated_mets": 3.5,
        "movement_pattern": "elbow_extension",
        "equipment": ["龙门架"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 12, "max": 20},
        "primary_muscles": ["triceps"],
        "secondary_muscles": [],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    # ─── 腹部/核心 ───────────────────────────────────────────────────────────
    "卷腹": {
        "estimated_mets": 2.8,   # Compendium 02030: crunches 2.8
        "movement_pattern": "spinal_flexion",
        "equipment": ["自重"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["增肌", "核心稳定"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 15, "max": 30},
        "primary_muscles": ["abdominals"],
        "secondary_muscles": ["obliques"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "平板支撑": {
        "estimated_mets": 3.0,
        "movement_pattern": "isometric",
        "equipment": ["自重"],
        "difficulty": "beginner",
        "exercise_type": "isolation",
        "training_goals": ["核心稳定", "耐力提升"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 20, "max": 120},
        "primary_muscles": ["abdominals", "obliques"],
        "secondary_muscles": ["lowerback"],
        "fatigue_score": {"local": 2, "systemic": 1},
    },
    "悬垂举腿": {
        "estimated_mets": 4.0,
        "movement_pattern": "hip_flexion",
        "equipment": ["单杠"],
        "difficulty": "intermediate",
        "exercise_type": "isolation",
        "training_goals": ["增肌", "核心稳定"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 20},
        "primary_muscles": ["abdominals"],
        "secondary_muscles": ["obliques"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    "悬垂抬腿": {
        "estimated_mets": 4.0,
        "movement_pattern": "hip_flexion",
        "equipment": ["单杠"],
        "difficulty": "intermediate",
        "exercise_type": "isolation",
        "training_goals": ["增肌", "核心稳定"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 8, "max": 20},
        "primary_muscles": ["abdominals"],
        "secondary_muscles": ["obliques"],
        "fatigue_score": {"local": 3, "systemic": 1},
    },
    # ─── 有氧 ────────────────────────────────────────────────────────────────
    "跑步": {
        # Compendium 02025: Running 8.0 km/h = 8.3 METs
        "estimated_mets": 8.3,
        "movement_pattern": "locomotion",
        "equipment": ["跑步机"],
        "difficulty": "beginner",
        "exercise_type": "cardio",
        "training_goals": ["有氧耐力", "减脂"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 20, "max": 60},
        "primary_muscles": ["quads", "hamstrings", "calves"],
        "secondary_muscles": ["glutes"],
        "fatigue_score": {"local": 3, "systemic": 4},
    },
    "快走": {
        # Compendium 17151: Walking brisk 6.4 km/h = 4.3 METs
        "estimated_mets": 4.3,
        "movement_pattern": "locomotion",
        "equipment": ["跑步机"],
        "difficulty": "beginner",
        "exercise_type": "cardio",
        "training_goals": ["有氧耐力", "减脂"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 30, "max": 60},
        "primary_muscles": ["quads", "hamstrings", "calves"],
        "secondary_muscles": ["glutes"],
        "fatigue_score": {"local": 2, "systemic": 2},
    },
    "椭圆机": {
        # Compendium 02070: Elliptical moderate = 5.0 METs
        "estimated_mets": 5.0,
        "movement_pattern": "locomotion",
        "equipment": ["椭圆机"],
        "difficulty": "beginner",
        "exercise_type": "cardio",
        "training_goals": ["有氧耐力", "减脂"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 20, "max": 60},
        "primary_muscles": ["quads", "hamstrings"],
        "secondary_muscles": ["glutes", "calves"],
        "fatigue_score": {"local": 2, "systemic": 3},
    },
    "动感单车": {
        # Compendium 01060: Stationary bike moderate (51-89W) = 5.5
        # Compendium 01070: vigorous (>90W) = 8.8
        # spin class 一般中强度: 6.8 METs
        "estimated_mets": 6.8,
        "movement_pattern": "cycling",
        "equipment": ["动感单车"],
        "difficulty": "beginner",
        "exercise_type": "cardio",
        "training_goals": ["有氧耐力", "减脂"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 20, "max": 60},
        "primary_muscles": ["quads", "hamstrings"],
        "secondary_muscles": ["glutes", "calves"],
        "fatigue_score": {"local": 3, "systemic": 4},
    },
    "划船机": {
        # Compendium 02065: Rowing machine moderate = 7.0 METs
        "estimated_mets": 7.0,
        "movement_pattern": "rowing",
        "equipment": ["划船机"],
        "difficulty": "beginner",
        "exercise_type": "cardio",
        "training_goals": ["有氧耐力", "增肌", "耐力提升"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 15, "max": 45},
        "primary_muscles": ["lats", "hamstrings"],
        "secondary_muscles": ["quads", "glutes", "biceps"],
        "fatigue_score": {"local": 3, "systemic": 4},
    },
    # ─── 拉伸/其他 ───────────────────────────────────────────────────────────
    "拉伸": {
        # Compendium 13030: Stretching, hatha yoga = 2.3 METs
        "estimated_mets": 2.3,
        "movement_pattern": "flexibility",
        "equipment": ["自重"],
        "difficulty": "beginner",
        "exercise_type": "flexibility",
        "training_goals": ["柔韧性", "恢复"],
        "risk_level": "low",
        "recommended_rep_range": {"min": 15, "max": 60},
        "primary_muscles": [],
        "secondary_muscles": [],
        "fatigue_score": {"local": 1, "systemic": 1},
    },
}

# 英文动作名关键词 → Compendium 标准 MET
# 用于为从 xlsx 导入的英文动作行补充 MET（精确匹配优先，关键词后备）
EN_EXACT_MET: dict[str, float] = {
    # ── Chest ──
    "barbell bench press":          5.5,
    "dumbbell bench press":         5.0,
    "incline barbell bench press":  5.5,
    "incline dumbbell bench press": 5.0,
    "decline bench press":          5.5,
    "dumbbell fly":                 4.0,
    "cable crossover":              4.5,
    "cable fly":                    4.5,
    "pec deck fly":                 4.0,
    "push-up":                      3.8,   # Compendium 02020
    "push up":                      3.8,
    "wide grip push-up":            3.8,
    "close grip push-up":           3.8,
    # ── Back ──
    "lat pulldown":                 5.0,
    "close grip lat pulldown":      5.0,
    "wide grip lat pulldown":       5.0,
    "pull-up":                      8.0,
    "pull up":                      8.0,
    "chin-up":                      8.0,
    "chin up":                      8.0,
    "seated cable row":             4.5,
    "barbell row":                  6.0,
    "bent over barbell row":        6.0,
    "dumbbell row":                 5.0,
    "one arm dumbbell row":         5.0,
    "t-bar row":                    6.0,
    "face pull":                    3.5,
    "straight arm pulldown":        4.0,
    # ── Legs ──
    "squat":                        6.0,
    "barbell squat":                6.0,
    "goblet squat":                 5.0,
    "front squat":                  6.0,
    "leg press":                    5.5,
    "deadlift":                     6.0,
    "barbell deadlift":             6.0,
    "romanian deadlift":            5.5,
    "stiff leg deadlift":           5.5,
    "lunge":                        4.0,
    "walking lunge":                4.0,
    "leg curl":                     4.0,
    "lying leg curl":               4.0,
    "seated leg curl":              4.0,
    "leg extension":                4.0,
    "calf raise":                   3.5,
    "standing calf raise":          3.5,
    "seated calf raise":            3.5,
    "hip thrust":                   4.5,
    "barbell hip thrust":           4.5,
    "glute bridge":                 3.5,
    "sumo deadlift":                6.0,
    # ── Shoulders ──
    "overhead press":               5.5,
    "barbell overhead press":       5.5,
    "dumbbell shoulder press":      5.0,
    "arnold press":                 5.0,
    "lateral raise":                3.0,
    "dumbbell lateral raise":       3.0,
    "front raise":                  3.0,
    "rear delt fly":                3.0,
    "upright row":                  4.5,
    "barbell shrug":                4.0,
    "dumbbell shrug":               4.0,
    # ── Arms ──
    "barbell curl":                 3.5,
    "dumbbell curl":                3.0,
    "hammer curl":                  3.0,
    "preacher curl":                3.0,
    "cable curl":                   3.0,
    "concentration curl":           3.0,
    "tricep pushdown":              3.5,
    "tricep push down":             3.5,
    "cable tricep pushdown":        3.5,
    "skull crusher":                3.5,
    "lying tricep extension":       3.5,
    "overhead tricep extension":    3.5,
    "close grip bench press":       4.5,
    "tricep dip":                   4.5,
    # ── Core ──
    "crunch":                       2.8,   # Compendium 02030
    "sit-up":                       3.0,   # Compendium 02035
    "sit up":                       3.0,
    "plank":                        3.0,
    "side plank":                   3.0,
    "leg raise":                    4.0,
    "hanging leg raise":            4.0,
    "cable crunch":                 3.5,
    "ab wheel rollout":             4.5,
    "russian twist":                3.5,
    "mountain climber":             8.0,   # Compendium 02040
    # ── Cardio ──
    "treadmill":                    8.3,
    "elliptical":                   5.0,
    "stationary bike":              6.8,
    "rowing machine":               7.0,
    "jump rope":                    11.0,  # Compendium 15551
    "burpee":                       8.0,
}

# 关键词后备 MET（当精确匹配失败时）
EN_KEYWORD_MET: list[tuple[str, float]] = [
    ("pull-up",      8.0), ("pullup",    8.0), ("chin up",  8.0), ("chin-up", 8.0),
    ("push-up",      3.8), ("pushup",    3.8), ("push up",  3.8),
    ("deadlift",     6.0), ("squat",     6.0), ("lunge",    4.0),
    ("leg press",    5.5), ("leg curl",  4.0), ("leg extension", 4.0),
    ("bench press",  5.5), ("overhead",  5.5), ("shoulder press", 5.0),
    ("lat pulldown", 5.0), ("row",       5.0),
    ("curl",         3.0), ("pushdown",  3.5), ("tricep",   3.5),
    ("lateral raise",3.0), ("fly",       4.0), ("crunch",   2.8),
    ("plank",        3.0), ("raise",     3.5),
    ("treadmill",    8.3), ("elliptical",5.0), ("bike",     6.8),
    ("rowing",       7.0), ("cardio",    6.0),
]

# exercise_type/difficulty 兜底 MET（无任何名称匹配时）
FALLBACK_MET: dict[tuple, float] = {
    ("compound",  "beginner"):     4.0,
    ("compound",  "intermediate"): 5.0,
    ("compound",  "advanced"):     6.0,
    ("isolation", "beginner"):     3.0,
    ("isolation", "intermediate"): 3.5,
    ("isolation", "advanced"):     4.0,
    ("cardio",    "beginner"):     5.0,
    ("cardio",    "intermediate"): 6.5,
    ("cardio",    "advanced"):     8.0,
}


# ═══════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════

def is_empty(v) -> bool:
    """判断一个字段是否为空/默认值。"""
    if v is None:
        return True
    if isinstance(v, (list, dict)) and not v:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def resolve_met(name: str, name_cn: str, ex_type: str, difficulty: str) -> float | None:
    """按优先级查找标准 MET。"""
    # 1. 中文名精确匹配
    if name_cn and name_cn in ZH_REFERENCE:
        return ZH_REFERENCE[name_cn]["estimated_mets"]
    # 2. 英文名精确匹配（小写）
    nl = (name or "").lower().strip()
    if nl in EN_EXACT_MET:
        return EN_EXACT_MET[nl]
    # 3. 英文名关键词匹配
    for kw, met in EN_KEYWORD_MET:
        if kw in nl:
            return met
    # 4. 按类型/难度兜底
    key = (ex_type or "compound", difficulty or "beginner")
    return FALLBACK_MET.get(key, 4.0)


def build_patch(row: dict) -> dict:
    """给一行 exercise 记录生成需要更新的字段字典。"""
    name_cn  = row.get("name_cn") or ""
    name     = row.get("name")    or ""
    ex_type  = row.get("exercise_type") or ""
    diff     = row.get("difficulty")    or ""

    patch: dict = {}

    # ── estimated_mets：始终用标准值覆盖 ──────────────────────────────────
    met = resolve_met(name, name_cn, ex_type, diff)
    if met is not None:
        patch["estimated_mets"] = met

    # ── 其余字段：仅当为空时才注入 ────────────────────────────────────────
    ref = ZH_REFERENCE.get(name_cn, {})

    for field in ("movement_pattern", "difficulty", "exercise_type", "risk_level"):
        if is_empty(row.get(field)) and field in ref:
            patch[field] = ref[field]

    for field in ("primary_muscles", "secondary_muscles", "equipment",
                  "training_goals", "recommended_rep_range", "fatigue_score"):
        if is_empty(row.get(field)) and field in ref:
            patch[field] = ref[field]

    return patch


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main(dry_run: bool = False):
    conn = psycopg2.connect(**DB_CFG, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()

    # 1. 读取所有行
    cur.execute("""
        SELECT exercise_id, name, name_cn,
               primary_muscles, secondary_muscles,
               movement_pattern, equipment, difficulty,
               training_goals, exercise_type,
               recommended_rep_range, risk_level,
               estimated_mets, fatigue_score
        FROM exercises
        ORDER BY exercise_id
    """)
    rows = cur.fetchall()
    print(f"\n共读取 {len(rows)} 条动作记录")

    # 2. 分析空字段分布
    CHECKED = ["movement_pattern", "equipment", "difficulty", "exercise_type",
               "risk_level", "training_goals", "recommended_rep_range",
               "primary_muscles", "secondary_muscles", "estimated_mets", "fatigue_score"]
    empty_counts: dict[str, int] = {f: 0 for f in CHECKED}
    for row in rows:
        for f in CHECKED:
            if is_empty(row.get(f)):
                empty_counts[f] += 1

    print("\n--- 空字段统计 ---")
    for f, cnt in empty_counts.items():
        if cnt:
            print(f"  {f:30s}: {cnt} 行为空")

    # 3. 生成并执行更新
    updated = 0
    met_only = 0
    skipped  = 0

    for row in rows:
        patch = build_patch(dict(row))
        if not patch:
            skipped += 1
            continue

        # 分离 JSONB 字段和普通字段
        JSONB_FIELDS = {"primary_muscles", "secondary_muscles", "equipment",
                        "training_goals", "recommended_rep_range", "fatigue_score"}
        set_parts = []
        values    = []
        for k, v in patch.items():
            if k in JSONB_FIELDS:
                set_parts.append(f"{k} = %s::jsonb")
                values.append(json.dumps(v, ensure_ascii=False))
            else:
                set_parts.append(f"{k} = %s")
                values.append(v)
        values.append(row["exercise_id"])

        sql = f"UPDATE exercises SET {', '.join(set_parts)} WHERE exercise_id = %s"

        only_met = list(patch.keys()) == ["estimated_mets"]
        tag = "(MET only)" if only_met else str(list(patch.keys()))
        print(f"  {'[DRY]' if dry_run else 'UPD '} {row['exercise_id']:40s} → {tag}")

        if not dry_run:
            cur.execute(sql, values)

        updated += 1
        if only_met:
            met_only += 1

    if not dry_run:
        conn.commit()

    conn.close()

    print(f"\n{'[DRY RUN] ' if dry_run else ''}结果：")
    print(f"  总行数    : {len(rows)}")
    print(f"  更新行数  : {updated}  (其中仅补 MET: {met_only})")
    print(f"  无需更新  : {skipped}")
    if not dry_run:
        print("  [OK] 已提交到数据库")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
