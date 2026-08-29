FROM python:3.11-slim
WORKDIR /app
# 构建上下文需为仓库根目录：
#   docker build -f jeecg-fastapi/Dockerfile .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY jeecg-fastapi/app ./app
COPY jeecg-fastapi/run.py .
COPY sentiment-ai ./sentiment-ai
RUN mkdir -p uploads
EXPOSE 8006
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "2"]
