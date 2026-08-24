# -*- coding: utf-8 -*-
"""OPC 智能膳食顾问 - FastAPI 入口。
接口：/api/chat(对话) /api/suggest(快捷推荐) /api/sessions(会话管理) /api/history
"""
import os, re, json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kb.retriever import retrieve
from services import intent, taboo, rag
from services import agent
from services import profile as profile_svc
from services.postprocess import postprocess, is_no_data, NO_DATA_REPLY
from services import auth
import db

app = FastAPI(title="OPC 智能膳食顾问")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- 请求模型 ----------
class ChatReq(BaseModel):
    conv_id: str = ""
    message: str

class SuggestReq(BaseModel):
    crowd: str  # 减脂塑形 / 增肌强化 / 慢病调理 / 控压调理

class AuthReq(BaseModel):
    username: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str
    nickname: str = ''

# ---------- 工具 ----------
def build_history_text(conv_id):
    if not conv_id:
        return ""
    msgs = db.get_history(conv_id, limit=10)
    if len(msgs) <= 1:
        return ""
    # 仅取前序轮次做摘要式注入
    return "\n".join(f"{m['role']}: {m['content'][:80]}" for m in msgs[:-1])

# ---------- 接口 ----------
@app.post("/api/chat")
def chat(req: ChatReq, username: str = __import__('fastapi').Depends(auth.get_current_user)):
    msg = (req.message or "").strip()
    # 边界处理（基础4）：空输入 / 超长输入
    if not msg:
        return {"reply": "请输入您的问题", "sources": [], "model": "", "conv_id": req.conv_id}
    if len(msg) > 500:
        return {"reply": "输入内容过长，请精简后重试", "sources": [], "model": "", "conv_id": req.conv_id}

    db.ensure_user(username)
    if not req.conv_id:
        req.conv_id = db.new_conversation(username, title=msg[:20])

    intent_label = intent.classify(msg)
    taboo_hits = taboo.detect_taboo(msg)
    crowd = intent.detect_crowd(msg)
    crowd_hint = "/".join(crowd) if crowd else ""

    # 无关/闲聊/功能询问：返回功能介绍（边界处理，非硬编码营养答案）
    if intent_label == "irrelevant":
        reply = ("我是健康优选 AI 智能膳食顾问，可以帮您：\n"
                 "• 识别您的健康诉求（减脂塑形 / 增肌强化 / 慢病调理 / 控压）\n"
                 "• 推荐个性化膳食方案与食材组合（如「轻盈减脂方案」「力量增肌方案」「稳糖调理方案」）\n"
                 "• 解答营养问题：食材热量、蛋白质、GI 值、膳食搭配、饮食禁忌等\n"
                 "• 管理多轮对话与历史记录\n\n"
                 "您可以告诉我您的目标，例如「我想减脂」「我血糖偏高吃什么」，或直接提问「鸡胸肉热量多少」。")
        db.add_message(req.conv_id, "user", msg)
        db.add_message(req.conv_id, "assistant", reply)
        return {"reply": reply, "sources": [], "model": "system-capability", "conv_id": req.conv_id}

    # Agent 编排：LLM 自主调用 skills（检索/推荐/禁忌/画像），后处理兜底
    history_text = build_history_text(req.conv_id)
    # 注入用户个人档案，使顾问每次对话都知道用户身份（健康目标/禁忌/偏好）
    user_profile = profile_svc.build_profile(username)
    # intent 传给 Agent：按意图裁剪工具集，强制 A/B 与 C 物理隔离（评审红线）
    answer, model = agent.run_agent(msg, history_text, taboo_hits, crowd_hint, profile=user_profile, intent=intent_label)
    # 来源展示：用于前端标注（Agent 内部已带来源，这里补充结构化来源）
    results = retrieve(msg, intent_label)
    sources = [{"doc": r["block"]["doc_name"], "chapter": r["block"]["chapter"], "section": r["block"]["section"]} for r in results[:3]]
    # 硬拒答闸（代码强制，杜绝编造）：知识库无相关内容时，无论 LLM 输出什么一律拒绝，
    # 使「检索分<阈值→固定拒答」在 Agent 活体模式下也成立，不依赖 LLM 自觉。
    if is_no_data(results):
        answer, model = NO_DATA_REPLY, "no-data-refusal"

    db.add_message(req.conv_id, "user", msg)
    db.add_message(req.conv_id, "assistant", answer, json.dumps(sources, ensure_ascii=False))
    return {"reply": answer, "sources": sources, "model": model, "conv_id": req.conv_id}

@app.post("/api/suggest")
def suggest(req: SuggestReq, username: str = __import__('fastapi').Depends(auth.get_current_user)):
    db.ensure_user(username)
    # 快捷入口：构造人群提问，走营养库推荐
    query_map = {
        "减脂塑形": "我想减脂塑形，请推荐适合的膳食方案和食材",
        "增肌强化": "我在健身增肌，请推荐力量增肌方案和蛋白质食材",
        "慢病调理": "我血糖偏高需要调理，请推荐稳糖调理方案和饮食要点",
        "控压调理": "我有高血压，请推荐控压饮食方案和注意点",
    }
    msg = query_map.get(req.crowd, "请给我膳食建议")
    fake = ChatReq(message=msg)
    return chat(fake, username)

@app.get("/api/sessions")
def sessions(username: str = __import__('fastapi').Depends(auth.get_current_user)):
    db.ensure_user(username)
    return {"sessions": db.list_conversations(username)}

# ---------- 个人档案（规则提取，基于全部历史） ----------
@app.get("/api/profile")
def profile(username: str = __import__('fastapi').Depends(auth.get_current_user)):
    db.ensure_user(username)
    return {"profile": profile_svc.build_profile(username)}

# ---------- 账号后台（登录账号隔离） ----------
class NicknameReq(BaseModel):
    nickname: str

@app.get("/api/account")
def account(username: str = __import__('fastapi').Depends(auth.get_current_user)):
    db.ensure_user(username)
    return {"id": username, "nickname": db.get_account_nickname(username) or "", "created_at": (db.get_account(username) or {}).get("created_at", "")}

@app.post("/api/account/nickname")
def set_nickname(req: NicknameReq, username: str = __import__('fastapi').Depends(auth.get_current_user)):
    nick = (req.nickname or "").strip()[:20]
    db.update_account_nickname(username, nick)
    db.update_nickname(username, nick)
    return {"ok": True, "nickname": nick}

@app.post("/api/account/clear")
def clear_account(username: str = __import__('fastapi').Depends(auth.get_current_user)):
    db.ensure_user(username)
    n = db.clear_user_data(username)
    return {"ok": True, "deleted_conversations": n}

@app.get("/api/account/export")
def export_account(username: str = __import__('fastapi').Depends(auth.get_current_user)):
    db.ensure_user(username)
    return {"messages": db.export_user_messages(username)}

@app.get("/api/history")
def history(conv_id: str, username: str = __import__('fastapi').Depends(auth.get_current_user)):
    return {"messages": db.get_history(conv_id, limit=50)}

@app.delete("/api/sessions/{conv_id}")
def del_session(conv_id: str, username: str = __import__('fastapi').Depends(auth.get_current_user)):
    row = db.get_conn().execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conv_id, username)).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="会话不存在或无权限")
    db.delete_conversation(conv_id)
    return {"ok": True}

# ---------- 注册 / 登录 ----------
@app.post("/api/auth/register")
def api_register(req: RegisterReq):
    try:
        auth.register(req.username, req.password, req.nickname)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    token = auth.create_token(req.username)
    db.ensure_user(req.username, req.nickname)
    return {"ok": True, "token": token, "username": req.username, "nickname": req.nickname}

@app.post("/api/auth/login")
def api_login(req: AuthReq):
    try:
        acc = auth.login(req.username, req.password)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail=str(e))
    token = auth.create_token(acc["username"])
    return {"ok": True, "token": token, "username": acc["username"], "nickname": acc.get("nickname") or ""}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/greeting")
def greeting():
    """开场白：顾问主动问候，引导用户说明诉求，并附免责声明。"""
    text = ("您好！我是健康优选 AI 智能膳食顾问 👋\n"
            "我可以根据您的健康目标，为您推荐个性化的膳食方案与食材组合，"
            "并解答营养相关问题（如食材热量、膳食搭配、饮食禁忌等）。\n\n"
            "请告诉我您的诉求，例如：\n"
            "• 减脂塑形 / 增肌强化 / 血糖偏高(控糖) / 血压偏高(控压)\n"
            "• 或直接问「鸡胸肉热量多少」「减脂期晚餐吃什么」\n\n"
            "（本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师）")
    return {"reply": text, "sources": [], "model": "system-greeting"}

# ---------- 知识库可视化（进阶展示） ----------
@app.get("/api/kb")
def kb_view():
    """返回知识库目录树（文档→章节→小节→知识块），供前端可视化展示。
    数据来自双索引 JSON，仅取 blocks 元数据与文本，不含检索权重。"""
    import glob
    kb_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb")
    files = ["index_nutrition.json", "index_platform.json"]
    docs = {}
    total_blocks = 0
    for f in files:
        path = os.path.join(kb_dir, f)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for b in data.get("blocks", []):
            total_blocks += 1
            doc = docs.setdefault(b["doc_name"], {
                "doc": b["doc"], "doc_name": b["doc_name"],
                "chapter_count": 0, "block_count": 0, "chapters": {},
            })
            doc["block_count"] += 1
            ch = doc["chapters"].setdefault(b["chapter"], {
                "chapter": b["chapter"], "section_count": 0, "sections": {},
            })
            sec = ch["sections"].setdefault(b["section"] or "（正文）", {
                "section": b["section"] or "（正文）", "blocks": [],
            })
            sec["blocks"].append({"text": b["text"], "chars": len(b["text"])})
    # 转换为列表并排序
    result = []
    for doc in docs.values():
        doc["chapter_count"] = len(doc["chapters"])
        doc["chapters"] = [v for v in doc["chapters"].values()]
        for ch in doc["chapters"]:
            ch["section_count"] = len(ch["sections"])
            ch["sections"] = [v for v in ch["sections"].values()]
        result.append(doc)
    return {"total_blocks": total_blocks, "docs": result}

# 生产环境可托管前端构建产物（可选）
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
