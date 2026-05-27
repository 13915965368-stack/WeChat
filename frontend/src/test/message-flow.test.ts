import { describe, expect, it } from "vitest";
import { mergeMessageList, replaceOptimisticMessage } from "../utils/messageFlow";
import type { Message } from "../types/chat";

describe("消息合并策略", () => {
  it("会用真实用户消息替换 optimistic 消息", () => {
    const tempMessage: Message = {
      id: "temp-1",
      conversationId: "conv-1",
      senderType: "user",
      senderId: "user",
      content: "临时消息",
      createdAt: "2026-05-18T10:00:00.000Z",
    };
    const confirmedMessage: Message = {
      ...tempMessage,
      id: "msg-1",
      content: "真实消息",
    };

    const result = replaceOptimisticMessage([tempMessage], "temp-1", confirmedMessage);

    expect(result).toEqual([confirmedMessage]);
  });

  it("追加 agent 回复时不会重复插入相同 id 的消息", () => {
    const agentMessage: Message = {
      id: "agent-1",
      conversationId: "conv-1",
      senderType: "agent",
      senderId: "architect",
      content: "回复内容",
      createdAt: "2026-05-18T10:00:01.000Z",
    };

    const result = mergeMessageList([agentMessage], agentMessage);

    expect(result).toHaveLength(1);
    expect(result[0].content).toBe("回复内容");
  });

  it("一次合并多条迁移消息时会全部保留", () => {
    const firstMessage: Message = {
      id: "msg-1",
      conversationId: "conv-1",
      senderType: "user",
      senderId: "user",
      content: "第一条",
      createdAt: "2026-05-18T10:00:00.000Z",
    };
    const secondMessage: Message = {
      id: "msg-2",
      conversationId: "conv-1",
      senderType: "agent",
      senderId: "architect",
      content: "第二条",
      createdAt: "2026-05-18T10:00:01.000Z",
    };

    const result = mergeMessageList([], firstMessage, secondMessage);

    expect(result).toHaveLength(2);
    expect(result.map((message) => message.content)).toEqual(["第一条", "第二条"]);
  });
});
