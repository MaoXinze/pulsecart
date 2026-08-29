# Sentiment-Plus 后端

JeecgBoot 精简版 FastAPI：仅系统配置 API（用户 / 角色 / 菜单 / 部门 / 字典 / 登录鉴权）。

```powershell
# 在仓库根目录安装依赖
cd ..
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
cd jeecg-fastapi
copy .env.example .env
..\.venv\Scripts\python scripts/init_slim_db.py
..\.venv\Scripts\python run.py
```

API：`http://localhost:8006/jeecg-boot`
默认账号：`admin` / `123456`
