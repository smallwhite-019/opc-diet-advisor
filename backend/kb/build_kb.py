# -*- coding: utf-8 -*-
"""
知识库构建脚本：解析三份 PDF → 结构化知识块(带元数据) → 双索引(BM25) JSON
  - 营养库 idx_nutrition: 素材A(秋季膳食指南) + 素材B(个性化饮食计划)
  - 平台库 idx_platform:  素材C(平台服务白皮书)
双索引物理隔离，代码层不可互访，杜绝 A/B 与 C 混淆(赛题红线)。
"""
import os, re, json
import pdfplumber
from rank_bm25 import BM25Okapi

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)  # opc-diet-advisor 的上级 = OPCorder
SRC = os.path.join(ROOT, "..") if False else r"c:\Users\阳光\Desktop\OPCorder"
OUT_DIR = os.path.join(BASE, "kb")

PDF_MAP = {
    "A": {"file": "1.pdf", "name": "2026秋季健康膳食指南", "index": "nutrition"},
    "B": {"file": "2.pdf", "name": "个性化饮食计划方案", "index": "nutrition"},
    "C": {"file": "3.pdf", "name": "健康优选平台服务白皮书", "index": "platform"},
}

CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十]+章")
SECTION_RE = re.compile(r"^\d+\.\d+(\.\d+)?\s*.+")
HEAD_JUNK_RE = re.compile(r"Kimi 生成|健康优选|^\s*$")

def extract_text(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            pages.append(t)
    return pages

def segment(doc_label, doc_name, pages):
    """按章/节切分为知识块，每块带 doc/chapter/section 元数据。"""
    blocks = []
    cur_chapter = "未分类"
    cur_section = ""
    buf = []
    def flush():
        if buf:
            text = "\n".join(buf).strip()
            text = re.sub(r"Kimi 生成", "", text).strip()
            if text:
                blocks.append({
                    "doc": doc_label,
                    "doc_name": doc_name,
                    "chapter": cur_chapter,
                    "section": cur_section,
                    "text": text,
                })
    for pg in pages:
        for line in pg.split("\n"):
            line = line.strip()
            if not line or HEAD_JUNK_RE.match(line):
                continue
            if CHAPTER_RE.match(line):
                flush(); buf = []
                cur_chapter = line; cur_section = ""
                continue
            if SECTION_RE.match(line):
                flush(); buf = []
                cur_section = line
                buf.append(line)
                continue
            buf.append(line)
    flush()
    return blocks

def build_index(blocks, index_name):
    def tok(text):
        text = re.sub(r"\s+", "", text)
        # 字符 bigram：中文无空格，bigram 比单字召回更准
        if len(text) <= 1:
            return list(text)
        return [text[i:i+2] for i in range(len(text)-1)]
    tokenized = [tok(b["text"]) for b in blocks]
    bm25 = BM25Okapi(tokenized)
    payload = {
        "index_name": index_name,
        "blocks": blocks,
        "tokenized": tokenized,
    }
    return bm25, payload

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    nutrition_blocks, platform_blocks = [], []
    for label, meta in PDF_MAP.items():
        path = os.path.join(SRC, meta["file"])
        print(f"[build] 解析素材{meta['name']} ({meta['file']}) ...")
        pages = extract_text(path)
        blocks = segment(label, meta["name"], pages)
        print(f"        -> {len(blocks)} 个知识块")
        if meta["index"] == "nutrition":
            nutrition_blocks += blocks
        else:
            platform_blocks += blocks

    # 分别构建双索引，存为独立文件(物理隔离)
    nu_bm25, nu_payload = build_index(nutrition_blocks, "nutrition")
    pl_bm25, pl_payload = build_index(platform_blocks, "platform")

    # 持久化：保存 blocks 与 tokenized，运行时重建 BM25
    with open(os.path.join(OUT_DIR, "index_nutrition.json"), "w", encoding="utf-8") as f:
        json.dump(nu_payload, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_DIR, "index_platform.json"), "w", encoding="utf-8") as f:
        json.dump(pl_payload, f, ensure_ascii=False, indent=1)

    print(f"[build] 营养库 {len(nutrition_blocks)} 块 / 平台库 {len(platform_blocks)} 块")
    print(f"[build] 索引已写入 {OUT_DIR}")

if __name__ == "__main__":
    main()
