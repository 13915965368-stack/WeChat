import { describe, expect, it } from "vitest";

import type { Agent, Conversation } from "../types/chat";
import {
  findBlankTemplateAgent,
  isBlankTemplateAgent,
  resolveConversationModelConfigId,
} from "../utils/blankConversation";

function createAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "architect",
    name: "Architect",
    roleSummary: "结构化拆解",
    styleSummary: "偏框架化",
    systemPrompt: "你是 Architect。",
    avatar: "A",
    themeColor: "#D4A574",
    themeLight: "#F5E6D3",
    themeSoft: "#FAF3EC",
    ...overrides,
  };
}

function createConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conv-1",
    type: "direct",
    title: "测试对话",
    memberIds: ["user", "architect"],
    agentId: "architect",
    createdAt: "2026-05-26T10:00:00.000Z",
    updatedAt: "2026-05-26T10:00:00.000Z",
    ...overrides,
  };
}

describe("blank 对话规则", () => {
  it("只将内置模板识别为 blank Agent，不误判普通空白命名 Agent", () => {
    const regularAgent = createAgent({
      id: "custom-empty-agent",
      name: "我的空白助手",
      systemPrompt: "你是一个普通自定义助手。",
    });
    const blankTemplateAgent = createAgent({
      id: "blank-agent",
      name: "Blank Agent",
      systemPrompt: "",
      isTemplate: true,
    });

    expect(isBlankTemplateAgent(regularAgent)).toBe(false);
    expect(findBlankTemplateAgent([regularAgent, blankTemplateAgent])?.id).toBe("blank-agent");
  });

  it("blank 单聊只使用会话级 modelConfigId，不回退到模板 Agent 绑定", () => {
    const blankTemplateAgent = createAgent({
      id: "blank-agent",
      systemPrompt: "",
      isTemplate: true,
      modelConfigId: "agent-level-model",
    });
    const blankConversation = createConversation({
      agentId: "blank-agent",
      memberIds: ["user", "blank-agent"],
      modelConfigId: null,
    });

    expect(resolveConversationModelConfigId(blankConversation, blankTemplateAgent)).toBeNull();
  });

  it("普通单聊仍然在缺少会话绑定时回退到 Agent 模型", () => {
    const directAgent = createAgent({
      modelConfigId: "agent-level-model",
    });
    const directConversation = createConversation({
      modelConfigId: null,
    });

    expect(resolveConversationModelConfigId(directConversation, directAgent)).toBe("agent-level-model");
  });

  it("blank 单聊存在会话级模型时优先使用该模型", () => {
    const blankTemplateAgent = createAgent({
      id: "blank-agent",
      systemPrompt: "",
      isTemplate: true,
      modelConfigId: "agent-level-model",
    });
    const blankConversation = createConversation({
      agentId: "blank-agent",
      memberIds: ["user", "blank-agent"],
      modelConfigId: "conversation-level-model",
    });

    expect(resolveConversationModelConfigId(blankConversation, blankTemplateAgent)).toBe(
      "conversation-level-model"
    );
  });
});
