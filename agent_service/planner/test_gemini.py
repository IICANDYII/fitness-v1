# -*- coding: utf-8 -*-
"""Quick test: LLM call for 2 exercises."""
import json
from openai import OpenAI

client = OpenAI(
    base_url="https://nextrouter.cc/v1",
    api_key="sk-gxBoLiZEqsQnwPweg2mlV6AWz0gpQJzlbtFz2rzRBYova4Fc"
)

SYSTEM = "你是专业健身教练兼运动科学专家，只返回 JSON 数组，不含任何其他内容。"
PROMPT = """为以下 2 个动作生成 JSON 数组（顺序与输入一致）：

每个对象：
{"name_cn":"...","secondary_muscles":["..."],"common_mistakes":["...","...","..."],"safety_tips":["...","..."],"contraindications":["..."],"estimated_mets":6.0,"fatigue_score":{"目标肌群":8,"中枢神经":5}}

1. 动作名=Dumbbell Goblet Squat  主要肌群=股四头肌,臀大肌  动作模式=push  难度=beginner  类型=compound
2. 动作名=Machine Pulldown  主要肌群=背阔肌,肱二头肌  动作模式=pull  难度=beginner  类型=compound

只返回 JSON 数组。"""

resp = client.chat.completions.create(
    model="gemini-3.5-flash",
    messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": PROMPT},
    ],
    temperature=0.3,
    timeout=30,
)

raw = resp.choices[0].message.content.strip()
print("Raw response:")
print(raw[:600])
print()

import re
raw_clean = re.sub(r"^```(?:json)?\s*", "", raw)
raw_clean = re.sub(r"\s*```$", "", raw_clean)
data = json.loads(raw_clean)
print(f"Parsed {len(data)} items")
for item in data:
    print(f"  {item.get('name_cn')} | mistakes={item.get('common_mistakes')} | mets={item.get('estimated_mets')}")
