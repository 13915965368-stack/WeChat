import { describe, it, expect } from 'vitest';
import type { Conversation } from '../types/chat';

function createConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'test-conv',
    type: 'direct',
    title: '测试对话',
    memberIds: ['user', 'architect'],
    agentId: 'architect',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

describe('Conversation 模型', () => {
  it('单聊应该包含 agentId', () => {
    const conv = createConversation({ type: 'direct', agentId: 'architect' });
    expect(conv.type).toBe('direct');
    expect(conv.agentId).toBe('architect');
    expect(conv.memberIds).toContain('user');
    expect(conv.memberIds).toContain('architect');
  });

  it('群聊不应该有 agentId', () => {
    const conv = createConversation({
      type: 'group',
      memberIds: ['user', 'architect', 'critic'],
      agentId: undefined,
    });
    expect(conv.type).toBe('group');
    expect(conv.agentId).toBeUndefined();
    expect(conv.memberIds.length).toBe(3);
  });

  it('新建单聊时 updatedAt 应该等于 createdAt', () => {
    const now = new Date().toISOString();
    const conv = createConversation({ createdAt: now, updatedAt: now });
    expect(conv.updatedAt).toBe(conv.createdAt);
  });

  it('置顶会话应该在排序中优先', () => {
    const convs: Conversation[] = [
      createConversation({ id: '1', updatedAt: '2024-01-01T00:00:00Z', pinned: false }),
      createConversation({ id: '2', updatedAt: '2024-01-02T00:00:00Z', pinned: true }),
      createConversation({ id: '3', updatedAt: '2024-01-03T00:00:00Z', pinned: false }),
    ];

    const sorted = [...convs].sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });

    expect(sorted[0].id).toBe('2'); // 置顶的优先
    expect(sorted[1].id).toBe('3'); // 然后按 updatedAt 倒序
    expect(sorted[2].id).toBe('1');
  });

  it('消息应该归属到 conversationId', () => {
    const message = {
      id: 'msg-1',
      conversationId: 'direct-architect-default',
      senderType: 'user' as const,
      senderId: 'user',
      content: '测试消息',
      createdAt: new Date().toISOString(),
    };

    expect(message.conversationId).toBe('direct-architect-default');
    expect(message.senderType).toBe('user');
  });
});

describe('会话时间更新', () => {
  it('发送消息后 updatedAt 应该更新', () => {
    const conv = createConversation({ updatedAt: '2024-01-01T00:00:00Z' });
    const newUpdatedAt = new Date().toISOString();

    // 模拟更新
    const updated = { ...conv, updatedAt: newUpdatedAt };

    expect(new Date(updated.updatedAt).getTime()).toBeGreaterThan(
      new Date(conv.updatedAt).getTime()
    );
  });

  it('Agent 回复后 updatedAt 也应该更新', () => {
    const conv = createConversation({ updatedAt: '2024-01-01T00:00:00Z' });
    const replyTime = new Date().toISOString();

    const updated = { ...conv, updatedAt: replyTime };

    expect(new Date(updated.updatedAt).getTime()).toBeGreaterThan(
      new Date(conv.updatedAt).getTime()
    );
  });
});
