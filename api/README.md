# MiniManus API

MiniManus 后端 API 服务，基于 FastAPI、SQLAlchemy、PostgreSQL、Redis 和 Alembic 开发。

## 环境准备

本项目使用 Python 3.12 和 uv 管理依赖。

在新电脑上开发时，先克隆项目，然后进入 `api` 目录安装依赖：

```powershell
git clone <repo-url>
cd MiniManus\api
uv sync
```

本地开发依赖 PostgreSQL 和 Redis。回到项目根目录启动开发依赖：

```powershell
cd ..
docker compose -f docker/compose.dev.yml up -d
```

开发环境 Docker 默认端口：

```text
PostgreSQL: localhost:15432
Redis:      localhost:16379
```

## 配置环境变量

API 配置集中在 `core/config.py` 中，目前代码默认读取 `api/.env.dev`：

```python
env_file=".env.dev"
```

第一次开发时，在 `api` 目录下复制示例配置：

```powershell
Copy-Item .env.example .env.dev
```

当前开发环境数据库配置：

```env
SQLALCHEMY_DATABASE_URI=postgresql+asyncpg://minimanus:123456@localhost:15432/minimanus
REDIS_HOST=localhost
REDIS_PORT=16379
```

说明：

- `.env.dev` 是本地开发配置，不提交 Git。
- `.env.example` 是开发配置模板，需要提交 Git。
- `ENV=development` 当前主要用于控制 SQLAlchemy 是否打印 SQL 日志。
- 生产环境配置目前还没有单独文件，后续应通过服务器环境变量、容器环境变量或部署平台配置注入。
- 不要把生产数据库密码、COS 密钥等真实敏感配置提交到 Git。

## 启动服务

确认 PostgreSQL、Redis 已启动，并且 `.env.dev` 已配置后，在 `api` 目录启动 API：

```powershell
.\dev.ps1
```

也可以直接使用 uvicorn：

```powershell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问接口文档：

```text
http://localhost:8000/docs
```

## 数据库迁移与回滚

本项目使用 Alembic 管理数据库结构变更。

应用运行时使用异步驱动：

```text
postgresql+asyncpg://...
```

Alembic 迁移使用同步驱动：

```text
postgresql+psycopg2://...
```

两者连接的是同一个 PostgreSQL 数据库。

### 执行迁移

在 `api` 目录下执行：

```powershell
alembic upgrade head
```

这会把当前数据库升级到最新迁移版本。

### 生成迁移

当 SQLAlchemy 模型发生变化后，生成新的迁移文件：

```powershell
alembic revision --autogenerate -m "描述本次变更"
```

生成后先检查 `alembic/versions/` 下的迁移文件，确认无误后再执行：

```powershell
alembic upgrade head
```

迁移文件需要提交 Git。

### 回滚迁移

回滚上一个迁移版本：

```powershell
alembic downgrade -1
```

回滚到指定版本：

```powershell
alembic downgrade <revision_id>
```

查看当前数据库版本：

```powershell
alembic current
```

查看迁移历史：

```powershell
alembic history
```

注意：

- 新电脑拉取代码后，一般只需要执行 `alembic upgrade head`。
- 不要在没有模型变更时随意生成迁移文件。
- 生产环境执行迁移前，应先确认连接的是生产数据库，并做好备份。
