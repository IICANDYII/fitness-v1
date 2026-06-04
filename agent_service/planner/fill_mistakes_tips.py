"""为 id=212(跑步机慢跑) 和 id=213(悬垂举腿) 补全 common_mistakes / safety_tips / contraindications。"""
import psycopg2, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = psycopg2.connect(host='localhost', port=5432, dbname='fitness',
                        user='postgres', password='666666')
cur = conn.cursor()

ROWS = {
    "treadmill_jog_001": {
        "common_mistakes": [
            "步幅过大（过跨步），脚跟大力砸地，膝关节冲击力增加",
            "含胸驼背，重心前倾过度，腰背肌群代偿",
            "双手抓扶手支撑体重，实际运动强度远低于目标",
            "速度突然加大而无热身适应，跟腱和膝关节应激风险高",
            "长时间以同一速度慢跑导致注意力分散、步态紊乱",
        ],
        "safety_tips": [
            "启动前先以 4–5 km/h 步行 3–5 分钟热身，再逐渐提速",
            "穿专业跑鞋，确保足弓支撑与缓震性能，避免平底休闲鞋",
            "用心率监控强度：有氧目标区间为最大心率的 60%–75%",
            "跑完后以 4 km/h 慢走 2–3 分钟缓冲，防止血液淤积下肢",
            "保持目光平视前方，双臂自然前后摆动，不要左右晃动",
        ],
        "contraindications": [
            "急性踝关节或膝关节扭伤/韧带损伤期间",
            "未经心血管科医生评估的严重心肺疾病患者",
            "严重骨质疏松（T 值 ≤ −2.5）伴平衡障碍者",
            "下肢应力性骨折或骨裂急性期",
        ],
    },
    "hanging_leg_raise_001": {
        "common_mistakes": [
            "用惯性摆腿而非腹肌主动发力，髋屈肌过度代偿",
            "腿下落时不加控制，借重力反弹，失去离心收缩刺激",
            "耸肩、斜方肌用力，肩胛带稳定性下降、颈部紧张",
            "腰部反弓（前凸），骨盆未能完成后倾，下腹肌群参与不足",
            "握力不足时通过摇摆身体借力，核心控制完全丧失",
        ],
        "safety_tips": [
            "全程保持腹部收紧、骨盆微后倾，以腹直肌发力带动腿部上抬",
            "握力不足时使用助力带或腕托，避免因松手意外落地",
            "初学者先做屈膝版（Hanging Knee Raise）再进阶至直腿",
            "上升与下降均采用 2–3 秒控制速度，避免甩腿",
            "肩关节充分热身后再挂杆，主动下压肩胛以保持肩袖稳定",
        ],
        "contraindications": [
            "肩关节不稳、急性肩袖撕裂或肩峰撞击综合征急性期",
            "腰椎间盘突出急性发作期（屈髋动作会增加椎间盘压力）",
            "腕部或肘部急性骨折/韧带损伤期间",
            "上肢握力严重不足（如手术后早期恢复阶段）",
        ],
    },
}

for eid, data in ROWS.items():
    cur.execute("""
        UPDATE exercises
        SET common_mistakes   = %s::jsonb,
            safety_tips       = %s::jsonb,
            contraindications = %s::jsonb
        WHERE exercise_id = %s
        RETURNING id, name
    """, (
        json.dumps(data["common_mistakes"],   ensure_ascii=False),
        json.dumps(data["safety_tips"],       ensure_ascii=False),
        json.dumps(data["contraindications"], ensure_ascii=False),
        eid,
    ))
    row = cur.fetchone()
    if row:
        print(f"  [OK] id={row[0]}  {row[1]} ({eid})")
        print(f"       common_mistakes   : {len(data['common_mistakes'])} 条")
        print(f"       safety_tips       : {len(data['safety_tips'])} 条")
        print(f"       contraindications : {len(data['contraindications'])} 条")
    else:
        print(f"  [WARN] exercise_id not found: {eid}")

conn.commit()
conn.close()
print("\n完成。")
