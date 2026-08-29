import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=True)

if __name__ == "__main__":
    reload = os.getenv("DEV_RELOAD", "false").lower() in ("1", "true", "yes")
    # Keep the local development server off the LAN unless explicitly requested.
    bind_host = os.getenv("BIND_HOST", "127.0.0.1")
    # Windows + 远程 MySQL：reload=True 会频繁重启子进程，远端易重置连接(WinError 10054)
    uvicorn.run("app.main:app", host=bind_host, port=8006, reload=reload)
