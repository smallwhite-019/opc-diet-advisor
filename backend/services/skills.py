# -*- coding: utf-8 -*-
"""Agent Skills（工具层）：LLM 通过 function calling 自主调用的能力。
每个 skill 内部仍走既有安全逻辑，双索引隔离在 retriever 内保证。"""
import json
from kb.retriever import retriever_nutrition, retriever_platform
from services import taboo, intent

def _fmt(results, k=4):
    out = []
    for r in results[:k]:
        b = r["block"]
        out.append(f"【{b['doc_name']}】{b['chapter']}·{b['section']}\n{b['text']}")
    return "\n\n".join(out)

def search_nutrition(query: str) -> str:
    """检索核心营养知识库（素材A+素材B），返回相关知识块与来源。仅用于营养/膳食/食材问题。"""
    res = retriever_nutrition.search(query)
    if not res:
        return "（营养库未检索到相关资料）"
    return _fmt(res)

def search_platform(query: str) -> str:
    """检索平台辅助资料（素材C），返回平台/会员/企业合作相关信息。仅用于平台类问题。"""
    res = retriever_platform.search(query)
    if not res:
        return "（平台库未检索到相关资料）"
    return _fmt(res)

def recommend_plan(crowd: str) -> str:
    """根据用户人群推荐膳食方案。crowd ∈ {减脂塑形, 增肌强化, 慢病调理, 控压调理}。"""
    mapping = {
        "减脂塑形": "轻盈减脂方案",
        "增肌强化": "力量增肌方案",
        "慢病调理": "稳糖调理方案",
        "控压调理": "控压饮食方案",
    }
    plan = mapping.get(crowd, "轻盈减脂方案")
    # 在营养库检索该方案
    res = retriever_nutrition.search(plan)
    if not res:
        return f"（未找到 {plan} 的详细资料）"
    return f"推荐方案：{plan}\n\n" + _fmt(res)

def check_taboo(user_text: str) -> str:
    """识别用户饮食禁忌/疾病，返回排除项与安全提示。命中疾病将须附就医提示与免责声明。"""
    hits = taboo.detect_taboo(user_text)
    if not hits:
        # 仍检测是否涉及疾病，供免责声明使用
        disease = taboo.detect_disease(user_text)
        return ("未识别到明确饮食禁忌。" +
                ("（注：涉及疾病相关，回答须附免责声明）" if disease else ""))
    lines = ["识别到以下饮食禁忌/健康状况，推荐时须排除相关食材并提示就医："]
    for h in hits:
        lines.append(f"- {h['name']}：排除{h['exclude']}。{h['tip']}")
    lines.append("- 须提示：「建议您在使用本方案前咨询专业医师或注册营养师」")
    return "\n".join(lines)

def get_crowd(user_text: str) -> str:
    """从用户文本识别健康人群标签。"""
    crowds = intent.detect_crowd(user_text)
    return "/".join(crowds) if crowds else "未明确"

# skill 注册表（供 Agent 构建 tools 参数）
SKILLS = {
    "search_nutrition": {
        "fn": search_nutrition,
        "description": "检索营养知识库（膳食指南+饮食计划），用于食材营养、膳食搭配、饮食禁忌、方案细节等营养类问题。输入为用户问题。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "营养相关检索词"}},
            "required": ["query"],
        },
    },
    "search_platform": {
        "fn": search_platform,
        "description": "检索平台资料库，用于会员价格、企业合作、平台介绍、成功案例、API开放平台等非营养类问题。输入为用户问题。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "平台相关检索词"}},
            "required": ["query"],
        },
    },
    "recommend_plan": {
        "fn": recommend_plan,
        "description": "根据用户人群推荐膳食方案（减脂塑形/增肌强化/慢病调理/控压调理）。",
        "parameters": {
            "type": "object",
            "properties": {"crowd": {"type": "string", "description": "人群标签"}},
            "required": ["crowd"],
        },
    },
    "check_taboo": {
        "fn": check_taboo,
        "description": "识别用户饮食禁忌与疾病（糖尿病/高尿酸/海鲜过敏/肾病/孕期），返回排除项与安全提示。",
        "parameters": {
            "type": "object",
            "properties": {"user_text": {"type": "string", "description": "用户原始输入"}},
            "required": ["user_text"],
        },
    },
    "get_crowd": {
        "fn": get_crowd,
        "description": "从用户文本识别健康人群标签（减脂塑形/增肌强化/慢病调理/控压调理）。",
        "parameters": {
            "type": "object",
            "properties": {"user_text": {"type": "string", "description": "用户原始输入"}},
            "required": ["user_text"],
        },
    },
}
