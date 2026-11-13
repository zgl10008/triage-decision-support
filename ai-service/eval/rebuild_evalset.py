# -*- coding: utf-8 -*-
"""
重构评测集构成 —— 让类别占比匹配真实使用分布
=====================================================================
动机：救援人员现场用语音/口语描述伤情，几乎不会精确报标准伤情名。
原评测集 exact 占 81%（100/123），严重高估精确名的真实占比，导致"整体 Recall"
被 100 条本就满分的 exact 稀释，掩盖了语义检索在难例上的价值。

重构后（150 条）：
  exact      30   —— 精确名是"理想输入"，从原 100 条均匀抽样保留作对照
  paraphrase 40   —— 近义改写（原 13 + 新 27）
  symptom    60   —— 口语症状（原 10 + 扩展 30 + 新 20）
  offtopic   20   —— 干扰拒答（原 10 + 新 10）
  难例 n = 100（para+symptom），占命中样本 77%。

原则：先定答案再跑分，跑完不回改；难例覆盖"有中有不中"的自然难度分布，
不 cherry-pick 好中的样本。

用法：python eval/rebuild_evalset.py
产物：eval/eval_queries_rebuilt.json
"""
import json
import os

from extend_symptom import EXTRA_SYMPTOMS as EXTRA_SYMPTOMS_30

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))

# 新写 27 条近义改写（paraphrase，大白话命名性改写）
NEW_PARAPHRASE = [
    {"id": "para_14", "category": "paraphrase", "query": "半边脸被弹片打烂了", "expected": "颌面部伤"},
    {"id": "para_15", "category": "paraphrase", "query": "脖子被弹片划开一道大口子，血止不住", "expected": "颈部损伤"},
    {"id": "para_16", "category": "paraphrase", "query": "脖子中了一枪，全身都动不了", "expected": "颈椎枪伤伴瘫痪"},
    {"id": "para_17", "category": "paraphrase", "query": "脖子被弹片打中，手脚都没知觉了", "expected": "颈部弹片伤伴高位脊髓损伤"},
    {"id": "para_18", "category": "paraphrase", "query": "胸口被子弹打了个对穿", "expected": "胸部枪弹伤"},
    {"id": "para_19", "category": "paraphrase", "query": "胸口被重物狠狠撞了一下", "expected": "胸部撞击伤"},
    {"id": "para_20", "category": "paraphrase", "query": "胸口被弹片打进去，喘气都费劲", "expected": "胸部弹片伤(2)"},
    {"id": "para_21", "category": "paraphrase", "query": "子弹从胸口穿到了肚子里", "expected": "火器性胸腹联合伤"},
    {"id": "para_22", "category": "paraphrase", "query": "胸和肚子一起被打穿了", "expected": "胸腹联合伤"},
    {"id": "para_23", "category": "paraphrase", "query": "肚子被弹片打中，疼得受不了", "expected": "胰腺穿透伤"},
    {"id": "para_24", "category": "paraphrase", "query": "肚子被塌下来的墙砸了", "expected": "小肠钝性伤"},
    {"id": "para_25", "category": "paraphrase", "query": "肚皮被弹片划开一道口子", "expected": "腹壁损伤"},
    {"id": "para_26", "category": "paraphrase", "query": "大腿被弹片打中了", "expected": "大腿弹片伤"},
    {"id": "para_27", "category": "paraphrase", "query": "大腿被弹片打进一个洞", "expected": "大腿盲管伤"},
    {"id": "para_28", "category": "paraphrase", "query": "腿上被弹片打了个对穿", "expected": "体表贯通伤"},
    {"id": "para_29", "category": "paraphrase", "query": "手腕的血管被弹片打断了", "expected": "桡动脉损伤"},
    {"id": "para_30", "category": "paraphrase", "query": "屁股被弹片炸开一道口子", "expected": "臀部软组织开放伤"},
    {"id": "para_31", "category": "paraphrase", "query": "裆部和屁股被炸裂了", "expected": "会阴部、臀部皮肤软组织裂伤"},
    {"id": "para_32", "category": "paraphrase", "query": "腰被弹片打中，腿没知觉了", "expected": "腰椎弹片伤"},
    {"id": "para_33", "category": "paraphrase", "query": "头骨被砸碎了", "expected": "粉碎性颅骨骨折"},
    {"id": "para_34", "category": "paraphrase", "query": "脑袋被钝器砸开，血和脑浆往外流", "expected": "非火器性开放性颅脑伤"},
    {"id": "para_35", "category": "paraphrase", "query": "头和胸口都受了伤", "expected": "颅脑伤合并胸部伤"},
    {"id": "para_36", "category": "paraphrase", "query": "头和骨盆都被打伤了", "expected": "颅脑伤合并骨盆损伤"},
    {"id": "para_37", "category": "paraphrase", "query": "皮肤沾了毒气，起了一片大水疱", "expected": "重度芥子气中毒"},
    {"id": "para_38", "category": "paraphrase", "query": "受了核辐射，又吐又拉还发高烧", "expected": "重度骨髓型放射病"},
    {"id": "para_39", "category": "paraphrase", "query": "核辐射后不停抽搐，人已经不清醒", "expected": "脑型放射病"},
    {"id": "para_40", "category": "paraphrase", "query": "浑身被汽油弹烧了，人已经休克", "expected": "大面积烧伤(伴休克)"},
]

# 新写 20 条口语症状（symptom，口语化症状描述，刻意含模糊/弱信号难例）
NEW_SYMPTOM = [
    {"id": "symp_41", "category": "symptom", "query": "胸壁上被子弹擦出一道血口子，血没怎么往胸腔里流", "expected": "胸壁枪弹伤(切线伤)"},
    {"id": "symp_42", "category": "symptom", "query": "被爆炸的气浪掀翻，胳膊腿好几处都变形了", "expected": "爆炸伤，多发骨折"},
    {"id": "symp_43", "category": "symptom", "query": "水里爆炸震到肚子，疼得厉害还一直胀气", "expected": "水下腹部冲击伤"},
    {"id": "symp_44", "category": "symptom", "query": "被火烧了还吸进烟，憋得喘不上气", "expected": "烧伤合并吸入性损伤"},
    {"id": "symp_45", "category": "symptom", "query": "船被炸了一下，肚子疼，大腿也疼得不能动", "expected": "舰船冲击伤"},
    {"id": "symp_46", "category": "symptom", "query": "被重物砸到胯骨，疼得走不了路", "expected": "骨盆闭合伤"},
    {"id": "symp_47", "category": "symptom", "query": "膝盖后窝被弹片打中，血喷得厉害，人发虚", "expected": "膝部弹片伤伴血管损伤"},
    {"id": "symp_48", "category": "symptom", "query": "被微波照过后，头疼头晕，心慌睡不着", "expected": "中度微波武器损伤"},
    {"id": "symp_49", "category": "symptom", "query": "胸和肚子都受伤了，又泡了海水，全身冰凉", "expected": "胸腹联合伤合并海水浸泡"},
    {"id": "symp_50", "category": "symptom", "query": "腰被撞了，腿不能动，又泡了海水", "expected": "脊柱脊髓损伤合并海水浸泡"},
    {"id": "symp_51", "category": "symptom", "query": "肚子被弹片打开，肠子露出来，又泡了海水", "expected": "腹部开放性损伤合并海水浸泡"},
    {"id": "symp_52", "category": "symptom", "query": "胸口被打穿，泡了海水，喘不上气", "expected": "胸部开放性损伤合并海水浸泡"},
    {"id": "symp_53", "category": "symptom", "query": "腿被弹片炸伤，又泡了海水，脚冰凉", "expected": "肢体弹片伤合并海水浸泡"},
    {"id": "symp_54", "category": "symptom", "query": "肚皮被弹片掀掉一块，泡了海水", "expected": "腹壁软组织缺损合并海水浸泡"},
    {"id": "symp_55", "category": "symptom", "query": "身上烧伤了，又掉进海里，人发冷犯迷糊", "expected": "烧伤合并海水浸泡"},
    {"id": "symp_56", "category": "symptom", "query": "被炸又被烧，还泡了海水，胸口发闷", "expected": "烧冲复合伤合并海水浸泡"},
    {"id": "symp_57", "category": "symptom", "query": "小腿被弹片炸伤又烧伤，泡了海水，体温很低", "expected": "弹烧复合伤合并海水浸泡"},
    {"id": "symp_58", "category": "symptom", "query": "脸和胸口都被弹片打中，喘气费劲", "expected": "颌面部损伤合并胸部损伤"},
    {"id": "symp_59", "category": "symptom", "query": "下巴脖子被炸伤，口鼻流血，又泡了海水", "expected": "颌面颈部伤合并海水浸泡"},
    {"id": "symp_60", "category": "symptom", "query": "胸口被砸了，腿也被压了几个小时，尿很少", "expected": "胸部伤合并及下肢挤压伤"},
]

# 新写 10 条无关干扰（offtopic，expected 为空）
NEW_OFFTOPIC = [
    {"id": "off_11", "category": "offtopic", "query": "今天中午吃什么", "expected": ""},
    {"id": "off_12", "category": "offtopic", "query": "帮我查一下航班", "expected": ""},
    {"id": "off_13", "category": "offtopic", "query": "这个月工资多少", "expected": ""},
    {"id": "off_14", "category": "offtopic", "query": "怎么减肥", "expected": ""},
    {"id": "off_15", "category": "offtopic", "query": "讲个笑话", "expected": ""},
    {"id": "off_16", "category": "offtopic", "query": "附近有什么好吃的", "expected": ""},
    {"id": "off_17", "category": "offtopic", "query": "帮我写作业", "expected": ""},
    {"id": "off_18", "category": "offtopic", "query": "股票怎么买", "expected": ""},
    {"id": "off_19", "category": "offtopic", "query": "今天几号", "expected": ""},
    {"id": "off_20", "category": "offtopic", "query": "帮我定个闹钟", "expected": ""},
]

# exact 从 100 条均匀抽 30 条（步长 3：索引 0,3,6,...,87），覆盖颅脑/颈/胸/腹/四肢/复合/海水/烧伤等
EXACT_STEP = 3
EXACT_COUNT = 30


def main():
    src = os.path.join(EVAL_DIR, "eval_queries_v2.json")
    dst = os.path.join(EVAL_DIR, "eval_queries_rebuilt.json")

    with open(src, encoding="utf-8") as f:
        cases = json.load(f)

    exact = [c for c in cases if c["category"] == "exact"]
    para_old = [c for c in cases if c["category"] == "paraphrase"]
    symp_old = [c for c in cases if c["category"] == "symptom"]
    off_old = [c for c in cases if c["category"] == "offtopic"]

    # 均匀抽样 30 条 exact（确定性、可复现）
    exact_30 = exact[0:EXACT_STEP * EXACT_COUNT:EXACT_STEP]

    rebuilt = exact_30 + para_old + symp_old + EXTRA_SYMPTOMS_30 + \
        NEW_PARAPHRASE + NEW_SYMPTOM + off_old + NEW_OFFTOPIC

    # 校验 id 唯一 + expected 非空（除 offtopic）
    ids = [c["id"] for c in rebuilt]
    assert len(ids) == len(set(ids)), "存在重复 id"
    for c in rebuilt:
        if c["category"] != "offtopic":
            assert c["expected"], "{} 缺 expected".format(c["id"])

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(rebuilt, f, ensure_ascii=False, indent=2)

    from collections import Counter
    cnt = Counter(c["category"] for c in rebuilt)
    print("已写入 {}：共 {} 条，构成={}".format(dst, len(rebuilt), dict(cnt)))


if __name__ == "__main__":
    main()
