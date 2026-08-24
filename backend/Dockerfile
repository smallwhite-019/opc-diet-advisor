FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# 构建知识库索引（若索引文件缺失）
RUN python kb/build_kb.py || true
EXPOSE 8000
CMD ["python", "app.py"]
