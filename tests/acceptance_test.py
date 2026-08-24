# -*- coding: utf-8 -*-
"""基础需求 + 进阶需求 逐条验收测试（对应整体方案第十三章）。
运行：py tests/acceptance_test.py
依赖：后端已启动于 http://localhost:8000（或改 BASE）
鉴权：先注册/登录获取 JWT，后续请求统一带 Authorization 头。"""
import sys, io, json, urllib.request, urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://localhost:8000"
UID = "test_accept"
PW = "accept123"

def req(path, payload=None, token=None, method="POST"):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    kwargs = {"headers": headers}
    if payload is not None:
        kwargs["data"] = json.dumps(payload).encode()
    r = urllib.request.Request(BASE + path, **kwargs)
    try:
        return json.loads(urllib.request.urlopen(r, timeout=30).read())
    except urllib.error.HTTPError as e:
        return {"_err": e.code, "detail": e.read().decode()}

# 注册并登录（鉴权）
reg = req("/api/auth/register", {"username": UID, "password": PW, "nickname": "验收账号"})
if not reg.get("ok"):
    # 已存在则直接登录
    reg = req("/api/auth/login", {"username": UID, "password": PW})
TOKEN = reg["token"]

def post(path, payload):
    return req(path, payload, token=TOKEN)

def get(path):
    return req(path, None, token=TOKEN, method="GET")

results = []
def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ---- 基础需求1：双库隔离 + 溯源 + 拒答 ----
r = post("/api/chat", {"message": "标准版会员一个月多少钱"})
check("基础1-平台库隔离(走C库)", len(r.get("sources", [])) > 0 and all("健康优选平台服务白皮书" == s["doc"] for s in r["sources"]), r.get("sources"))
r2 = post("/api/chat", {"message": "人参有什么营养"})
check("基础1-编造拒答(无资料)", "暂无" in r2["reply"], r2["reply"][:30])
r3 = post("/api/chat", {"message": "鸡胸肉的蛋白质含量"})
check("基础1-引用溯源(含来源标注)", "来源" in r3["reply"], r3["reply"][:40])
# 红线-营养问题绝不引C库：营养意图下 sources 不得出现白皮书（工具级裁剪保证）
r_n = post("/api/chat", {"message": "减脂期晚餐吃什么"})
check("红线-营养问题不引C库(白皮书)", all(s["doc"] != "健康优选平台服务白皮书" for s in r_n.get("sources", [])), r_n.get("sources"))

# ---- 基础需求2：多轮记忆 ----
r4 = post("/api/chat", {"message": "我有糖尿病"})
r5 = post("/api/chat", {"conv_id": r4["conv_id"], "message": "那我主食能吃什么"})
check("基础2-多轮上下文(控糖延续)", "低GI" in r5["reply"] or "控糖" in r5["reply"] or "GI" in r5["reply"], r5["reply"][:40])
sess = get("/api/sessions")
check("基础2-会话管理(历史列表)", len(sess.get("sessions", [])) >= 1, str(len(sess.get("sessions", []))))

# ---- 基础需求3：推荐 + 禁忌 ----
r6 = post("/api/suggest", {"crowd": "减脂塑形"})
check("基础3-方案推荐(减脂)", "减脂" in r6["reply"], r6["reply"][:30])
r7 = post("/api/chat", {"message": "我有糖尿病，推荐个方案"})
check("基础3-禁忌识别(就医提示)", "专业医师或注册营养师" in r7["reply"], r7["reply"][:40])

# ---- 基础需求4：三句错误提示 ----
check("基础4-空输入提示", post("/api/chat", {"message": "   "})["reply"] == "请输入您的问题")
check("基础4-超长输入提示", "过长" in post("/api/chat", {"message": "x"*600})["reply"])

# ---- 无关/功能询问：不误判为拒答 ----
r_irr = post("/api/chat", {"message": "你能做什么"})
check("边界-无关询问返回功能介绍(非拒答)", "膳食顾问" in r_irr["reply"] and "暂无" not in r_irr["reply"], r_irr["reply"][:30])

# ---- 进阶3：历史持久化 ----
hist = get(f"/api/history?conv_id={r4['conv_id']}")
check("进阶3-历史持久化(消息留存)", len(hist.get("messages", [])) >= 2, str(len(hist.get("messages", []))))

# ---- 进阶2：模型来源标注 ----
check("进阶2-模型来源标注", bool(r3.get("model")), r3.get("model",""))

# ---- 鉴权：未登录应被拒绝 ----
no_auth = req("/api/sessions")
check("鉴权-未带token拒绝(401)", no_auth.get("_err") == 401, str(no_auth.get("_err")))

print("\n==== 验收结果 ====")
passed = sum(1 for _, c, _ in results if c)
print(f"通过 {passed}/{len(results)}")
sys.exit(0 if passed == len(results) else 1)
