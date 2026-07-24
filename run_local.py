"""启动本地实验服务器：python run_local.py，然后访问 http://127.0.0.1:8100/。"""

import os

import uvicorn

if __name__ == "__main__":
    # 本地入口强制开调试脚本注入（不依赖 Host；生产 run_local 不上主站）。
    os.environ.setdefault("LP_LOCAL_DEBUG", "1")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8100, reload=True)
