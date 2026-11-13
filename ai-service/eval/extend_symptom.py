# -*- coding: utf-8 -*-
"""
扩充症状类（symptom）评测集 —— 从 recall.meta.json 的真实临床表现口语化改写
=====================================================================
原则：
1. query 用"无经验救援人员"的口语说法，不照抄知识库 recall 文本（照抄会让
   dense/sparse 双高、指标虚高），但症状必须来自该伤情的真实临床表现。
2. expected 为对应标准伤情名（recall.meta.json 里真实存在的 id）。
3. 先定答案再跑分，跑完不回改。

用法：python eval/extend_symptom.py
产物：eval/eval_queries_v3.json = eval_queries_v2.json(133 条) + 以下 30 条 symptom
"""
import json
import os

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))

# 30 条新症状：覆盖 颅脑/胸/腹/血管/四肢神经/骨盆/爆炸烧伤/中毒/放射/浸泡
EXTRA_SYMPTOMS = [
    {"id": "symp_11", "category": "symptom", "query": "脑袋被砸了一下，先晕过去又醒了，过了半小时又昏迷了", "expected": "急性硬膜外血肿"},
    {"id": "symp_12", "category": "symptom", "query": "从高处摔下来头先着地，一直昏迷还越来越重，反复吐", "expected": "急性硬膜下血肿"},
    {"id": "symp_13", "category": "symptom", "query": "头上挨了一棒子，当场就晕了，醒过来又恶心又吐", "expected": "脑挫裂伤"},
    {"id": "symp_14", "category": "symptom", "query": "出车祸摔到头，一直没醒，手脚软绵绵的，呼吸一阵一阵乱", "expected": "弥漫性脑轴索损伤"},
    {"id": "symp_15", "category": "symptom", "query": "摔了一跤磕到头，晕了两分钟，醒过来记不清当时咋摔的", "expected": "轻型脑损伤"},
    {"id": "symp_16", "category": "symptom", "query": "头部被弹片炸开，伤口里嵌着泥沙和头发，人已经休克了", "expected": "火器性开放性颅脑伤"},
    {"id": "symp_17", "category": "symptom", "query": "左胸被刀捅了，脖子上的青筋都鼓起来，血压往下掉", "expected": "左胸刃器伤(心脏穿透伤)"},
    {"id": "symp_18", "category": "symptom", "query": "胸口被弹片打穿，一喘气伤口就往外冒血还带着嘶嘶声", "expected": "胸部弹片伤(1)"},
    {"id": "symp_19", "category": "symptom", "query": "后背被重物砸了，手脚都动不了，尿也解不出来，喘不上气", "expected": "胸椎骨折伴全瘫和闭合性血气胸"},
    {"id": "symp_20", "category": "symptom", "query": "右上腹被车撞了，脸色惨白手脚冰凉，肚子胀得厉害", "expected": "肝钝性伤(伴休克)"},
    {"id": "symp_21", "category": "symptom", "query": "左上腹被弹片打穿，肚子胀，一按里面像有水在晃", "expected": "脾穿透伤(伴休克)"},
    {"id": "symp_22", "category": "symptom", "query": "腰被重物砸了，尿出来的全是红的", "expected": "肾钝性伤"},
    {"id": "symp_23", "category": "symptom", "query": "小肚子被刀刺了，尿不出来，尿里还带血", "expected": "膀胱穿透伤"},
    {"id": "symp_24", "category": "symptom", "query": "上腹被炸开，伤口往外流刚吃下去的东西", "expected": "胃穿透伤"},
    {"id": "symp_25", "category": "symptom", "query": "肚子被弹片打穿，肠子都露出来了，还往外流粪水", "expected": "结肠穿透伤"},
    {"id": "symp_26", "category": "symptom", "query": "屁股上中了一枪，拉的大便带血，肛门也往外渗血", "expected": "直肠穿透伤"},
    {"id": "symp_27", "category": "symptom", "query": "脖子被弹片打中，血一股一股往外喷", "expected": "颈外动脉损伤"},
    {"id": "symp_28", "category": "symptom", "query": "大腿根被炸伤喷血，脚背上摸不到脉了", "expected": "股动脉损伤"},
    {"id": "symp_29", "category": "symptom", "query": "膝盖后面喷血，整条小腿发凉，摸不到脉", "expected": "腘动脉损伤"},
    {"id": "symp_30", "category": "symptom", "query": "胳膊肘被弹片炸了，手有一边发麻，小指和无名指弯不了", "expected": "肘部破片伤伴尺神经损伤"},
    {"id": "symp_31", "category": "symptom", "query": "膝盖外侧中了枪，脚背发麻，脚趾头抬不起来", "expected": "膝部枪弹伤伴腓总神经损伤"},
    {"id": "symp_32", "category": "symptom", "query": "上臂中了枪，前后两个洞，胳膊抬不起来", "expected": "上臂枪弹伤"},
    {"id": "symp_33", "category": "symptom", "query": "手被雷管炸了，几个手指头都炸没了", "expected": "手部炸伤"},
    {"id": "symp_34", "category": "symptom", "query": "胯骨被枪打穿，血往外涌，还尿血", "expected": "骨盆开放伤"},
    {"id": "symp_35", "category": "symptom", "query": "船舱里爆炸，吸了一嘴烟，耳朵嗡嗡响还往外流血", "expected": "舰船舱室爆炸伤"},
    {"id": "symp_36", "category": "symptom", "query": "舱室爆炸被闪光和火燎到，眼睛又疼又看不清", "expected": "舱室爆炸眼烧伤"},
    {"id": "symp_37", "category": "symptom", "query": "吸了毒气，一开始只是咳嗽胸闷，几个小时后喘不上气，咳出粉色的沫子", "expected": "光气中毒"},
    {"id": "symp_38", "category": "symptom", "query": "吸了毒气以后胡言乱语，脸通红口干，瞳孔放得老大", "expected": "毕兹(BZ)中毒"},
    {"id": "symp_39", "category": "symptom", "query": "受了核辐射，一直狂吐，拉的是血水一样的便", "expected": "肠型放射病"},
    {"id": "symp_40", "category": "symptom", "query": "掉海里泡了好久才捞上来，体温特别低，人已经迷迷糊糊", "expected": "海水浸泡中度低体温"},
]


def main():
    src = os.path.join(EVAL_DIR, "eval_queries_v2.json")
    dst = os.path.join(EVAL_DIR, "eval_queries_v3.json")

    with open(src, encoding="utf-8") as f:
        cases = json.load(f)

    existing_ids = {c["id"] for c in cases}
    for s in EXTRA_SYMPTOMS:
        assert s["id"] not in existing_ids, "重复 id: {}".format(s["id"])

    merged = cases + EXTRA_SYMPTOMS
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    symp_total = sum(1 for c in merged if c["category"] == "symptom")
    print("已写入 {}：共 {} 条（symptom 由 10 -> {}，新增 {} 条）".format(
        dst, len(merged), symp_total, len(EXTRA_SYMPTOMS)))


if __name__ == "__main__":
    main()
