import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from gym_analyzer.db import _match_name

db_names = [
    '平板卧推', '上斜卧推', '史密斯深蹲', '史密斯机深蹲',
    '跑步', '跑步机慢跑', '高位下拉', '引体向上',
    '绳索夹胸', '卷腹', '悬垂举腿', '哑铃卧推',
]

cases = [
    ('史密斯深蹲',     '精确匹配'),
    ('史密斯机深蹲',   '精确匹配'),
    ('杠铃平板卧推',   '子串 → 平板卧推'),
    ('跑步机',         '子串 → 跑步'),
    ('卧推',           '编辑距离2 → 平板卧推 or 哑铃卧推'),
    ('高位下拉机',     '子串 → 高位下拉'),
    ('绳索夹胸训练',   '子串 → 绳索夹胸'),
    ('腹部卷腹',       '子串 → 卷腹'),
    ('龙门架飞鸟',     '无匹配 → 保留原名'),
]

print(f"{'输入':15s}  {'库中匹配':15s}  说明")
print('-' * 55)
for name, note in cases:
    result = _match_name(name, db_names)
    tag = '✓ matched' if result != name else '— no change'
    print(f"{name:15s}  {result:15s}  {tag}  ({note})")
