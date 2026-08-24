# -*- coding: utf-8 -*-
"""个人档案（规则+关键词提取）：基于用户全部历史对话，复用意图/禁忌引擎，
自动汇总健康目标、饮食禁忌、关注话题，生成结构化档案。零额外 LLM 调用，离线可用。"""
import db
from services import intent, taboo


def build_profile(user_id):
    """扫描该用户所有会话的历史消息，提取档案字段。"""
    convs = db.list_conversations(user_id)
    crowd_count = {}
    taboo_names = {}
    topics = set()
    msg_count = 0
    last_active = ""

    for conv in convs:
        cid = conv["id"]
        msgs = db.get_history(cid, limit=200)
        if not last_active and conv.get("updated_at"):
            last_active = conv.get("updated_at", "")
        for m in msgs:
            if m["role"] != "user":
                continue
            text = m["content"] or ""
            msg_count += 1
            for c in intent.detect_crowd(text):
                crowd_count[c] = crowd_count.get(c, 0) + 1
            for rule in taboo.detect_taboo(text):
                taboo_names[rule["name"]] = taboo_names.get(rule["name"], 0) + 1
            # 关注话题（关键词粗提取）
            if any(k in text for k in ["减脂", "减肥", "瘦身"]):
                topics.add("减脂/体重管理")
            if any(k in text for k in ["增肌", "健身", "肌肉"]):
                topics.add("增肌/运动营养")
            if any(k in text for k in ["血糖", "糖尿病", "控糖"]):
                topics.add("血糖管理")
            if any(k in text for k in ["血压", "高血压"]):
                topics.add("血压管理")
            if any(k in text for k in ["备孕", "怀孕", "孕期", "孕妇"]):
                topics.add("孕期营养")
            if any(k in text for k in ["早餐", "午餐", "晚餐", "加餐"]):
                topics.add("三餐搭配")
            if any(k in text for k in ["食材", "热量", "蛋白质", "碳水", "脂肪", "GI"]):
                topics.add("营养数据查询")

    goals = sorted(crowd_count.items(), key=lambda x: -x[1])
    taboos = sorted(taboo_names.items(), key=lambda x: -x[1])

    profile = {
        "user_id": user_id,
        "health_goals": [g for g, _ in goals],
        "dietary_taboos": [t for t, _ in taboos],
        "topics": sorted(topics),
        "conversation_count": len(convs),
        "user_msg_count": msg_count,
        "last_active": last_active,
        "summary": _summarize(goals, taboos, topics, convs, msg_count, last_active),
    }
    return profile


def _summarize(goals, taboos, topics, convs, msg_count, last_active):
    if msg_count == 0:
        return "暂无对话记录，开始咨询后将自动生成您的个人膳食档案。"
    parts = []
    if goals:
        parts.append("健康目标：" + "、".join(g for g, _ in goals))
    if taboos:
        parts.append("饮食禁忌：" + "、".join(t for t, _ in taboos) + "（涉及健康风险，方案将自动规避并提示就医）")
    if topics:
        parts.append("关注话题：" + "、".join(sorted(topics)))
    parts.append(f"累计对话 {len(convs)} 轮、{msg_count} 条咨询")
    if last_active:
        parts.append(f"最近活跃：{last_active}")
    return "；".join(parts) + "。"
