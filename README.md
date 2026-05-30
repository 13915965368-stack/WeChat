# agent-mvp

`agent-mvp` 是一个前后端分离的多 Agent 聊天原型项目。

- 前端：React + TypeScript + Vite
- 后端：FastAPI + SQLite
- 当前主运行方式：前端走 Vite 开发服务器，后端提供真实 API

这个根目录 `README.md` 用来解决“刚从 GitHub 拉下来，不知道要装什么依赖、配什么环境、怎么启动”的问题。  
如果你已经在子目录里看过文档，也可以直接把这里当成总入口。

## 项目结构

```text
agent-mvp/
  backend/   FastAPI 后端
  frontend/  React + Vite 前端
```

补充文档：

- 后端说明：`backend/README.md`
- 前端说明：`frontend/README.md`

## 运行前准备

### 1. 需要的软件

建议先安装下面这些基础环境：

- Python `3.12` 或更高版本
- Node.js `18+`
- npm `9+`
- Git

可选但推荐：

- 一个支持创建虚拟环境的 Python 环境管理方式
- PowerShell、Windows Terminal 或其他可用命令行工具

### 2. 依赖安装范围

这个仓库没有把第三方依赖直接提交到 GitHub，所以拉下来后需要你本地自己安装：

- 后端 Python 依赖：从 `backend/pyproject.toml` 安装
- 前端 Node 依赖：从 `frontend/package.json` 安装

## 安装依赖

### 后端依赖

进入后端目录后执行：

```bash
cd e:\wegent\agent-mvp\backend
python -m pip install -e .
```

后端当前主要依赖包括：

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`
- `pydantic-settings`
- `httpx`
- `cryptography`
- `duckduckgo-search`
- `python-multipart`
- `pytest`

### 前端依赖

进入前端目录后执行：

```bash
cd e:\wegent\agent-mvp\frontend
npm install
```

前端当前主要依赖包括：

- `react`
- `react-dom`
- `react-markdown`
- `remark-gfm`
- `remark-breaks`
- `rehype-sanitize`
- `vite`
- `vitest`
- `typescript`
- `tailwindcss`

## 环境变量配置

### 后端环境变量

后端已提供示例文件：`backend/.env.example`

建议你复制一份为 `backend/.env`：

```bash
cd e:\wegent\agent-mvp\backend
copy .env.example .env
```

如果你使用的是 macOS / Linux：

```bash
cd /path/to/agent-mvp/backend
cp .env.example .env
```

### 最少需要关注的配置项

`backend/.env` 中当前关键字段如下：

```env
APP_ENV=dev
DATABASE_URL=sqlite:///agent_mvp.db
LLM_PROVIDER=mock
LLM_MODEL=mock-model
LLM_API_KEY=
MODEL_CONFIG_ENCRYPTION_KEY=
WEB_SEARCH_ENABLED=true
SEARCH_PRIMARY_PROVIDER=searxng
SEARCH_FALLBACK_ENABLED=true
SEARCH_FALLBACK_PROVIDERS=duckduckgo,tavily
SEARXNG_BASE_URL=
BOCHA_API_KEY=
BOCHA_BASE_URL=
TAVILY_API_KEY=
TAVILY_BASE_URL=
```

### 各字段的作用

- `APP_ENV`：运行环境，开发环境通常保持 `dev`
- `DATABASE_URL`：数据库地址，默认就是本地 SQLite
- `LLM_PROVIDER`：默认 LLM 提供方，开发期可先用 `mock`
- `LLM_MODEL`：默认模型名
- `LLM_API_KEY`：调用模型时使用的 API Key
- `MODEL_CONFIG_ENCRYPTION_KEY`：数据库里模型密钥的加密主密钥
- `WEB_SEARCH_ENABLED`：是否启用 Web Search
- `SEARCH_PRIMARY_PROVIDER`：主搜索服务
- `SEARCH_FALLBACK_PROVIDERS`：主搜索失败时的回退服务列表
- `SEARXNG_BASE_URL` / `BOCHA_API_KEY` / `TAVILY_API_KEY`：搜索相关外部服务配置

### 首次本地启动的推荐配置

如果你只是先把项目跑起来，本地开发建议这样：

- 保持 `DATABASE_URL=sqlite:///agent_mvp.db`
- 保持 `LLM_PROVIDER=mock`
- 保持 `LLM_MODEL=mock-model`
- 如果暂时不用真实模型，可以先不填 `LLM_API_KEY`
- 如果暂时不用联网搜索，可以保留默认值，或者后面再补搜索服务配置

### 加密主密钥

`MODEL_CONFIG_ENCRYPTION_KEY` 建议配置成有效的 Fernet key。

可以用下面命令生成：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把输出结果填回 `.env`：

```env
MODEL_CONFIG_ENCRYPTION_KEY=这里替换成你生成的key
```

## 启动方式

建议先启动后端，再启动前端。

### 1. 启动后端

```bash
cd e:\wegent\agent-mvp\backend
python -m pip install -e .
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

启动成功后可访问：

- 健康检查：[http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 2. 启动前端

```bash
cd e:\wegent\agent-mvp\frontend
npm install
npm run dev
```

启动成功后访问：

- 前端页面：[http://127.0.0.1:5173](http://127.0.0.1:5173)

## 前后端联调方式

前端当前默认通过 Vite 代理访问后端：

- 前端地址：`http://127.0.0.1:5173`
- 后端地址：`http://127.0.0.1:8000`
- 前端 API 基础路径：`/api/v1`

Vite 代理配置在：

- `frontend/vite.config.ts`

当前代理规则是：

- `/api` -> `http://127.0.0.1:8000`

这意味着：

- 前端本地开发通常不需要单独再配 API 地址环境变量
- 如果后端没启动，前端会出现无法连接后端的问题
- 如果你把前端端口改掉，可能还要同步检查后端 CORS 配置

## 常用命令

### 后端

```bash
cd e:\wegent\agent-mvp\backend
pytest tests -v
```

### 前端

```bash
cd e:\wegent\agent-mvp\frontend
npm run test
npm run build
npm run lint
```

## 常见问题

### 1. 为什么刚拉下来项目不能直接运行？

因为 GitHub 上提交的是源码，不包含第三方依赖，也不会提交本地环境文件、数据库文件、`node_modules`、Python 虚拟环境等内容，所以需要你在本地自己安装依赖并配置 `.env`。

### 2. 前端打开后提示连不上后端怎么办？

优先检查：

- 后端是否已经启动在 `127.0.0.1:8000`
- 前端是否运行在 `127.0.0.1:5173`
- `frontend/vite.config.ts` 里的代理是否仍然指向 `8000`

### 3. 不填真实模型 API Key 可以先运行吗？

可以。

如果你先用默认 `mock` 配置，本地项目仍然可以启动；只是涉及真实模型调用时，需要再补充 `LLM_API_KEY` 和相关模型配置。

### 4. 数据库存在哪里？

默认使用本地 SQLite：

- `backend/agent_mvp.db` 或由 `DATABASE_URL` 指向的位置

### 5. 需要提交 `.env` 吗？

不需要。

仓库已经忽略了 `.env` 文件，你只需要保留 `.env.example` 作为模板，在本地创建自己的 `.env` 即可。

## 推荐使用顺序

第一次拉下项目时，建议按这个顺序操作：

1. 安装 Python 和 Node.js
2. 安装后端依赖：`python -m pip install -e .`
3. 安装前端依赖：`npm install`
4. 复制 `backend/.env.example` 为 `backend/.env`
5. 生成并填写 `MODEL_CONFIG_ENCRYPTION_KEY`
6. 启动后端
7. 启动前端
8. 打开前端页面并检查 `health` 接口是否正常

## 相关文档

- [backend/README.md](file:///e:/wegent/agent-mvp/backend/README.md)
- [frontend/README.md](file:///e:/wegent/agent-mvp/frontend/README.md)

如果你后面还需要，我也可以继续帮你把这个 README 再补成更适合 GitHub 首页展示的版本，比如加上：

- 功能截图
- 快速开始目录
- API 概览
- 部署说明
