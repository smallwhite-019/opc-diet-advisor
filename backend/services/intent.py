# -*- coding: utf-8 -*-
"""意图路由：判断用户问题属于 营养库(nutrition) / 平台库(platform) / 闲聊无关(irrelevant)。
路由在检索之前执行，决定走哪个索引，从机制上杜绝 A/B 与 C 混淆。"""
import re

PLATFORM_KEYWORDS = [
    "会员", "标准版", "专业版", "免费版", "价格", "多少钱", "费用", "收费",
    "企业", "公司", "合作", "API", "开放平台", "白皮书", "案例", "官网",
    "客服", "热线", "联系方式", "地址", "品牌", "团队", "技术架构", "SaaS",
    "健康优选平台", " HealthPick", "健康管家", "营养师1对1", "1对1咨询",
]

# 明确闲聊/无关词：仅这些才归 irrelevant，避免误杀正常饮食提问
IRRELEVANT_KEYWORDS = [
    "你是谁", "你是什么", "能做什么", "会什么", "介绍一下你自己", "你好",
    "在吗", "谢谢", "感谢", "再见", "天气", "今天几号", "讲个笑话",
]

def classify(query):
    q = query.strip()
    if not q:
        return "irrelevant"
    # 1) 平台词优先 → 平台库（防混淆红线）
    pl = sum(1 for kw in PLATFORM_KEYWORDS if kw in q)
    if pl >= 1:
        return "platform"
    # 2) 明确闲聊词 → 功能介绍分支
    if any(kw in q for kw in IRRELEVANT_KEYWORDS):
        return "irrelevant"
    # 3) 其余默认走营养库（食材/症状/日常饮食/方案均覆盖，由 RAG 兜底拒答）
    return "nutrition"

# 人群识别（用于快捷入口与推荐）
def detect_crowd(query):
    q = query
    crowds = []
    if re.search(r"减脂|减重|减肥|瘦身|体脂|BMI|瘦", q):
        crowds.append("减脂塑形")
    if re.search(r"增肌|健身|肌肉|练肌肉|力量|蛋白粉", q):
        crowds.append("增肌强化")
    if re.search(r"血糖|糖尿病|控糖|低GI|调理|慢病", q):
        crowds.append("慢病调理")
    if re.search(r"高血压|血压高|控压|盐", q):
        crowds.append("控压调理")
    return crowds
