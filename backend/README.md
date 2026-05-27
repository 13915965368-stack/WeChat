# agent-mvp backend

最小 FastAPI + SQLite 后端，用于支撑 `Agent / Conversation / Message` 的真实读写与本地联调。

## 启动

```bash
cd e:\wegent\agent-mvp\backend
python -m pip install -e .
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

启动后可先访问：

- `GET http://127.0.0.1:8000/api/v1/health`

## API Key 加密存储

- 数据库托管的模型 API Key 会在后端使用 `MODEL_CONFIG_ENCRYPTION_KEY` 加密后再写入 SQLite。
- 该主密钥只用于数据库密文加解密，不等于供应商的 `LLM_API_KEY`。
- `MODEL_CONFIG_ENCRYPTION_KEY` 必须配置为有效的 Fernet key，例如：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- 兼容接口 `/api/v1/settings/llm` 仍然保留，但其保存到数据库的 key 也会进入同一套加密托管流程。

## 测试

```bash
cd e:\wegent\agent-mvp\backend
pytest tests -v
```

## 前端联调与 CORS

- 当前前端默认通过 Vite 开发服务器 `http://127.0.0.1:5173` 启动
- 后端已内置 CORS 白名单，允许 `http://localhost:5173` 与 `http://127.0.0.1:5173`
- 推荐保持前端走 Vite 代理访问 `/api/v1/*`，不要再把前端视为默认 `mock` 主模式
- 如果把前端换到其他端口或域名，需要同步修改 `app/main.py` 中的 `allow_origins`

## 最小接口

- `GET /api/v1/health`
- `GET /api/v1/agents`
- `PUT /api/v1/agents/{agentId}`
- `PATCH /api/v1/agents/{agentId}/pin`
- `GET /api/v1/conversations`
- `PATCH /api/v1/conversations/{conversationId}/pin`
- `DELETE /api/v1/conversations/{conversationId}`
- `POST /api/v1/conversations/bulk-delete`
- `GET /api/v1/messages?conversationId=...`
- `POST /api/v1/conversations/direct`
- `POST /api/v1/conversations/group`
- `POST /api/v1/messages`
- `PATCH /api/v1/agents/{agentId}/model`
- `GET /api/v1/model-configs`
- `POST /api/v1/model-configs`
- `PATCH /api/v1/model-configs/{id}`
- `DELETE /api/v1/model-configs/{id}`
- `POST /api/v1/model-configs/{id}/validate`
- `POST /api/v1/attachments/images`
- `GET /api/v1/settings/llm`
- `PUT /api/v1/settings/llm`

## 会话删除说明

- 删除单个会话或批量删除会话时，会同时删除关联的 `conversation_members` 与 `messages`
- 会话与 Agent 的置顶状态都会持久化到数据库，服务重启后仍然保留
