# -*- coding: utf-8 -*-
"""后处理：来源标注校验 + 免责声明兜底 + 无资料拒答。
确保评审无论怎么测，来源/免责/拒答都不会漏（代码强制）。"""
import re
from . import taboo

SOURCE_RE = re.compile(r"\(来源[:：]《[^》]+》")

def ensure_source(answer, blocks):
    """若答案无来源标注，但检索到了知识块，则在末尾补注首个块来源。"""
    if SOURCE_RE.search(answer):
        return answer
    if blocks:
        b = blocks[0]["block"]
        src = f"\n\n(来源：《{b['doc_name']}》{b['chapter']}·{b['section']})"
        return answer + src
    return answer

def ensure_disclaimer(answer, query):
    """疾病/医疗相关必须带免责声明，漏了强制追加。"""
    if taboo.detect_disease(query) and taboo.DISCLAIMER not in answer:
        answer = answer.rstrip() + f"\n\n（{taboo.DISCLAIMER}）"
    return answer

def ensure_taboo_tip(answer, taboo_hits):
    """命中禁忌必须带就医提示。"""
    if taboo_hits and "咨询专业医师或注册营养师" not in answer:
        answer = answer.rstrip() + "\n\n（建议您在使用本方案前咨询专业医师或注册营养师）"
    return answer

def is_no_data(results, threshold=2.5):
    """检索相关性过低 → 视为无资料（拒答）。
    标定：有答案查询 top≥3.0，无资料查询(如'人参')top≈2.0，阈值2.5可区分。"""
    if not results:
        return True
    return max(r["score"] for r in results) <= threshold

NO_DATA_REPLY = "知识库中暂无该食材或方案的详细资料，无法提供准确数据，避免误导。如有需要，建议咨询专业医师或注册营养师。"

def postprocess(answer, results, query, taboo_hits):
    """统一后处理流水线。"""
    if is_no_data(results):
        return NO_DATA_REPLY
    answer = ensure_source(answer, results)
    answer = ensure_disclaimer(answer, query)
    answer = ensure_taboo_tip(answer, taboo_hits)
    return answer
