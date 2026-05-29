# -*- coding: utf-8 -*-
"""Find available models on nextrouter.cc and zchat.tech."""
from openai import OpenAI

# Try nextrouter.cc
print("=== nextrouter.cc ===")
c1 = OpenAI(base_url="https://nextrouter.cc/v1",
            api_key="sk-gxBoLiZEqsQnwPweg2mlV6AWz0gpQJzlbtFz2rzRBYova4Fc")
try:
    models = c1.models.list()
    for m in list(models)[:20]:
        print(" ", m.id)
except Exception as e:
    print("Error:", e)

# Try zchat.tech
print("\n=== zchat.tech (first 10) ===")
c2 = OpenAI(base_url="https://api.zchat.tech/v1",
            api_key="sk-G90J2FGkwO4sEPBNmaJs8XwzNCuFLat372D95AbuEQSpIhqS")
try:
    models = c2.models.list()
    for m in list(models)[:20]:
        print(" ", m.id)
except Exception as e:
    print("Error:", e)
