# ============ 阶段一：前端构建（Node） ============
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund || npm install
COPY frontend/ ./
# 产出 /fe/dist（VITE_API_BASE 留空 → 前端走同源 /api）
RUN npm run build

# ============ 阶段二：后端运行（Python + FastAPI） ============
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
# 构建知识库双索引（若索引文件缺失）
RUN python kb/build_kb.py || true
# 前端构建产物放到后端静态挂载路径 /frontend/dist（app.py 据此提供 UI）
COPY --from=frontend /fe/dist /frontend/dist
EXPOSE 8000
CMD ["python", "app.py"]
