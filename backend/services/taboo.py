# -*- coding: utf-8 -*-
"""禁忌引擎：规则前置过滤，识别用户饮食禁忌并生成安全提示。
命中任意禁忌 → 追加「建议您在使用本方案前咨询专业医师或注册营养师」。"""
import re

# 禁忌关键词 → (排除项说明, 追加提示)
TABOO_RULES = [
    {
        "name": "糖尿病/血糖高",
        "keywords": ["糖尿病", "血糖", "高血糖", "控糖"],
        "exclude": "高GI食物（白米饭、糯米、西瓜、果汁、蜂蜜、含糖饮料、蛋糕）",
        "tip": "建议优先选择低GI食材（糙米、燕麦、藜麦、绿叶菜、低糖水果），并严格限制精制糖与高糖水果。",
    },
    {
        "name": "高尿酸/痛风",
        "keywords": ["尿酸", "痛风", "高尿酸"],
        "exclude": "高嘌呤食物（动物内脏、浓肉汤、沙丁鱼、啤酒、海鲜贝类）",
        "tip": "建议限制嘌呤摄入，多选低嘌呤的蛋奶、蔬菜与谷物，多饮水促进排泄。",
    },
    {
        "name": "海鲜过敏",
        "keywords": ["海鲜过敏", "对海鲜过敏", "虾过敏", "鱼过敏"],
        "exclude": "全部海鲜类（鱼虾蟹贝等）",
        "tip": "建议以禽肉、瘦肉、豆制品、蛋奶作为蛋白质替代来源。",
    },
    {
        "name": "肾病",
        "keywords": ["肾病", "肾功能不全", "慢性肾炎"],
        "exclude": "高蛋白饮食方案（需限蛋白总量）",
        "tip": "建议在医师指导下控制每日蛋白质总量，并限盐限钾。",
    },
    {
        "name": "孕期",
        "keywords": ["怀孕", "孕期", "孕妇", "妊娠"],
        "exclude": "生食（生鱼片、溏心蛋）与高汞鱼类",
        "tip": "建议避免生食与高汞鱼类，营养方案需在专业医师指导下制定。",
    },
]

DISEASE_KEYWORDS = ["糖尿病", "血糖", "高血压", "肾病", "肝病", "心血管", "孕期", "怀孕", "哺乳", "术后"]

def detect_taboo(query):
    hits = []
    for rule in TABOO_RULES:
        if any(kw in query for kw in rule["keywords"]):
            hits.append(rule)
    return hits

def detect_disease(query):
    """是否涉及疾病/医疗相关，用于强制追加免责声明。"""
    return any(kw in query for kw in DISEASE_KEYWORDS)

def build_taboo_prompt(hits):
    if not hits:
        return ""
    lines = ["[用户饮食禁忌与安全提示]"]
    for h in hits:
        lines.append(f"- 识别到「{h['name']}」：推荐时排除{h['exclude']}。{h['tip']}")
    lines.append("- 必须提示：「建议您在使用本方案前咨询专业医师或注册营养师」")
    return "\n".join(lines)

DISCLAIMER = "本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师"
