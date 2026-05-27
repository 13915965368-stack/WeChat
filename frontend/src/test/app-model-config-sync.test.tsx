import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  bulkDeleteConversations: vi.fn(),
  createAgent: vi.fn(),
  createModelConfig: vi.fn(),
  createDirectConversation: vi.fn(),
  createGroupConversation: vi.fn(),
  deleteModelConfig: vi.fn(),
  deleteConversation: vi.fn(),
  getAgents: vi.fn(),
  getConversations: vi.fn(),
  getMessages: vi.fn(),
  getModelConfigs: vi.fn(),
  sendGroupMessageStream: vi.fn(),
  sendMessage: vi.fn(),
  updateAgentModelBinding: vi.fn(),
  updateAgent: vi.fn(),
  updateModelConfig: vi.fn(),
  updateAgentPin: vi.fn(),
  updateConversationPin: vi.fn(),
  uploadImageAttachment: vi.fn(),
  validateModelConfig: vi.fn(),
}));

vi.mock("../api/chat", () => apiMocks);

vi.mock("../components/AgentProfilePanel", () => ({
  AgentProfilePanel: () => <div data-testid="agent-profile-panel" />,
}));

vi.mock("../components/AgentDetailPage", () => ({
  AgentDetailPage: () => <div data-testid="agent-detail-page" />,
}));

vi.mock("../components/AgentEditPage", () => ({
  AgentEditPage: () => <div data-testid="agent-edit-page" />,
}));

vi.mock("../components/ConversationSidebar", () => ({
  ConversationSidebar: () => <div data-testid="conversation-sidebar" />,
}));

vi.mock("../components/ChatMessageList", () => ({
  ChatMessageList: () => <div data-testid="chat-message-list" />,
}));

vi.mock("../components/MessageComposer", () => ({
  MessageComposer: ({
    canSend,
    sendDisabledReason,
  }: {
    canSend?: boolean;
    sendDisabledReason?: string;
  }) => (
    <div data-testid="send-capability">
      {canSend ? "enabled" : sendDisabledReason ?? "disabled"}
    </div>
  ),
}));

vi.mock("../components/GroupMemberPanel", () => ({
  GroupMemberPanel: () => <div data-testid="group-member-panel" />,
}));

vi.mock("../components/CreateGroupModal", () => ({
  CreateGroupModal: () => null,
}));

vi.mock("../components/SettingsPanel", () => ({
  SettingsPanel: ({
    isOpen,
    onValidateModelConfig,
  }: {
    isOpen: boolean;
    onValidateModelConfig: (id: string) => void;
  }) =>
    isOpen ? (
      <button type="button" onClick={() => onValidateModelConfig("model-openai")}>
        触发模型校验
      </button>
    ) : null,
}));

vi.mock("../components/ModelPickerModal", () => ({
  ModelPickerModal: () => null,
}));

vi.mock("../components/ToastViewport", () => ({
  ToastViewport: () => null,
}));

vi.mock("../components/CreateAgentModal", () => ({
  CreateAgentModal: () => null,
}));

vi.mock("../components/ToolPanel", () => ({
  ToolPanel: ({ onSelectTool }: { onSelectTool: (toolId: string) => void }) => (
    <button type="button" onClick={() => onSelectTool("settings")}>
      打开设置
    </button>
  ),
}));

import App from "../App";

describe("App 模型状态同步", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "toast-id") });

    apiMocks.getAgents
      .mockResolvedValueOnce([
        {
          id: "architect",
          name: "Architect",
          roleSummary: "结构化拆解",
          styleSummary: "偏框架化",
          systemPrompt: "你是 Architect。",
          avatar: "A",
          avatarImage: null,
          themeColor: "#D4A574",
          themeLight: "#F5E6D3",
          themeSoft: "#FAF3EC",
          modelConfigId: "model-openai",
          modelUnavailable: false,
          isTemplate: false,
          pinned: false,
          pinnedAt: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "architect",
          name: "Architect",
          roleSummary: "结构化拆解",
          styleSummary: "偏框架化",
          systemPrompt: "你是 Architect。",
          avatar: "A",
          avatarImage: null,
          themeColor: "#D4A574",
          themeLight: "#F5E6D3",
          themeSoft: "#FAF3EC",
          modelConfigId: "model-openai",
          modelUnavailable: true,
          isTemplate: false,
          pinned: false,
          pinnedAt: null,
        },
      ]);
    apiMocks.getConversations.mockResolvedValue([
      {
        id: "direct-architect",
        type: "direct",
        title: "与 Architect 的对话",
        memberIds: ["user", "architect"],
        agentId: "architect",
        modelConfigId: null,
        isDisabled: false,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
    ]);
    apiMocks.getMessages.mockResolvedValue([]);
    apiMocks.getModelConfigs.mockResolvedValue([
      {
        id: "model-openai",
        provider: "openai",
        model: "gpt-4o",
        displayName: "OpenAI - gpt-4o",
        apiFormat: "openai_chat",
        baseUrl: "https://api.openai.com/v1",
        useFullUrl: false,
        status: "available",
        statusMessage: null,
        apiKeyConfigured: true,
        supportsImageInput: true,
        supportsFileInput: false,
        supportsSystemPrompt: true,
        supportsStreaming: false,
        contextWindowInput: 128000,
        contextWindowOutput: null,
        maxImageCount: null,
        maxImageSizeMb: null,
        defaultTemperature: null,
        lastValidatedAt: null,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
      },
    ]);
    apiMocks.validateModelConfig.mockResolvedValue({
      id: "model-openai",
      provider: "openai",
      model: "gpt-4o",
      displayName: "OpenAI - gpt-4o",
      apiFormat: "openai_chat",
      baseUrl: "https://api.openai.com/v1",
      useFullUrl: false,
      status: "failed",
      statusMessage: "baseUrl cannot be empty",
      apiKeyConfigured: true,
      supportsImageInput: true,
      supportsFileInput: false,
      supportsSystemPrompt: true,
      supportsStreaming: false,
      contextWindowInput: 128000,
      contextWindowOutput: null,
      maxImageCount: null,
      maxImageSizeMb: null,
      defaultTemperature: null,
      lastValidatedAt: "2026-05-26T01:00:00.000Z",
      createdAt: "2026-05-26T00:00:00.000Z",
      updatedAt: "2026-05-26T01:00:00.000Z",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("模型校验后会刷新 Agent 状态并禁用发送", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /与 Architect 的对话/ }));

    await waitFor(() => {
      expect(screen.getByTestId("send-capability")).toHaveTextContent("enabled");
    });

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("button", { name: "触发模型校验" }));

    await waitFor(() => {
      expect(screen.getByTestId("send-capability")).toHaveTextContent(
        "当前 Agent 绑定的模型已失效，请先重新绑定。"
      );
    });

    expect(apiMocks.validateModelConfig).toHaveBeenCalledWith("model-openai");
    expect(apiMocks.getAgents).toHaveBeenCalledTimes(2);
  });
});
