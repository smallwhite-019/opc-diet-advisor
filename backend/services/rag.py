# -*- coding: utf-8 -*-
"""RAG 生成：组装 Prompt → 调用真实 LLM（动态调用，进阶2）；
无 API Key 时降级为「检索直出」模板，保证可运行（基础底线）。"""
import os, re
from dotenv import load_dotenv
from . import taboo

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

def _format_blocks(results):
    out = []
    for r in results:
        b = r["block"]
        out.append(f"【{b['doc_name']}】{b['chapter']}·{b['section']}\n{b['text']}")
    return "\n\n".join(out)

SYSTEM_PROMPT = """你是「健康优选 AI 智能膳食顾问」，面向25-45岁都市白领，提供个性化膳食建议。
规则（必须严格遵守）：
1. 仅基于下方<知识块>作答，禁止编造知识库以外的数据或数值。
2. 营养类回答必须标注来源，格式：(来源：《文档名》章节·小节)。
3. 涉及疾病(糖尿病/高血压/肾病/孕期等)必须在结尾追加免责声明：「本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师」。
4. 命中用户饮食禁忌时，排除不适宜食材，并提示就医。
5. 若<知识块>无相关内容，回答「知识库中暂无该食材或方案的详细资料，无法提供准确数据」。
6. 严禁使用平台会员价格/企业合作信息回答营养问题。
语气专业、简洁、亲切。"""

def _call_llm(system, user, history_text=""):
    from openai import OpenAI
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    messages = [{"role": "system", "content": system}]
    if history_text:
        messages.append({"role": "user", "content": "[历史对话摘要]\n" + history_text})
    messages.append({"role": "user", "content": user})
    resp = client.chat.completions.create(model=LLM_MODEL, messages=messages, temperature=0.3)
    return resp.choices[0].message.content.strip()

def _fallback_generate(results, taboo_prompt, crowd_hint):
    """无 API Key 降级：直接基于检索块拼接结构化答案，仍带来源与免责。"""
    if not results:
        return None
    blocks = results[:3]
    parts = []
    if crowd_hint:
        parts.append(f"【人群识别】根据您的描述，您更符合「{crowd_hint}」人群需求。")
    for r in blocks:
        b = r["block"]
        snippet = b["text"][:240]
        parts.append(f"{snippet}\n(来源：《{b['doc_name']}》{b['chapter']}·{b['section']})")
    if taboo_prompt:
        parts.append(taboo_prompt)
    return "\n\n".join(parts)

def _profile_line(profile):
    """将个人档案转为提示行文本。"""
    if not profile or profile.get("user_msg_count", 0) == 0:
        return ""
    parts = []
    goals = profile.get("health_goals", [])
    taboos = profile.get("dietary_taboos", [])
    topics = profile.get("topics", [])
    if goals:
        parts.append("健康目标：" + "、".join(goals))
    if taboos:
        parts.append("饮食禁忌：" + "、".join(taboos))
    if topics:
        parts.append("关注话题：" + "、".join(topics))
    if not parts:
        return ""
    return "\n[用户个人档案] " + "；".join(parts) + "（请结合该用户身份与偏好作答）"

def generate(query, results, taboo_hits, crowd_hint="", history_text="", model_label="", profile=None):
    """主入口。有 Key 走 LLM，无 Key 走降级模板。返回 (answer, model_used)。
    profile: 用户个人档案，注入上下文使顾问知道用户身份。"""
    blocks_text = _format_blocks(results)
    taboo_prompt = taboo.build_taboo_prompt(taboo_hits)
    crowd_line = f"\n[识别人群] {crowd_hint}" if crowd_hint else ""
    profile_line = _profile_line(profile)

    if LLM_API_KEY:
        user_msg = f"""<知识块>
{blocks_text}
{taboo_prompt}{crowd_line}{profile_line}

用户问题：{query}"""
        try:
            ans = _call_llm(SYSTEM_PROMPT, user_msg, history_text)
            return ans, LLM_MODEL
        except Exception as e:
            # LLM 异常降级，避免前端崩溃
            fb = _fallback_generate(results, taboo_prompt, crowd_hint)
            return (fb or "服务繁忙，请稍后重试。"), "fallback(LLM异常)"
    else:
        fb = _fallback_generate(results, taboo_prompt, crowd_hint)
        return (fb or "知识库中暂无相关资料。"), "retrieval-template(未配置LLM Key)"
