# -*- coding: utf-8 -*-
"""检索服务：加载双索引(BM25)，按意图路由返回 Top-K 知识块。
两个检索器为独立实例，代码层不可互访，物理隔离 A+B 与 C。"""
import os, re, json
from rank_bm25 import BM25Okapi

KB_DIR = os.path.dirname(os.path.abspath(__file__))

class Retriever:
    def __init__(self, index_file, top_k=6):
        path = os.path.join(KB_DIR, index_file)
        data = json.load(open(path, encoding="utf-8"))
        self.blocks = data["blocks"]
        self.bm25 = BM25Okapi(data["tokenized"])
        self.top_k = top_k

    def search(self, query, top_k=None):
        k = top_k or self.top_k
        text = re.sub(r"\s+", "", query)
        toks = list(text) if len(text) <= 1 else [text[i:i+2] for i in range(len(text)-1)]
        scores = self.bm25.get_scores(toks)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked:
            if scores[i] <= 0:
                break
            results.append({"score": float(scores[i]), "block": self.blocks[i]})
            if len(results) >= k:
                break
        return results

# 物理双索引：两个独立 Retriever 实例
retriever_nutrition = Retriever("index_nutrition.json")   # A + B
retriever_platform = Retriever("index_platform.json")    # C

def retrieve(query, intent):
    """按意图路由到对应索引，杜绝跨库混淆。"""
    if intent == "platform":
        return retriever_platform.search(query)
    return retriever_nutrition.search(query)
