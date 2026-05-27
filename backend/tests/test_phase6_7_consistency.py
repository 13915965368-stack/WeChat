from __future__ import annotations

import httpx
import pytest

BASE = "http://127.0.0.1:8000/api/v1"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=15) as c:
        yield c


class TestErrorResponseHelper:
    def assert_error(self, response: httpx.Response, expected_status: int, expected_code: str):
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. "
            f"Body: {response.text}"
        )
        body = response.json()
        assert isinstance(body, dict), f"Response body is not a dict: {body}"
        assert "error" in body, f"Missing 'error' top-level key. Body: {body}"
        error_obj = body["error"]
        assert isinstance(error_obj, dict), f"'error' is not a dict: {error_obj}"
        assert "code" in error_obj, f"Missing 'code' in error. Error: {error_obj}"
        assert "message" in error_obj, f"Missing 'message' in error. Error: {error_obj}"
        assert error_obj["code"] == expected_code, (
            f"Expected error code '{expected_code}', got '{error_obj['code']}'"
        )
        assert isinstance(error_obj["message"], str), f"'message' is not a string"
        assert len(error_obj["message"]) > 0, "'message' is empty"


# ===================================================================
# Phase 6.1: 错误格式标准化
# ===================================================================

class TestPhase6_1_ErrorFormatStandardization(TestErrorResponseHelper):
    """验证所有错误响应统一为 {"error": {"code": "CODE", "message": "MSG"}}"""

    def test_6_1_1_put_agents_nonexistent_404(self, client):
        """PUT /agents/nonexistent → 404, agent_not_found"""
        r = client.put("/agents/nonexistent", json={
            "name": "X",
            "roleSummary": "X",
            "styleSummary": "X",
            "systemPrompt": "X",
            "avatar": "X",
        })
        self.assert_error(r, 404, "agent_not_found")

    def test_6_1_2_put_agents_architect_empty_name_422(self, client):
        """PUT /agents/architect with empty name → 422, validation_error, message含'name'"""
        r = client.put("/agents/architect", json={
            "name": "   ",
            "roleSummary": "valid",
            "styleSummary": "valid",
            "systemPrompt": "valid",
            "avatar": "valid",
        })
        self.assert_error(r, 422, "validation_error")
        assert "name" in r.json()["error"]["message"].lower(), (
            f"Message should contain 'name': {r.json()['error']['message']}"
        )

    def test_6_1_3_post_conversations_direct_empty_agentId_422(self, client):
        """POST /conversations/direct with empty agentId → 422, validation_error"""
        r = client.post("/conversations/direct", json={
            "agentId": "   ",
        })
        self.assert_error(r, 422, "validation_error")

    def test_6_1_4_post_conversations_group_one_member_422(self, client):
        """POST /conversations/group with only 1 member → 422, validation_error"""
        r = client.post("/conversations/group", json={
            "title": "Group",
            "memberIds": ["architect"],
        })
        self.assert_error(r, 422, "validation_error")

    def test_6_1_5_post_messages_empty_content_422(self, client):
        """POST /messages with empty content → 422, validation_error"""
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "   ",
        })
        self.assert_error(r, 422, "validation_error")

    def test_6_1_6_get_messages_empty_conversationId_422(self, client):
        """GET /messages with empty conversationId → 422, validation_error"""
        r = client.get("/messages", params={"conversationId": "   "})
        self.assert_error(r, 422, "validation_error")

    def test_6_1_7_post_messages_nonexistent_conversation_404(self, client):
        """POST /messages to nonexistent conversation → 404, conversation_not_found"""
        r = client.post("/messages", json={
            "conversationId": "nonexistent-conversation-xyz",
            "content": "hello",
        })
        self.assert_error(r, 404, "conversation_not_found")

    def test_6_1_8_put_settings_llm_empty_provider_422(self, client):
        """PUT /settings/llm with empty provider → 422, llm_provider_required"""
        r = client.put("/settings/llm", json={
            "provider": "   ",
            "model": "gpt-4",
            "apiKey": "key",
        })
        self.assert_error(r, 422, "llm_provider_required")

    def test_6_1_9_put_settings_llm_empty_model_422(self, client):
        """PUT /settings/llm with empty model → 422, llm_model_required"""
        r = client.put("/settings/llm", json={
            "provider": "openai",
            "model": "   ",
            "apiKey": "key",
        })
        self.assert_error(r, 422, "llm_model_required")


# ===================================================================
# Phase 6.2: response_model不污染错误响应
# ===================================================================

class TestPhase6_2_ResponseModelDoesNotCorruptErrors:
    """验证当route handler有response_model但返回JSONResponse时"""

    def test_6_2_1_error_keys_only_error(self, client):
        """错误体的顶层keys仅为 ['error']（不包含AgentResponse等模型字段）"""
        r = client.put("/agents/nonexistent", json={
            "name": "X",
            "roleSummary": "X",
            "styleSummary": "X",
            "systemPrompt": "X",
            "avatar": "X",
        })
        body = r.json()
        assert list(body.keys()) == ["error"], (
            f"Expected only 'error' key in error response, got: {list(body.keys())}. "
            f"response_model may have corrupted the JSONResponse."
        )

    def test_6_2_2_error_inner_keys_only_code_message(self, client):
        """错误body['error']的keys仅为 ['code', 'message']"""
        r = client.put("/agents/architect", json={
            "name": "   ",
            "roleSummary": "X",
            "styleSummary": "X",
            "systemPrompt": "X",
            "avatar": "X",
        })
        error_obj = r.json()["error"]
        assert sorted(error_obj.keys()) == ["code", "message"], (
            f"Expected 'code' and 'message' in error, got: {list(error_obj.keys())}"
        )

    def test_6_2_3_404_status_not_overridden_to_200(self, client):
        """404状态码不被response_model覆盖为200"""
        r = client.put("/agents/nonexistent", json={
            "name": "X",
            "roleSummary": "X",
            "styleSummary": "X",
            "systemPrompt": "X",
            "avatar": "X",
        })
        assert r.status_code == 404, (
            f"Expected 404, got {r.status_code}. response_model may have forced 200."
        )

    def test_6_2_4_422_status_not_overridden_to_200(self, client):
        """422状态码不被response_model覆盖为200"""
        r = client.put("/agents/architect", json={
            "name": "   ",
            "roleSummary": "X",
            "styleSummary": "X",
            "systemPrompt": "X",
            "avatar": "X",
        })
        assert r.status_code == 422, (
            f"Expected 422, got {r.status_code}. response_model may have forced 200."
        )

    def test_6_2_5_multiple_error_endpoints_keys_intact(self, client):
        """多个不同端点的错误响应keys都仅仅为['error']"""
        endpoints = [
            lambda: client.put("/agents/architect", json={
                "name": "   ", "roleSummary": "X", "styleSummary": "X",
                "systemPrompt": "X", "avatar": "X",
            }),
            lambda: client.post("/conversations/direct", json={"agentId": "   "}),
            lambda: client.post("/conversations/group", json={
                "title": "G", "memberIds": ["architect"],
            }),
            lambda: client.post("/messages", json={
                "conversationId": "direct-architect-default", "content": "   ",
            }),
            lambda: client.put("/settings/llm", json={
                "provider": "   ", "model": "gpt-4", "apiKey": "",
            }),
        ]
        for fn in endpoints:
            r = fn()
            body = r.json()
            assert list(body.keys()) == ["error"], (
                f"Unexpected keys in error response: {list(body.keys())}. Body: {body}"
            )

    def test_6_2_6_success_path_uses_camelcase(self, client):
        """成功路径仍使用camelCase别名"""
        r = client.get("/agents")
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list)
        assert len(agents) > 0
        agent = agents[0]
        assert "roleSummary" in agent, (
            f"Expected camelCase 'roleSummary', got keys: {list(agent.keys())}"
        )
        assert "role_summary" not in agent, (
            "Snake_case should not appear in success response with alias_generator."
        )
        assert "systemPrompt" in agent
        assert "system_prompt" not in agent
        assert "themeColor" in agent
        assert "theme_color" not in agent

    def test_6_2_7_conversation_success_uses_camelcase(self, client):
        """会话成功路径使用camelCase"""
        r = client.get("/conversations")
        assert r.status_code == 200
        convs = r.json()
        assert len(convs) > 0
        conv = convs[0]
        assert "memberIds" in conv
        assert "member_ids" not in conv
        assert "agentId" in conv
        assert "agent_id" not in conv
        assert "createdAt" in conv
        assert "created_at" not in conv

    def test_6_2_8_message_success_uses_camelcase(self, client):
        """消息成功路径使用camelCase"""
        r = client.get("/messages", params={"conversationId": "direct-architect-default"})
        assert r.status_code == 200
        body = r.json()
        assert "hasMore" in body
        assert "has_more" not in body
        if body["items"]:
            msg = body["items"][0]
            assert "senderType" in msg
            assert "sender_type" not in msg
            assert "conversationId" in msg
            assert "conversation_id" not in msg
            assert "createdAt" in msg
            assert "created_at" not in msg


# ===================================================================
# Phase 7.1: 消息发送后会话时间更新
# ===================================================================

class TestPhase7_1_ConversationTimeUpdate:
    """消息发送后会话 updatedAt 更新"""

    def test_7_1_1_updated_at_changes_after_send(self, client):
        """发送消息后会话 updatedAt 已更新"""
        convs_before = client.get("/conversations").json()
        direct_before = [c for c in convs_before if c["id"] == "direct-architect-default"][0]
        before_updated = direct_before["updatedAt"]

        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "更新会话时间测试消息",
        })
        assert r.status_code == 201
        send_updated_at = r.json()["conversationUpdatedAt"]

        convs_after = client.get("/conversations").json()
        direct_after = [c for c in convs_after if c["id"] == "direct-architect-default"][0]
        after_updated = direct_after["updatedAt"]

        assert after_updated != before_updated, (
            f"updatedAt should have changed after sending a message. "
            f"Before: {before_updated}, After: {after_updated}"
        )
        assert after_updated >= before_updated, (
            f"updatedAt should not go backwards. "
            f"Before: {before_updated}, After: {after_updated}"
        )
        assert send_updated_at == after_updated, (
            f"conversationUpdatedAt in send response must match GET updatedAt. "
            f"Send: {send_updated_at}, GET: {after_updated}"
        )

    def test_7_1_2_multiple_sends_increment_updated_at(self, client):
        """多次发送消息，updatedAt 单调递增"""
        r1 = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "第一次消息",
        })
        t1 = r1.json()["conversationUpdatedAt"]

        r2 = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "第二次消息",
        })
        t2 = r2.json()["conversationUpdatedAt"]

        assert t2 >= t1, (
            f"Second send updatedAt should be >= first. t1={t1}, t2={t2}"
        )

        convs_after = client.get("/conversations").json()
        direct_after = [c for c in convs_after if c["id"] == "direct-architect-default"][0]
        assert direct_after["updatedAt"] == t2, (
            f"GET updatedAt must match last send. "
            f"Expected: {t2}, Got: {direct_after['updatedAt']}"
        )


# ===================================================================
# Phase 7.2: 消息排序验证
# ===================================================================

class TestPhase7_2_MessageOrdering:
    """消息按 createdAt 升序排列"""

    def test_7_2_1_messages_ordered_by_created_at(self, client):
        """连续发送多条消息后，GET /messages 验证按 createdAt 升序排列"""
        client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "排序测试 A",
        })
        client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "排序测试 B",
        })
        client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "排序测试 C",
        })

        r = client.get("/messages", params={
            "conversationId": "direct-architect-default",
            "limit": 100,
        })
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 3, f"Expected at least 3 messages, got {len(items)}"

        for i in range(1, len(items)):
            assert items[i]["createdAt"] >= items[i - 1]["createdAt"], (
                f"Messages are not in ascending order at index {i}. "
                f"Prev: {items[i-1]['createdAt']}, Current: {items[i]['createdAt']}"
            )

    def test_7_2_2_pagination_respects_ordering(self, client):
        """分页查询也保持升序"""
        r = client.get("/messages", params={
            "conversationId": "direct-architect-default",
            "limit": 2,
            "offset": 0,
        })
        items = r.json()["items"]
        for i in range(1, len(items)):
            assert items[i]["createdAt"] >= items[i - 1]["createdAt"]

    def test_7_2_3_group_messages_ordered(self, client):
        """群聊消息也按时间升序"""
        client.post("/messages", json={
            "conversationId": "group-product-discussion-default",
            "content": "群聊排序测试",
        })
        r = client.get("/messages", params={
            "conversationId": "group-product-discussion-default",
            "limit": 100,
        })
        items = r.json()["items"]
        for i in range(1, len(items)):
            assert items[i]["createdAt"] >= items[i - 1]["createdAt"], (
                f"Group messages not ordered at index {i}"
            )


# ===================================================================
# Phase 7.3: 群聊回复顺序验证
# ===================================================================

class TestPhase7_3_GroupReplyOrder:
    """群聊 agentMessages 的 senderId 顺序与 memberIds 一致"""

    def test_7_3_1_reply_order_matches_member_ids(self, client):
        """创建群聊 memberIds=['critic', 'writer', 'architect']，验证回复顺序"""
        r = client.post("/conversations/group", json={
            "title": "群聊顺序测试",
            "memberIds": ["critic", "writer", "architect"],
        })
        assert r.status_code == 201
        conv_id = r.json()["id"]

        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": "请回复顺序测试",
        })
        assert msg_r.status_code == 201
        body = msg_r.json()
        sender_ids = [m["senderId"] for m in body["agentMessages"]]
        assert sender_ids == ["critic", "writer", "architect"], (
            f"agentMessages senderId order must match memberIds order. "
            f"Expected: ['critic', 'writer', 'architect'], Got: {sender_ids}"
        )

    def test_7_3_2_alternate_member_order(self, client):
        """不同的 memberIds 顺序产生不同的回复顺序"""
        r = client.post("/conversations/group", json={
            "title": "反向顺序测试",
            "memberIds": ["architect", "critic"],
        })
        assert r.status_code == 201
        conv_id = r.json()["id"]

        msg_r = client.post("/messages", json={
            "conversationId": conv_id,
            "content": "反向测试",
        })
        sender_ids = [m["senderId"] for m in msg_r.json()["agentMessages"]]
        assert sender_ids == ["architect", "critic"], (
            f"Expected: ['architect', 'critic'], Got: {sender_ids}"
        )

    def test_7_3_3_seeded_group_reply_order(self, client):
        """种子数据的群聊回复顺序与 memberIds ['architect', 'critic', 'writer'] 一致"""
        msg_r = client.post("/messages", json={
            "conversationId": "group-product-discussion-default",
            "content": "验证种子群聊顺序",
        })
        assert msg_r.status_code == 201
        sender_ids = [m["senderId"] for m in msg_r.json()["agentMessages"]]
        assert sender_ids == ["architect", "critic", "writer"], (
            f"Seeded group reply order must be ['architect', 'critic', 'writer']. Got: {sender_ids}"
        )


# ===================================================================
# Phase 7.4: conversationUpdatedAt一致性
# ===================================================================

class TestPhase7_4_ConversationUpdatedAtConsistency:
    """conversationUpdatedAt == agentMessages最后一条的createdAt"""

    def test_7_4_1_direct_conversation_updated_at_equals_last_agent_created_at(self, client):
        """发送消息后，conversationUpdatedAt == agentMessages最后一条的createdAt"""
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "一致性检查",
        })
        assert r.status_code == 201
        body = r.json()

        conversation_updated_at = body["conversationUpdatedAt"]
        agent_messages = body["agentMessages"]
        assert len(agent_messages) >= 1
        last_agent_created_at = agent_messages[-1]["createdAt"]

        assert conversation_updated_at == last_agent_created_at, (
            f"conversationUpdatedAt must equal last agentMessage createdAt. "
            f"conversationUpdatedAt: {conversation_updated_at}, "
            f"last agentMessage createdAt: {last_agent_created_at}"
        )

    def test_7_4_2_group_conversation_updated_at_equals_last_agent_created_at(self, client):
        """群聊 conversationUpdatedAt == agentMessages最后一条的createdAt"""
        r = client.post("/messages", json={
            "conversationId": "group-product-discussion-default",
            "content": "群聊一致性检查",
        })
        assert r.status_code == 201
        body = r.json()

        conversation_updated_at = body["conversationUpdatedAt"]
        agent_messages = body["agentMessages"]
        assert len(agent_messages) >= 1
        last_agent_created_at = agent_messages[-1]["createdAt"]

        assert conversation_updated_at == last_agent_created_at, (
            f"Group conversationUpdatedAt must equal last agentMessage createdAt. "
            f"conversationUpdatedAt: {conversation_updated_at}, "
            f"last agentMessage createdAt: {last_agent_created_at}"
        )

    def test_7_4_3_updated_at_in_get_matches(self, client):
        """发送消息后，GET /conversations 的 updatedAt 与 conversationUpdatedAt 一致"""
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "GET一致性检查",
        })
        assert r.status_code == 201
        send_updated_at = r.json()["conversationUpdatedAt"]

        convs = client.get("/conversations").json()
        direct = [c for c in convs if c["id"] == "direct-architect-default"][0]

        assert direct["updatedAt"] == send_updated_at, (
            f"GET updatedAt must match send conversationUpdatedAt. "
            f"GET: {direct['updatedAt']}, Send: {send_updated_at}"
        )

    def test_7_4_4_all_agent_created_at_after_user_created_at(self, client):
        """所有agent回复的createdAt >= 用户消息的createdAt"""
        r = client.post("/messages", json={
            "conversationId": "direct-architect-default",
            "content": "时间顺序检查",
        })
        assert r.status_code == 201
        body = r.json()

        user_created_at = body["userMessage"]["createdAt"]
        for agent_msg in body["agentMessages"]:
            assert agent_msg["createdAt"] >= user_created_at, (
                f"Agent message created_at must be >= user message created_at. "
                f"User: {user_created_at}, Agent({agent_msg['senderId']}): {agent_msg['createdAt']}"
            )
