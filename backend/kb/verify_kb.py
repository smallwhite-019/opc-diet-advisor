# -*- coding: utf-8 -*-
import json, re, sys
from rank_bm25 import BM25Okapi
sys.stdout.reconfigure(encoding="utf-8")

def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return BM25Okapi(d["tokenized"]), d["blocks"]

nu, nub = load("kb/index_nutrition.json")
pl, plb = load("kb/index_platform.json")

def q(idx, blocks, qs):
    text = re.sub(r"\s+", "", qs)
    toks = list(text) if len(text) <= 1 else [text[i:i+2] for i in range(len(text)-1)]
    sc = idx.get_scores(toks)
    top = sorted(range(len(sc)), key=lambda i: sc[i], reverse=True)[:3]
    return [(sc[i], blocks[i]) for i in top if sc[i] > 0]

print("营养库查[鸡胸肉热量]:")
for s, b in q(nu, nub, "鸡胸肉热量蛋白质"):
    print("  ", round(s,1), b["doc_name"], "/", b["chapter"], "/", b["section"], "->", b["text"][:40])
print("平台库查[标准版价格]:")
for s, b in q(pl, plb, "标准版价格会员"):
    print("  ", round(s,1), b["doc_name"], "/", b["chapter"], "->", b["text"][:40])
r = q(nu, nub, "标准版价格会员")
print("营养库查[标准版价格] ->", ("命中(隔离异常)" if r else "空(隔离OK)"), [b["doc_name"] for s,b in r])
