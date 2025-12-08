import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.backend import run as run_backend
from app.frontend import run as run_frontend
import threading
import time

def main():
    """启动后端和前端服务"""
    print("启动简历筛选助手...")
    
    # 启动后端服务
    backend_thread = threading.Thread(target=run_backend)
    backend_thread.daemon = True
    backend_thread.start()
    
    # 等待后端启动
    time.sleep(2)
    
    # 启动前端服务
    run_frontend()

if __name__ == "__main__":
    main()