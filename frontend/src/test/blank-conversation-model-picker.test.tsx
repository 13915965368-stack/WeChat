import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConversationSidebar } from "../components/ConversationSidebar";
import { ModelPickerModal } from "../components/ModelPickerModal";
import type { Agent, Conversation, Message, ModelConfig } from "../types/chat";

const agents: Agent[] = [
  {
    id: "architect",
    name: "Architect",
    roleSummary: "结构化拆解",
    styleSummary: "偏框架化",
    systemPrompt: "你是 Architect。",
    avatar: "A",
    themeColor: "#D4A574",
    themeLight: "#F5E6D3",
    themeSoft: "#FAF3EC",
  },
];

const conversations: Conversation[] = [];
const messages: Message[] = [];

const models: ModelConfig[] = [
  {
    id: "model-openai",
    provider: "openai",
    model: "gpt-4o",
    displayName: "OpenAI - gpt-4o",
    apiFormat: "openai_chat",
    baseUrl: "https://api.openai.com/v1",
    useFullUrl: false,
    status: "available",
    apiKeyConfigured: true,
    supportsImageInput: true,
    supportsFileInput: false,
    supportsSystemPrompt: true,
    supportsStreaming: false,
    contextWindowInput: 128000,
    contextWindowOutput: 8192,
    maxImageCount: 5,
    maxImageSizeMb: 10,
    defaultTemperature: 0.7,
    createdAt: "2026-05-25T00:00:00.000Z",
    updatedAt: "2026-05-25T00:00:00.000Z",
  },
];

describe("空白对话入口", () => {
  it("侧边栏展示空白对话入口", () => {
    const onCreateBlankConversation = vi.fn();

    render(
      <ConversationSidebar
        agents={agents}
        conversations={conversations}
        messages={messages}
        currentDirectAgentId={null}
        activeConversationId=""
        onSelectAgent={vi.fn()}
        onSelectConversation={vi.fn()}
        onCreateAgent={vi.fn()}
        onCreateBlankConversation={onCreateBlankConversation}
        onCreateGroup={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "空白对话" }));

    expect(onCreateBlankConversation).toHaveBeenCalled();
  });

  it("模型选择器可以选择可用模型", () => {
    const onSelect = vi.fn();

    render(
      <ModelPickerModal
        isOpen
        models={models}
        onClose={vi.fn()}
        onSelect={onSelect}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /以此模型开始/i }));

    expect(onSelect).toHaveBeenCalledWith("model-openai");
  });
});
