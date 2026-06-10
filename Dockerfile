FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 暴露端口
EXPOSE 8000 8501

# 启动脚本
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
