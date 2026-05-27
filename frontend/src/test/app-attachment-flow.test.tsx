import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";

const apiMocks = vi.hoisted(() => ({
  bulkDeleteConversations: vi.fn(),
  createAgent: vi.fn(),
  createModelConfig: vi.fn(),
  createDirectConversation: vi.fn(),
  createGroupConversation: vi.fn(),
  deleteConversation: vi.fn(),
  deleteModelConfig: vi.fn(),
  getAgents: vi.fn(),
  getConversations: vi.fn(),
  getMessages: vi.fn(),
  getModelConfigs: vi.fn(),
  sendGroupMessageStream: vi.fn(),
  sendMessage: vi.fn(),
  updateAgent: vi.fn(),
  updateAgentModelBinding: vi.fn(),
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
    onSend,
  }: {
    onSend: (content: string, imageFiles: File[]) => Promise<void> | void;
  }) => (
    <div>
      <button
        type="button"
        onClick={() =>
          void onSend(
            "带图消息",
            [new File(["demo-bytes"], "wireframe.png", { type: "image/png" })]
          )
        }
      >
        发送带图消息
      </button>
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
  SettingsPanel: () => null,
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
  ToolPanel: () => <div data-testid="tool-panel" />,
}));

import App from "../App";

describe("App 附件消息链路", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "toast-id") });

    apiMocks.getAgents.mockResolvedValue([
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
        maxImageCount: 5,
        maxImageSizeMb: 10,
        defaultTemperature: null,
        lastValidatedAt: null,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
      },
    ]);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("发送带图消息时会把 attachmentId 与本地文件元数据一并提交", async () => {
    apiMocks.uploadImageAttachment.mockResolvedValue({
      id: "att-uploaded",
      attachmentId: "att-uploaded",
      type: "image",
      mimeType: "image/png",
      previewUrl: "/api/v1/attachments/images/att-uploaded/preview",
      expiresAt: "2026-06-01T00:00:00.000Z",
    });
    apiMocks.sendMessage.mockResolvedValue({
      userMessage: {
        id: "msg-user",
        conversationId: "direct-architect",
        senderType: "user",
        senderId: "user",
        content: "带图消息",
        attachments: [],
        createdAt: "2026-05-26T00:00:01.000Z",
      },
      agentMessages: [],
      conversationUpdatedAt: "2026-05-26T00:00:01.000Z",
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /与 Architect 的对话/ }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "发送带图消息" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "发送带图消息" }));

    await waitFor(() => {
      expect(apiMocks.uploadImageAttachment).toHaveBeenCalledWith(
        expect.any(File),
        "direct-architect"
      );
      expect(apiMocks.sendMessage).toHaveBeenCalledWith({
        conversationId: "direct-architect",
        content: "带图消息",
        attachments: [
          expect.objectContaining({
            id: "att-uploaded",
            attachmentId: "att-uploaded",
            type: "image",
            kind: "image",
            source: "upload",
            mimeType: "image/png",
            previewUrl: "/api/v1/attachments/images/att-uploaded/preview",
            expiresAt: "2026-06-01T00:00:00.000Z",
            name: "wireframe.png",
            size: 10,
          }),
        ],
      });
    });
  });

  it("将 IMAGE_NOT_SUPPORTED 展示为中文业务提示", async () => {
    apiMocks.uploadImageAttachment.mockResolvedValue({
      id: "att-uploaded",
      attachmentId: "att-uploaded",
      type: "image",
      mimeType: "image/png",
      previewUrl: "/api/v1/attachments/images/att-uploaded/preview",
      expiresAt: "2026-06-01T00:00:00.000Z",
    });
    apiMocks.sendMessage.mockRejectedValue(
      new ApiError(
        "image attachments are not supported by the current model",
        422,
        "IMAGE_NOT_SUPPORTED"
      )
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /与 Architect 的对话/ }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "发送带图消息" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "发送带图消息" }));

    await waitFor(() => {
      expect(
        screen.getByText("当前模型不支持图片输入，请切换到支持图片的模型后再试。")
      ).toBeInTheDocument();
    });
  });
});
