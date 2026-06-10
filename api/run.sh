#!/bin/bash

# 启用 uvicorn 运行服务（使用 exec 让 uvicorn 成为主进程）
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 5