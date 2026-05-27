# agent-mvp frontend

当前前端基于 React + TypeScript + Vite，默认以真实后端 API 作为主运行模式，用于本地联调和功能验收。历史上的 `mock/localStorage` 方案仅作为测试夹具与前端独立开发阶段的背景，不再是默认启动路径。

## 启动方式

建议先启动后端，再启动前端。

### 1. 启动后端

```bash
cd e:\wegent\agent-mvp\backend
python -m pip install -e .
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

后端健康检查：

- `http://127.0.0.1:8000/api/v1/health`

### 2. 启动前端

```bash
cd e:\wegent\agent-mvp\frontend
npm install
npm run dev
```

前端开发地址：

- `http://127.0.0.1:5173`

## 联调说明

- 前端代码中的 API 基础路径固定为 `/api/v1`
- Vite 开发服务器会把 `/api/*` 代理到 `http://127.0.0.1:8000`
- 因此前端开发环境下不需要额外配置环境变量，也不应该再把页面理解为“默认跑本地 mock”
- 如果首页出现“无法连接后端服务”或初始化失败，优先检查后端是否已启动，以及 `5173 -> 8000` 的代理链路是否正常

## 当前主接口

当前前端主链路已经对齐真实后端，核心接口包括：

- `GET /api/v1/agents`
- `PUT /api/v1/agents/{agentId}`
- `PATCH /api/v1/agents/{agentId}/pin`
- `PATCH /api/v1/agents/{agentId}/model`
- `GET /api/v1/conversations`
- `POST /api/v1/conversations/direct`
- `POST /api/v1/conversations/group`
- `PATCH /api/v1/conversations/{conversationId}/pin`
- `DELETE /api/v1/conversations/{conversationId}`
- `POST /api/v1/conversations/bulk-delete`
- `GET /api/v1/messages`
- `POST /api/v1/messages`
- `GET/POST/PATCH/DELETE /api/v1/model-configs`
- `POST /api/v1/model-configs/{id}/validate`
- `POST /api/v1/attachments/images`

兼容接口说明：

- `/api/v1/settings/llm` 仍保留兼容能力，但模型管理主入口已经切换到 `/api/v1/model-configs`

## CORS 与访问来源

- 开发环境推荐通过 Vite 代理访问后端，也就是从 `http://127.0.0.1:5173` 打开前端页面
- 后端当前允许的前端来源为 `http://localhost:5173` 与 `http://127.0.0.1:5173`
- 若改用其他端口或域名启动前端，需要同步调整后端 CORS 配置

## 常用命令

```bash
cd e:\wegent\agent-mvp\frontend
npm run test
npm run build
npm run lint
```

## 当前已接通能力

- Agent 列表读取、编辑、置顶与模型绑定
- 单聊、群聊、空白对话创建与消息读写
- 模型配置新增、编辑、校验、删除
- 图片上传与附件消息发送
- 会话置顶、单条删除、批量删除
