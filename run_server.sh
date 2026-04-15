#!/bin/bash
source venv/bin/activate
# 环境变量已在 .env 或 session 中设置，这里确保启动
export PYTHONUNBUFFERED=1
python3 main.py --port 8001
