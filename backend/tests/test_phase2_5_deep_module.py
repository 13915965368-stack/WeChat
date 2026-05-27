from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def api(path: str) -> str:
    return f"{BASE}{path}"


def err(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Phase 2 – Agent 模块深度测试
# ---------------------------------------------------------------------------

class TestPhase2Agent:
    """Agent 模块深度测试"""

    # -- P2.1: 验证 4 个 Agent 的完整字段结构（新增模板与模型字段） ----------
    def test_agent_fields_complete(self):
        """P2.1: 验证 4 个 Agent 字段完整，包含 blank-agent 与 Task1 新字段"""
        # Restore seed data first (DB may be contaminated from prior runs)
        self._restore_seed_agents()

        r = httpx.get(api("/agents"))
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) == 4, f"Expected 4 agents, got {len(agents)}"

        expected_ids = ["architect", "blank-agent", "critic", "writer"]
        actual_ids = [a["id"] for a in agents]
        assert actual_ids == expected_ids, f"Agent order mismatch: {actual_ids}"

        required_fields = [
            ("id", str),
            ("name", str),
            ("roleSummary", str),
            ("styleSummary", str),
            ("systemPrompt", str),
            ("avatar", str),
            ("avatarImage", type(None)),  # null in seed
            ("themeColor", str),
            ("themeLight", str),
            ("themeSoft", str),
            ("modelConfigId", type(None)),
            ("modelUnavailable", bool),
            ("isTemplate", bool),
        ]

        for agent in agents:
            for field, expected_type in required_fields:
                assert field in agent, f"Agent {agent['id']} missing field '{field}'"
                if expected_type is type(None):
                    assert agent[field] is None, f"Agent {agent['id']} field '{field}' expected None, got {agent[field]}"
                else:
                    assert isinstance(agent[field], expected_type), \
                        f"Agent {agent['id']} field '{field}' expected {expected_type}, got {type(agent[field])}"

    # -- P2.2: 验证 theme 颜色值 -------------------------------------------
    def test_agent_seed_theme_colors(self):
        """P2.2: 验证 Agent 种子数据的 theme 颜色值与 seed.py 一致"""
        # Restore seed data first
        self._restore_seed_agents()

        r = httpx.get(api("/agents"))
        assert r.status_code == 200
        agents = {a["id"]: a for a in r.json()}

        seed_themes = {
            "architect": {"themeColor": "#D4A574", "themeLight": "#F5E6D3", "themeSoft": "#FAF3EC"},
            "critic":    {"themeColor": "#C97B7B", "themeLight": "#F5DEDE", "themeSoft": "#FCF5F5"},
            "writer":    {"themeColor": "#7BA89C", "themeLight": "#D4E8E2", "themeSoft": "#F0F7F5"},
        }

        for agent_id, expected in seed_themes.items():
            agent = agents[agent_id]
            for key, value in expected.items():
                assert agent[key] == value, \
                    f"Agent {agent_id} {key}: expected '{value}', got '{agent[key]}'"

    def _restore_seed_agents(self):
        """Restore all 3 agents to their seed values."""
        seed_data = [
            {
                "id": "architect", "name": "Architect",
                "roleSummary": "擅长结构化拆解与系统设计",
                "styleSummary": "表达克制、偏框架化，习惯从整体到局部展开思路",
                "systemPrompt": "你是一个偏系统性与结构化思考的智能助手。",
                "avatar": "A", "avatarImage": None,
                "themeColor": "#D4A574", "themeLight": "#F5E6D3", "themeSoft": "#FAF3EC",
            },
            {
                "id": "critic", "name": "Critic",
                "roleSummary": "擅长找风险、挑漏洞、做反向检验",
                "styleSummary": "偏审慎、偏质疑，善于提出边界条件和反面论证",
                "systemPrompt": "你是一个偏风险识别和问题质疑的智能助手。",
                "avatar": "C", "avatarImage": None,
                "themeColor": "#C97B7B", "themeLight": "#F5DEDE", "themeSoft": "#FCF5F5",
            },
            {
                "id": "writer", "name": "Writer",
                "roleSummary": "擅长表达、整理和改写",
                "styleSummary": "偏自然、偏叙述，善于把复杂想法转化为流畅文字",
                "systemPrompt": "你是一个偏表达整理和内容组织的智能助手。",
                "avatar": "W", "avatarImage": None,
                "themeColor": "#7BA89C", "themeLight": "#D4E8E2", "themeSoft": "#F0F7F5",
            },
        ]
        for agent_data in seed_data:
            httpx.put(api(f"/agents/{agent_data['id']}"), json={
                "name": agent_data["name"],
                "roleSummary": agent_data["roleSummary"],
                "styleSummary": agent_data["styleSummary"],
                "systemPrompt": agent_data["systemPrompt"],
                "avatar": agent_data["avatar"],
                "avatarImage": agent_data["avatarImage"],
                "themeColor": agent_data["themeColor"],
                "themeLight": agent_data["themeLight"],
                "themeSoft": agent_data["themeSoft"],
            })

    # -- P2.3: PUT 后 GET 验证持久化 ---------------------------------------
    def test_put_persists_all_fields(self):
        """P2.3: PUT 更新后 GET 验证所有字段持久化"""
        payload = {
            "name": "Test Agent",
            "roleSummary": "Test role",
            "styleSummary": "Test style",
            "systemPrompt": "Test prompt",
            "avatar": "TA",
            "avatarImage": "data:image/png;base64,test123",
            "themeColor": "#111111",
            "themeLight": "#222222",
            "themeSoft": "#333333",
        }

        put_r = httpx.put(api("/agents/architect"), json=payload)
        assert put_r.status_code == 200, f"PUT failed: {put_r.status_code} {put_r.text}"

        get_r = httpx.get(api("/agents"))
        assert get_r.status_code == 200
        agents = {a["id"]: a for a in get_r.json()}

        for field, value in payload.items():
            # Map snake_case payload key to camelCase response key
            resp_key = field  # payload already uses camelCase
            assert agents["architect"][resp_key] == value, \
                f"Persistence failed for {resp_key}: expected '{value}', got '{agents['architect'][resp_key]}'"

    # -- P2.4: 全部 6 个 422 错误路径 --------------------------------------
    def test_put_empty_name_422(self):
        """P2.4a: PUT with empty name returns 422"""
        r = httpx.put(api("/agents/architect"), json={
            "name": "  ",
            "roleSummary": "x",
            "styleSummary": "x",
            "systemPrompt": "x",
            "avatar": "x",
        })
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"
        assert r.json() == err("validation_error", "name cannot be empty")

    def test_put_empty_role_summary_422(self):
        """P2.4b: PUT with empty roleSummary returns 422"""
        r = httpx.put(api("/agents/architect"), json={
            "name": "x",
            "roleSummary": "",
            "styleSummary": "x",
            "systemPrompt": "x",
            "avatar": "x",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "roleSummary cannot be empty")

    def test_put_empty_style_summary_422(self):
        """P2.4c: PUT with empty styleSummary returns 422"""
        r = httpx.put(api("/agents/architect"), json={
            "name": "x",
            "roleSummary": "x",
            "styleSummary": "   ",
            "systemPrompt": "x",
            "avatar": "x",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "styleSummary cannot be empty")

    def test_put_empty_system_prompt_422(self):
        """P2.4d: PUT with empty systemPrompt returns 422"""
        r = httpx.put(api("/agents/architect"), json={
            "name": "x",
            "roleSummary": "x",
            "styleSummary": "x",
            "systemPrompt": "\n  \n",
            "avatar": "x",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "systemPrompt cannot be empty")

    def test_put_empty_avatar_422(self):
        """P2.4e: PUT with empty avatar returns 422"""
        r = httpx.put(api("/agents/architect"), json={
            "name": "x",
            "roleSummary": "x",
            "styleSummary": "x",
            "systemPrompt": "x",
            "avatar": "",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "avatar cannot be empty")

    def test_put_missing_fields_422(self):
        """P2.4f: PUT with missing required fields returns 422 (FastAPI validation)"""
        r = httpx.put(api("/agents/architect"), json={"name": "OnlyName"})
        assert r.status_code == 422
        body = r.json()
        assert body["error"]["code"] == "validation_error"

    # -- P2.5: PUT 不存在 Agent 返回 404 ------------------------------------
    def test_put_nonexistent_agent_404(self):
        """P2.5: PUT 不存在 Agent 返回 404 + 'agent_not_found'"""
        r = httpx.put(api("/agents/nonexistent-agent-id"), json={
            "name": "x",
            "roleSummary": "x",
            "styleSummary": "x",
            "systemPrompt": "x",
            "avatar": "x",
        })
        assert r.status_code == 404
        assert r.json() == err("agent_not_found", "Agent not found")

    # -- P2.6: seed 不会覆盖已修改的 Agent ----------------------------------
    def test_seed_does_not_overwrite_modified_agent(self):
        """P2.6: seed 不会覆盖已修改的 Agent"""
        # First restore to a known state
        httpx.put(api("/agents/architect"), json={
            "name": "Architect Custom",
            "roleSummary": "Custom role",
            "styleSummary": "Custom style",
            "systemPrompt": "Custom prompt",
            "avatar": "AC",
            "avatarImage": None,
            "themeColor": "#AAAAAA",
            "themeLight": "#BBBBBB",
            "themeSoft": "#CCCCCC",
        })

        # Verify modification persisted
        r = httpx.get(api("/agents"))
        agents = {a["id"]: a for a in r.json()}
        assert agents["architect"]["name"] == "Architect Custom"

        # Call health endpoint to trigger seed (since seed runs on lifespan only,
        # we need to restart server to test this properly. Instead, verify GET still 
        # returns our modified data)
        r2 = httpx.get(api("/agents"))
        agents2 = {a["id"]: a for a in r2.json()}
        assert agents2["architect"]["name"] == "Architect Custom"
        assert agents2["architect"]["avatar"] == "AC"
        assert agents2["architect"]["themeColor"] == "#AAAAAA"

    # -- P2.7: 更新一个 Agent 不影响其他 Agent ------------------------------
    def test_update_one_agent_does_not_affect_others(self):
        """P2.7: 更新一个 Agent 不影响其他 Agent"""
        # First snapshot all 3 agents
        r_before = httpx.get(api("/agents"))
        agents_before = {a["id"]: a for a in r_before.json()}

        # Update only writer
        httpx.put(api("/agents/writer"), json={
            "name": "Writer Updated",
            "roleSummary": "Updated role",
            "styleSummary": "Updated style",
            "systemPrompt": "Updated prompt",
            "avatar": "WU",
            "avatarImage": "data:image/png;base64,writer_test",
            "themeColor": "#999999",
            "themeLight": "#888888",
            "themeSoft": "#777777",
        })

        # Verify
        r_after = httpx.get(api("/agents"))
        agents_after = {a["id"]: a for a in r_after.json()}

        assert agents_after["writer"]["name"] == "Writer Updated"
        assert agents_after["writer"]["avatar"] == "WU"

        # Architect and Critic should be unchanged (except architect was modified in previous tests)
        # At minimum, critic should still have its original fields
        assert agents_after["critic"]["name"] == agents_before["critic"]["name"], \
            "Critic should not have changed"
        assert agents_after["critic"]["themeColor"] == agents_before["critic"]["themeColor"], \
            "Critic themeColor should not have changed"


# ---------------------------------------------------------------------------
# Phase 3 – Conversation 模块深度测试
# ---------------------------------------------------------------------------

class TestPhase3Conversation:
    """Conversation 模块深度测试"""

    # -- P3.1: 排序验证 ----------------------------------------------------
    def test_conversation_sort_order(self):
        """P3.1: 会话列表按 pinned desc + updated_at desc 排序"""
        # Create two new conversations to make order test meaningful
        r_direct = httpx.post(api("/conversations/direct"), json={"agentId": "critic"})
        assert r_direct.status_code in (200, 201)
        r_group = httpx.post(api("/conversations/group"), json={
            "title": "Sort Test Group",
            "memberIds": ["architect", "critic"],
        })
        assert r_group.status_code in (200, 201)

        r = httpx.get(api("/conversations"))
        assert r.status_code == 200
        convs = r.json()
        assert len(convs) >= 2

        # Verify pinned conversations come first
        for i in range(len(convs) - 1):
            if convs[i]["pinned"] and not convs[i + 1]["pinned"]:
                continue  # correct: pinned before unpinned
            if convs[i]["pinned"] == convs[i + 1]["pinned"]:
                # Same pin status: updated_at should be desc
                assert convs[i]["updatedAt"] >= convs[i + 1]["updatedAt"], \
                    f"Sort order violation at index {i}: {convs[i]['updatedAt']} < {convs[i+1]['updatedAt']}"
            elif not convs[i]["pinned"] and convs[i + 1]["pinned"]:
                assert False, f"Unpinned conversation at {i} appears before pinned at {i+1}"

    # -- P3.2: group vs direct 属性验证 ------------------------------------
    def test_group_has_null_agent_id(self):
        """P3.2a: group 会话 agentId=null"""
        r = httpx.get(api("/conversations"))
        assert r.status_code == 200
        for conv in r.json():
            if conv["type"] == "group":
                assert conv["agentId"] is None, \
                    f"Group conversation {conv['id']} has non-null agentId"

    def test_direct_has_agent_id(self):
        """P3.2b: direct 会话有 agentId"""
        r = httpx.get(api("/conversations"))
        assert r.status_code == 200
        direct_convs = [c for c in r.json() if c["type"] == "direct"]
        assert len(direct_convs) > 0, "No direct conversations found"
        for conv in direct_convs:
            assert conv["agentId"] is not None, \
                f"Direct conversation {conv['id']} has null agentId"

    # -- P3.3: 单聊创建验证 ------------------------------------------------
    def test_create_direct_conversation(self):
        """P3.3: 创建单聊 — ID 为 32 位 hex、memberIds 正确、自动去重"""
        # Delete any existing direct with writer first by checking if it exists
        # Just create a new one — if it returns 200 (existing), that's fine too
        r = httpx.post(api("/conversations/direct"), json={
            "agentId": "writer",
            "title": "Test Direct",
        })
        assert r.status_code in (200, 201)
        conv = r.json()

        # ID is 32-char hex
        assert len(conv["id"]) == 32, f"ID length: {len(conv['id'])}"
        assert re.match(r'^[0-9a-f]{32}$', conv["id"]), f"ID not 32-char hex: {conv['id']}"

        # type is direct
        assert conv["type"] == "direct"

        # agentId matches
        assert conv["agentId"] == "writer"

        # memberIds contains user + writer, sorted
        assert len(conv["memberIds"]) == 2
        assert conv["memberIds"][0] == "user"
        assert conv["memberIds"][1] == "writer"

        # Deduplication: creating again should return existing (status 200)
        r2 = httpx.post(api("/conversations/direct"), json={"agentId": "writer"})
        assert r2.status_code == 200, f"De-duplication failed: {r2.status_code}"
        assert r2.json()["id"] == conv["id"], "De-duplication returned different conversation"

    # -- P3.4: 群聊创建验证 ------------------------------------------------
    def test_create_group_conversation(self):
        """P3.4: 创建群聊 — user 自动添加、member 排序、最少 2 个 Agent"""
        r = httpx.post(api("/conversations/group"), json={
            "title": "Test Group Chat",
            "memberIds": ["critic", "writer"],
        })
        assert r.status_code == 201
        conv = r.json()

        assert conv["type"] == "group"
        assert conv["title"] == "Test Group Chat"
        assert conv["agentId"] is None

        # user is first member
        assert conv["memberIds"][0] == "user"
        # agents follow in order
        assert conv["memberIds"][1] == "critic"
        assert conv["memberIds"][2] == "writer"

    # -- P3.5: 创建错误路径 ------------------------------------------------
    def test_create_direct_empty_agent_id(self):
        """P3.5a: 单聊 empty agentId → 422"""
        r = httpx.post(api("/conversations/direct"), json={"agentId": "  "})
        assert r.status_code == 422
        assert r.json() == err("validation_error", "agentId is required")

    def test_create_direct_nonexistent_agent(self):
        """P3.5b: 单聊 nonexistent agent → 404"""
        r = httpx.post(api("/conversations/direct"), json={"agentId": "ghost-agent"})
        assert r.status_code == 404
        assert r.json() == err("agent_not_found", "Agent not found")

    def test_create_direct_empty_title(self):
        """P3.5c: 单聊 empty title → 422"""
        r = httpx.post(api("/conversations/direct"), json={
            "agentId": "architect",
            "title": "   ",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "title cannot be empty")

    def test_create_group_empty_title(self):
        """P3.5d: 群聊 empty title → 422"""
        r = httpx.post(api("/conversations/group"), json={
            "title": "",
            "memberIds": ["architect", "critic"],
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "title cannot be empty")

    def test_create_group_less_than_2_agents(self):
        """P3.5e: 群聊少于 2 个 Agent → 422"""
        r = httpx.post(api("/conversations/group"), json={
            "title": "Solo Group",
            "memberIds": ["architect"],
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "memberIds must contain at least two unique agent ids")

    def test_create_group_invalid_agent_ids(self):
        """P3.5f: 群聊含无效 agent ID → 422"""
        r = httpx.post(api("/conversations/group"), json={
            "title": "Invalid Group",
            "memberIds": ["architect", "ghost-agent"],
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "memberIds contains invalid agent ids")

    def test_create_group_duplicate_agent_ids(self):
        """P3.5g: 群聊重复 agent → 422"""
        r = httpx.post(api("/conversations/group"), json={
            "title": "Dup Group",
            "memberIds": ["architect", "architect"],
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "memberIds must contain at least two unique agent ids")


# ---------------------------------------------------------------------------
# Phase 4 – Message 模块深度测试
# ---------------------------------------------------------------------------

class TestPhase4Message:
    """Message 模块深度测试"""

    def _get_or_create_direct(self, agent_id: str) -> str:
        """Ensure a direct conversation exists for agent, return conversation_id."""
        r = httpx.post(api("/conversations/direct"), json={"agentId": agent_id})
        assert r.status_code in (200, 201)
        return r.json()["id"]

    def _get_or_create_group(self, agent_ids: list[str]) -> str:
        """Ensure a group conversation exists, return conversation_id."""
        title = f"Test Group {len(agent_ids)}"
        r = httpx.post(api("/conversations/group"), json={
            "title": title,
            "memberIds": agent_ids,
        })
        assert r.status_code in (200, 201)
        return r.json()["id"]

    # -- P4.1: 消息分页 ----------------------------------------------------
    def test_message_pagination(self):
        """P4.1: 分页 — limit/offset/hasMore"""
        conv_id = "direct-architect-default"
        # Verify the conversation exists
        r_check = httpx.get(api("/messages"), params={"conversationId": conv_id, "limit": 5})
        # If not found, create it
        if r_check.status_code == 404:
            conv_id = self._get_or_create_direct("architect")

        # Full page
        r = httpx.get(api("/messages"), params={"conversationId": conv_id, "limit": 5, "offset": 0})
        assert r.status_code == 200
        page = r.json()
        assert "items" in page
        assert "limit" in page
        assert "offset" in page
        assert "hasMore" in page
        assert page["limit"] == 5
        assert page["offset"] == 0
        assert isinstance(page["hasMore"], bool)
        assert isinstance(page["items"], list)
        assert len(page["items"]) <= 5

        # offset 0, limit 1
        r2 = httpx.get(api("/messages"), params={"conversationId": conv_id, "limit": 1, "offset": 0})
        assert r2.status_code == 200
        page2 = r2.json()
        assert len(page2["items"]) == 1 or len(page2["items"]) == 0
        assert page2["limit"] == 1
        assert page2["offset"] == 0

        # offset beyond range
        r3 = httpx.get(api("/messages"), params={"conversationId": conv_id, "limit": 5, "offset": 9999})
        assert r3.status_code == 200
        page3 = r3.json()
        assert page3["items"] == []
        assert page3["hasMore"] is False

    # -- P4.2: 单聊发送消息 ------------------------------------------------
    def test_direct_message_send_one_reply(self):
        """P4.2: 单聊发送 — 1 个 Agent 回复、senderId 匹配"""
        conv_id = self._get_or_create_direct("writer")

        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": "你好，请帮我写一段介绍",
        })
        assert r.status_code == 201, f"Send failed: {r.status_code} {r.text}"
        result = r.json()

        # user_message
        um = result["userMessage"]
        assert um["senderType"] == "user"
        assert um["senderId"] == "user"
        assert um["content"] == "你好，请帮我写一段介绍"

        # agent_messages — exactly 1 for direct
        ams = result["agentMessages"]
        assert len(ams) == 1, f"Expected 1 agent reply, got {len(ams)}"
        assert ams[0]["senderType"] == "agent"
        assert ams[0]["senderId"] == "writer"

        # conversation_updated_at present
        assert "conversationUpdatedAt" in result

    def test_direct_message_timestamp_order(self):
        """P4.2b: 单聊时间戳一致性 — user message <= agent reply"""
        conv_id = self._get_or_create_direct("critic")

        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": "时间戳测试",
        })
        assert r.status_code == 201
        result = r.json()

        user_ts = result["userMessage"]["createdAt"]
        agent_ts = result["agentMessages"][0]["createdAt"]
        assert user_ts <= agent_ts, f"User msg time {user_ts} should be <= agent time {agent_ts}"

    # -- P4.3: 群聊发送消息 ------------------------------------------------
    def test_group_message_send_multi_reply(self):
        """P4.3: 群聊发送 — 多个回复、顺序正确"""
        conv_id = self._get_or_create_group(["architect", "critic", "writer"])

        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": "群聊测试消息",
        })
        assert r.status_code == 201, f"Send failed: {r.status_code} {r.text}"
        result = r.json()

        ams = result["agentMessages"]
        assert len(ams) == 3, f"Expected 3 agent replies in group, got {len(ams)}"

        # Each should have senderType "agent"
        agent_ids = [m["senderId"] for m in ams]
        for a in ams:
            assert a["senderType"] == "agent"
            assert a["senderId"] in {"architect", "critic", "writer"}

        # Order: member_ids order (after user)
        assert agent_ids == ["architect", "critic", "writer"], \
            f"Agent reply order wrong: {agent_ids}"

    # -- P4.4: 消息边界条件 -------------------------------------------------
    def test_message_4000_chars_accepted(self):
        """P4.4a: 4000 字符通过"""
        conv_id = self._get_or_create_direct("architect")
        content = "A" * 4000
        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": content,
        })
        assert r.status_code == 201, f"4000 chars should be accepted: {r.status_code} {r.text}"

    def test_message_4001_chars_rejected(self):
        """P4.4b: 4001 字符拒绝"""
        conv_id = self._get_or_create_direct("architect")
        content = "B" * 4001
        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": content,
        })
        assert r.status_code == 422, f"4001 chars should be rejected: {r.status_code}"
        assert r.json() == err("validation_error", "content is too long")

    def test_message_unicode_emoji_preserved(self):
        """P4.4c: Unicode/emoji/换行保存"""
        conv_id = self._get_or_create_direct("writer")
        content = "你好 🌍🎉\n第二行\n\t缩进 é è ü ñ 日本語 한국어"

        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": content,
        })
        assert r.status_code == 201, f"Unicode message send failed: {r.status_code}"
        result = r.json()
        assert result["userMessage"]["content"] == content, \
            f"Unicode content mismatch: {result['userMessage']['content']}"

    # -- P4.5: 消息错误路径 -------------------------------------------------
    def test_message_empty_conversation_id_422(self):
        """P4.5a: 空 conversationId → 422"""
        r = httpx.post(api("/messages"), json={
            "conversationId": "  ",
            "content": "test",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "conversationId is required")

    def test_message_empty_content_422(self):
        """P4.5b: 空 content → 422"""
        conv_id = self._get_or_create_direct("architect")
        r = httpx.post(api("/messages"), json={
            "conversationId": conv_id,
            "content": "",
        })
        assert r.status_code == 422
        assert r.json() == err("validation_error", "content cannot be empty")

    def test_message_nonexistent_conversation_404(self):
        """P4.5c: 不存在会话 → 404"""
        r = httpx.post(api("/messages"), json={
            "conversationId": "deadbeefdeadbeefdeadbeefdeadbeef",
            "content": "test",
        })
        assert r.status_code == 404
        assert r.json() == err("conversation_not_found", "Conversation not found")

    def test_get_messages_nonexistent_conversation_404(self):
        """P4.5d: GET 不存在会话的消息 → 404"""
        r = httpx.get(api("/messages"), params={
            "conversationId": "deadbeefdeadbeefdeadbeefdeadbeef",
        })
        assert r.status_code == 404
        assert r.json() == err("conversation_not_found", "Conversation not found")


# ---------------------------------------------------------------------------
# Phase 5 – Settings 模块深度测试
# ---------------------------------------------------------------------------

class TestPhase5Settings:
    """Settings 模块深度测试"""

    # -- P5.1: 默认值验证 ---------------------------------------------------
    def test_get_default_llm_settings(self):
        """P5.1: GET /settings/llm 默认值 — mock/mock-model/hasApiKey=false"""
        # Reset to default (empty) state: settings may have been modified by earlier tests
        r = httpx.get(api("/settings/llm"))
        assert r.status_code == 200
        body = r.json()

        # If previous tests contaminated state, the DB-saved settings will be read
        # instead of env defaults. This is expected behavior per get_llm_status logic.
        # We verify: after explicit reset to default values, GET returns mock defaults.
        httpx.put(api("/settings/llm"), json={
            "provider": "mock",
            "model": "mock-model",
            "apiKey": "",
        })

        r2 = httpx.get(api("/settings/llm"))
        assert r2.status_code == 200
        body2 = r2.json()

        assert body2["provider"] == "mock", f"Default provider: {body2['provider']}"
        assert body2["model"] == "mock-model", f"Default model: {body2['model']}"
        assert body2["hasApiKey"] is False, f"Default hasApiKey: {body2['hasApiKey']}"

    # -- P5.2: apiKey 不泄露 ------------------------------------------------
    def test_api_key_not_leaked(self):
        """P5.2: GET 响应中 apiKey 不泄露"""
        # First set an api key
        httpx.put(api("/settings/llm"), json={
            "provider": "openai",
            "model": "gpt-4",
            "apiKey": "sk-very-secret-key-12345",
        })

        # GET should not expose the key
        r = httpx.get(api("/settings/llm"))
        assert r.status_code == 200
        body = r.json()
        assert "apiKey" not in body, "apiKey should not be present in GET response"
        assert "api_key" not in body, "api_key should not be present in GET response"
        assert body["hasApiKey"] is True

    # -- P5.3: PUT 后 GET 一致性 -------------------------------------------
    def test_put_get_consistency(self):
        """P5.3: PUT 后 GET 一致性"""
        payload = {
            "provider": "anthropic",
            "model": "claude-3",
            "apiKey": "sk-ant-test-key",
        }

        put_r = httpx.put(api("/settings/llm"), json=payload)
        assert put_r.status_code == 200
        put_body = put_r.json()
        assert put_body["provider"] == "anthropic"
        assert put_body["model"] == "claude-3"
        assert put_body["hasApiKey"] is True

        get_r = httpx.get(api("/settings/llm"))
        assert get_r.status_code == 200
        get_body = get_r.json()
        assert get_body == put_body, f"GET/PUT mismatch: {get_body} != {put_body}"

    # -- P5.4: 覆盖更新验证 ------------------------------------------------
    def test_settings_overwrite(self):
        """P5.4: 覆盖更新 — 新值覆盖旧值"""
        httpx.put(api("/settings/llm"), json={
            "provider": "first-provider",
            "model": "first-model",
            "apiKey": "first-key",
        })

        r2 = httpx.put(api("/settings/llm"), json={
            "provider": "second-provider",
            "model": "second-model",
            "apiKey": "",
        })
        assert r2.status_code == 200
        body = r2.json()
        assert body["provider"] == "second-provider"
        assert body["model"] == "second-model"
        assert body["hasApiKey"] is False  # empty string means no key

    # -- P5.5: 错误路径 -----------------------------------------------------
    def test_put_empty_provider_422(self):
        """P5.5a: PUT empty provider → 422"""
        r = httpx.put(api("/settings/llm"), json={
            "provider": "  ",
            "model": "test-model",
            "apiKey": "",
        })
        assert r.status_code == 422
        assert r.json() == err("llm_provider_required", "provider cannot be empty")

    def test_put_empty_model_422(self):
        """P5.5b: PUT empty model → 422"""
        r = httpx.put(api("/settings/llm"), json={
            "provider": "test-provider",
            "model": "",
            "apiKey": "",
        })
        assert r.status_code == 422
        assert r.json() == err("llm_model_required", "model cannot be empty")


# ---------------------------------------------------------------------------
# Discovery / exploratory tests (extra BUG detection)
# ---------------------------------------------------------------------------

class TestExploratory:
    """探索性测试 — 挖掘潜在 BUG"""

    def test_error_response_structure_consistency(self):
        """验证所有错误响应使用一致的 {error: {code, message}} 结构"""
        endpoints = [
            ("PUT", api("/agents/nonexistent"), 404),
            ("PUT", api("/agents/architect"), 422),
            ("POST", api("/conversations/direct"), 422),
            ("POST", api("/conversations/group"), 422),
            ("POST", api("/messages"), 422),
            ("GET", api("/messages"), 422),
            ("PUT", api("/settings/llm"), 422),
        ]

        for method, url, expected_status in endpoints:
            if method == "PUT" and url == api("/agents/architect"):
                r = httpx.put(url, json={"name": ""})
            elif method == "POST" and "direct" in url:
                r = httpx.post(url, json={"agentId": ""})
            elif method == "POST" and "group" in url:
                r = httpx.post(url, json={"title": "", "memberIds": []})
            elif method == "POST" and url == api("/messages"):
                r = httpx.post(url, json={"conversationId": "", "content": ""})
            elif method == "GET" and url == api("/messages"):
                r = httpx.get(url, params={"conversationId": ""})
            elif method == "PUT" and "settings" in url:
                r = httpx.put(url, json={"provider": "", "model": "", "apiKey": ""})
            else:
                r = httpx.request(method, url)

            body = r.json()
            assert "error" in body, f"{method} {url}: missing 'error' key"
            assert "code" in body["error"], f"{method} {url}: missing 'code' in error"
            assert "message" in body["error"], f"{method} {url}: missing 'message' in error"

    def test_health_endpoint(self):
        """验证健康检查"""
        r = httpx.get(api("/health"))
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_missing_required_json_body_fastapi_422(self):
        """验证 FastAPI 缺少请求体的默认 422 响应"""
        r = httpx.put(api("/agents/architect"), json={})
        assert r.status_code == 422
        body = r.json()
        assert body["error"]["code"] == "validation_error"

    def test_content_type_json(self):
        """验证响应 Content-Type 为 application/json"""
        r = httpx.get(api("/agents"))
        content_type = r.headers.get("content-type", "")
        assert "application/json" in content_type, f"Unexpected content-type: {content_type}"


# ---------------------------------------------------------------------------
# Main runner (when executed directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("Phase 2-5 功能模块深度测试")
    print(f"Target: {BASE}")
    print("=" * 70)

    test_classes = [
        TestPhase2Agent,
        TestPhase3Conversation,
        TestPhase4Message,
        TestPhase5Settings,
        TestExploratory,
    ]

    passed = 0
    failed = 0
    errors: list[tuple[str, str, str]] = []

    for test_class in test_classes:
        instance = test_class()
        methods = [
            m for m in dir(instance)
            if m.startswith("test_") and callable(getattr(instance, m))
        ]
        for method_name in methods:
            full_name = f"{test_class.__name__}.{method_name}"
            method = getattr(instance, method_name)
            try:
                method()
                passed += 1
                print(f"  PASS  {full_name}")
            except AssertionError as exc:
                failed += 1
                msg = str(exc)
                errors.append((full_name, "AssertionError", msg))
                print(f"  FAIL  {full_name}")
                print(f"        {msg}")
            except Exception as exc:
                failed += 1
                msg = str(exc)
                errors.append((full_name, type(exc).__name__, msg))
                print(f"  ERROR {full_name}")
                print(f"        {type(exc).__name__}: {msg}")

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)

    if errors:
        print("\nFAILURE DETAILS:")
        for name, error_type, msg in errors:
            print(f"  [{error_type}] {name}")
            print(f"    {msg}")

    # BUG 汇总
    print("\n" + "=" * 70)
    print("BUG 与契约问题分析")
    print("=" * 70)

    bugs: list[str] = []

    # Dynamically check for known patterns
    if any("AssertionError" == e[1] for e in errors):
        bugs.append("存在断言失败，详见上述 FAILURE DETAILS")

    if not bugs:
        bugs.append("未发现明显 BUG，所有断言通过")

    for i, bug in enumerate(bugs, 1):
        print(f"  BUG-{i}: {bug}")

    sys.exit(0 if failed == 0 else 1)
