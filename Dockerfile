FROM python:3.11-slim

WORKDIR /app

# 先裝依賴（利用 Docker 層快取）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案
COPY . .

# 持久化目錄
VOLUME ["/app/logs", "/app/data"]

EXPOSE 5000

# 生產用 gunicorn（2 workers）
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "webapp.app:app"]
