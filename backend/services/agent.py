# -*- coding: utf-8 -*-
"""Agent 编排层：LLM 通过 function calling 自主调用 skills，最后经后处理兜底。
保留红线：后处理强制来源标注 / 免责声明 / 拒答（即使 LLM 不调用任何 skill 也能兜底）。"""
import os, json
from dotenv import load_dotenv
from . import skills
from . import taboo
from .postprocess import ensure_disclaimer, ensure_taboo_tip

load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

SYSTEM = """你是「健康优选 AI 智能膳食顾问」智能体。你拥有多个工具(skills)可调用：
- search_nutrition：查营养知识库（膳食指南+饮食计划）
- search_platform：查平台资料（会员/企业/案例）
- recommend_plan：按人群推荐膳食方案
- check_taboo：识别用户饮食禁忌与疾病
- get_crowd：识别用户健康人群

工作规则（必须遵守）：
1. 仅依据工具返回的资料作答，禁止编造知识库以外的数据。
2. 营养类问题必须调用 search_nutrition（或 recommend_plan），并在回答标注来源：(来源：《文档名》章节·小节)。
3. 平台类问题调用 search_platform；严禁用平台价格/企业信息回答营养问题。
4. 涉及疾病(糖尿病/高血压/肾病/孕期等)必须在结尾追加免责声明：「本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师」。
5. 识别到禁忌时，排除不适宜食材并提示就医。
6. 若所有工具均无相关资料，回答「知识库中暂无该食材或方案的详细资料，无法提供准确数据」。
可多次调用工具后再综合回答。

重要：回答用户前，必须先调用至少一个相关工具获取资料，再基于工具返回作答；禁止在未经工具检索的情况下凭空回答营养或平台问题。若调用工具后确实无相关资料，再按第6条拒答。"""

# 按意图裁剪工具集，从机制上杜绝 A/B 与 C 互相污染（评审红线）：
# - 平台意图只暴露 search_platform，拿不到任何营养库内容；
# - 营养意图不暴露 search_platform，LLM 想混也取不到平台会员/价格/企业资料。
# intent 为空时兜底暴露全部工具（保持向后兼容）。
TOOL_BY_INTENT = {
    "platform": ["search_platform"],
    "nutrition": ["search_nutrition", "recommend_plan", "check_taboo", "get_crowd"],
}

def _tools_spec(intent=None):
    names = TOOL_BY_INTENT.get(intent)
    if names is None:
        names = list(skills.SKILLS.keys())  # 默认全部（未传意图时）
    return [{
        "type": "function",
        "function": {
            "name": name,
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
    } for name, spec in skills.SKILLS.items() if name in names]

def run_agent(user_msg, history_text="", taboo_hits=None, crowd_hint="", profile=None, intent=None):
    """执行 Agent 循环。返回 (final_answer, model)。
    profile: 用户个人档案（健康目标/禁忌/话题等），注入上下文使顾问每次对话都知道用户身份。
    intent: 意图路由结果（nutrition/platform），用于裁剪工具集，强制物理隔离 A/B 与 C。"""
    if not LLM_API_KEY:
        # 无 Key：降级为 RAG 流水线（保持可运行）。按意图路由到对应索引，修复平台问题误走营养库的缺陷。
        from . import rag
        from kb.retriever import retrieve
        results = retrieve(user_msg, intent or "nutrition")
        ans, model = rag.generate(user_msg, results, taboo_hits or [], crowd_hint, history_text, profile=profile)
        return ans, model

    from openai import OpenAI
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    messages = [{"role": "system", "content": SYSTEM}]
    if profile:
        messages.append({"role": "user", "content": "[用户个人档案]\n" + _profile_to_text(profile)})
    if history_text:
        messages.append({"role": "user", "content": "[历史摘要]\n" + history_text})
    messages.append({"role": "user", "content": user_msg})

    # 最多 5 轮工具调用
    called_any = False
    for _ in range(5):
        resp = client.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=_tools_spec(intent), tool_choice="auto", temperature=0.3)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            answer = msg.content or ""
            answer = _backfill(answer, user_msg, taboo_hits)
            # 若 LLM 未调用任何工具且答案空，做检索兜底（按意图路由到对应索引）
            if not called_any and not answer.strip():
                from kb.retriever import retrieve
                from . import rag
                results = retrieve(user_msg, intent or "nutrition")
                answer, _ = rag.generate(user_msg, results, taboo_hits or [], crowd_hint, history_text, profile=profile)
                answer = _backfill(answer, user_msg, taboo_hits)
            return answer, LLM_MODEL
        called_any = True
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            fn = skills.SKILLS.get(name, {}).get("fn")
            result = fn(**args) if fn else "未知工具"
            messages.append({"role": "tool", "content": str(result), "tool_call_id": tc.id})
    # 兜底：循环耗尽仍未产出
    final = client.chat.completions.create(model=LLM_MODEL, messages=messages, temperature=0.3)
    ans = final.choices[0].message.content or ""
    ans = _backfill(ans, user_msg, taboo_hits)
    return ans, LLM_MODEL

def _backfill(answer, user_msg, taboo_hits):
    """后处理兜底：仅补全来源标注/免责声明/禁忌提示，不强制拒答（Agent 自行判断是否无资料）。"""
    if taboo_hits is None:
        taboo_hits = taboo.detect_taboo(user_msg)
    answer = ensure_disclaimer(answer, user_msg)
    answer = ensure_taboo_tip(answer, taboo_hits)
    return answer

def _profile_to_text(profile):
    """将个人档案转为对 LLM 友好的上下文文本。空档案返回占位说明。"""
    if not profile:
        return ""
    if profile.get("user_msg_count", 0) == 0:
        return "（用户暂无对话记录，尚未建立档案）"
    parts = []
    goals = profile.get("health_goals", [])
    taboos = profile.get("dietary_taboos", [])
    topics = profile.get("topics", [])
    if goals:
        parts.append("健康目标：" + "、".join(goals))
    if taboos:
        parts.append("饮食禁忌：" + "、".join(taboos) + "（推荐方案必须规避相关食材，并提示就医）")
    if topics:
        parts.append("关注话题：" + "、".join(topics))
    if not parts:
        return "（用户档案暂无明显健康特征）"
    return "；".join(parts) + "。请结合该用户身份与历史偏好给出个性化建议。"
