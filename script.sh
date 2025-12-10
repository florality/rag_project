# #!/usr/bin/env bash
# set -e

# ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# cd "$ROOT_DIR"

# # 设置Python路径，确保可以导入app模块
# export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

# # 确保/tmp目录存在
# mkdir -p /tmp

# # Activate venv if exists
# if [ -d "venv" ]; then
#   source venv/bin/activate
# fi

# echo "[script] installing dependencies (if needed)..."
# pip3 install -r requirements.txt >/dev/null

# echo "[script] starting backend..."
# python3 -m app.backend >/tmp/resume_backend.log 2>&1 &
# BACK_PID=$!
# sleep 2
# if ps -p $BACK_PID >/dev/null; then
#   BACK_PORT=$(cat backend_port.txt 2>/dev/null || true)
#   if [ -z "$BACK_PORT" ]; then
#     BACK_PORT=$(grep -o "http://127.0.0.1:[0-9]*" /tmp/resume_backend.log | tail -n 1 | sed 's#http://127.0.0.1:##')
#   fi
#   BACK_PORT=${BACK_PORT:-unknown}
#   echo "[script] backend running on http://127.0.0.1:${BACK_PORT}"
# else
#   echo "[script] backend failed to start; see /tmp/resume_backend.log"
#   exit 1
# fi

# echo "[script] starting frontend..."
# python3 -m app.frontend >/tmp/resume_frontend.log 2>&1 &
# FRONT_PID=$!
# sleep 2
# if ps -p $FRONT_PID >/dev/null; then
#   # 首先尝试从文件中读取端口
#   FRONT_PORT=$(cat frontend_port.txt 2>/dev/null || true)
#   if [ -z "$FRONT_PORT" ]; then
#     # 如果文件不存在或为空，则尝试从日志中提取
#     FRONT_PORT=$(grep -o "\[前端\] 运行在 http://127.0.0.1:[0-9]*" /tmp/resume_frontend.log | tail -n 1 | sed 's/.*http:\/\/127.0.0.1://' || echo "")
#     if [ -z "$FRONT_PORT" ]; then
#       FRONT_PORT=$(grep -o "http://127.0.0.1:[0-9]*" /tmp/resume_frontend.log | tail -n 1 | sed 's#http://127.0.0.1:##' || echo "")
#     fi
#   fi
#   FRONT_PORT=${FRONT_PORT:-unknown}
#   echo "[script] frontend running on http://127.0.0.1:${FRONT_PORT}"
# else
#   echo "[script] frontend failed to start; see /tmp/resume_frontend.log"
#   exit 1
# fi

# echo "[script] tailing logs (Ctrl+C to stop)..."
# tail -f /tmp/resume_backend.log /tmp/resume_frontend.log


#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# 设置Python路径
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

# 激活虚拟环境
if [ -d "venv" ]; then
  source venv/bin/activate
fi

echo "[script] installing dependencies..."
pip3 install -r requirements.txt

# 使用 Render 提供的端口
PORT=${PORT:-8000}
echo "[script] using PORT: $PORT"

# 直接启动后端服务（绑定到 0.0.0.0）
echo "[script] starting backend on 0.0.0.0:$PORT..."
python3 -m app.backend --host 0.0.0.0 --port $PORT
