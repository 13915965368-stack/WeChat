import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  updateModelConfig: vi.fn(),
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
  ConversationSidebar: ({
    conversations,
    onSelectConversation,
  }: {
    conversations?: Array<{ id: string; title: string }>;
    onSelectConversation?: (conversationId: string) => void;
  }) => (
    <div data-testid="conversation-sidebar">
      {(conversations ?? []).map((conversation) => (
        <button
          key={conversation.id}
          type="button"
          onClick={() => onSelectConversation?.(conversation.id)}
          aria-label={`侧栏切换 ${conversation.id}`}
        >
          切换
        </button>
      ))}
    </div>
  ),
}));

vi.mock("../components/ChatMessageList", () => ({
  ChatMessageList: ({ messages }: { messages?: Array<{ id: string; content: string }> }) => (
    <div data-testid="chat-message-list">
      {(messages ?? []).map((message) => (
        <div key={message.id}>{message.content}</div>
      ))}
    </div>
  ),
}));

vi.mock("../components/MessageComposer", () => ({
  MessageComposer: ({
    canSend,
    sendDisabledReason,
    canAttachImage,
    imageCapabilityReason,
    showThinkingToggle,
    thinkingEnabled,
    onToggleThinking,
    onSend,
  }: {
    canSend?: boolean;
    sendDisabledReason?: string;
    canAttachImage?: boolean;
    imageCapabilityReason?: string;
    showThinkingToggle?: boolean;
    thinkingEnabled?: boolean;
    onToggleThinking?: () => void;
    onSend?: (
      content: string,
      imageFiles: File[],
      options?: { thinkingEnabled?: boolean }
    ) => Promise<void> | void;
  }) => (
    <div>
      <div data-testid="send-capability">{canSend ? "enabled" : sendDisabledReason ?? "disabled"}</div>
      <div data-testid="image-capability">
        {canAttachImage ? "image-enabled" : imageCapabilityReason ?? "image-disabled"}
      </div>
      <div data-testid="thinking-toggle-visibility">{showThinkingToggle ? "shown" : "hidden"}</div>
      <div data-testid="thinking-toggle-state">{thinkingEnabled ? "on" : "off"}</div>
      {showThinkingToggle ? (
        <button type="button" onClick={() => onToggleThinking?.()}>
          切换 thinking
        </button>
      ) : null}
      <button
        type="button"
        onClick={() => void onSend?.("请开始群聊接力", [], { thinkingEnabled })}
      >
        发送测试消息
      </button>
    </div>
  ),
}));

vi.mock("../components/GroupMemberPanel", () => ({
  GroupMemberPanel: () => <div data-testid="group-member-panel" />,
}));

vi.mock("../components/CreateGroupModal", () => ({
  CreateGroupModal: ({
    isOpen,
    onCreateGroup,
  }: {
    isOpen: boolean;
    onCreateGroup: (title: string, memberIds: string[], historyRounds: number) => void;
  }) =>
    isOpen ? (
      <button type="button" onClick={() => onCreateGroup("评审群", ["architect", "critic"], 6)}>
        确认创建群聊
      </button>
    ) : null,
}));

vi.mock("../components/SettingsPanel", () => ({
  SettingsPanel: () => null,
}));

vi.mock("../components/ModelPickerModal", () => ({
  ModelPickerModal: () => null,
}));

vi.mock("../components/ToastViewport", () => ({
  ToastViewport: ({
    toasts,
  }: {
    toasts?: Array<{ id: string; title: string; description?: string }>;
  }) => (
    <div data-testid="toast-viewport">
      {(toasts ?? []).map((toast) => (
        <div key={toast.id}>
          <div>{toast.title}</div>
          {toast.description ? <div>{toast.description}</div> : null}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("../components/CreateAgentModal", () => ({
  CreateAgentModal: () => null,
}));

vi.mock("../components/ToolPanel", () => ({
  ToolPanel: () => null,
  useToolActivities: () => ({
    activities: [],
    handleToolCall: vi.fn(),
    handleToolResult: vi.fn(),
    clearActivities: vi.fn(),
  }),
}));

import App from "../App";

const agents = [
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
    pinned: true,
    pinnedAt: "2026-05-26T00:00:00.000Z",
  },
  {
    id: "critic",
    name: "Critic",
    roleSummary: "专注风险审查",
    styleSummary: "偏审慎",
    systemPrompt: "你是 Critic。",
    avatar: "C",
    avatarImage: null,
    themeColor: "#C97B7B",
    themeLight: "#F5DEDE",
    themeSoft: "#FCF5F5",
    modelConfigId: "model-critic",
    modelUnavailable: false,
    isTemplate: false,
    pinned: false,
    pinnedAt: null,
  },
];

const modelConfigs = [
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
  {
    id: "model-critic",
    provider: "openai",
    model: "gpt-4o-mini",
    displayName: "OpenAI - gpt-4o-mini",
    apiFormat: "openai_chat",
    baseUrl: "https://api.openai.com/v1",
    useFullUrl: false,
    status: "failed",
    statusMessage: "invalid key",
    apiKeyConfigured: true,
    supportsImageInput: false,
    supportsFileInput: false,
    supportsSystemPrompt: true,
    supportsStreaming: false,
    contextWindowInput: 64000,
    contextWindowOutput: null,
    maxImageCount: 1,
    maxImageSizeMb: 5,
    defaultTemperature: null,
    lastValidatedAt: null,
    createdAt: "2026-05-26T00:00:00.000Z",
    updatedAt: "2026-05-26T00:00:00.000Z",
  },
];

beforeEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "toast-id") });

  apiMocks.getAgents.mockResolvedValue(agents);
  apiMocks.getMessages.mockResolvedValue([]);
  apiMocks.getModelConfigs.mockResolvedValue(modelConfigs);
  apiMocks.sendGroupMessageStream.mockResolvedValue(undefined);
});

describe("App 首页与群聊流程", () => {
  it("启动时先显示首页默认态，并列出最近会话入口", async () => {
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

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "首页" })).toBeInTheDocument();
    });

    expect(screen.getByText("当前 Agent")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    expect(screen.queryByTestId("send-capability")).not.toBeInTheDocument();
  });

  it("群聊发送能力按成员整体判断，不再只看当前焦点 Agent", async () => {
    apiMocks.getConversations.mockResolvedValue([
      {
        id: "group-review",
        type: "group",
        title: "评审群",
        memberIds: ["user", "architect", "critic"],
        modelConfigId: null,
        isDisabled: false,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
    ]);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /评审群/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /评审群/ }));

    await waitFor(() => {
      expect(screen.getByTestId("send-capability")).toHaveTextContent(
        "Critic 的模型暂不可用，请先校验或更换模型。"
      );
    });

    expect(screen.getByTestId("image-capability")).toHaveTextContent(
      "Critic 的模型暂不可用，请先校验或更换模型。"
    );
    expect(screen.getByTestId("thinking-toggle-visibility")).toHaveTextContent("hidden");
  });

  it("单聊 thinking 开关按会话维度持久化，并随发送请求透传", async () => {
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
      {
        id: "direct-critic",
        type: "direct",
        title: "与 Critic 的对话",
        memberIds: ["user", "critic"],
        agentId: "critic",
        modelConfigId: "model-openai",
        isDisabled: false,
        createdAt: "2026-05-26T00:10:00.000Z",
        updatedAt: "2026-05-26T00:10:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
    ]);
    apiMocks.getModelConfigs.mockResolvedValue([
      modelConfigs[0],
      {
        ...modelConfigs[1],
        id: "model-openai-2",
        status: "available",
        statusMessage: null,
      },
    ]);
    apiMocks.sendMessage.mockResolvedValue({
      userMessage: {
        id: "msg-user",
        conversationId: "direct-architect",
        senderType: "user",
        senderId: "user",
        content: "请开始群聊接力",
        createdAt: "2026-05-26T10:00:00.000Z",
      },
      agentMessages: [],
      conversationUpdatedAt: "2026-05-26T10:00:01.000Z",
      usageSummary: null,
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /与 Critic 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /与 Architect 的对话/ }));

    await waitFor(() => {
      expect(screen.getByTestId("thinking-toggle-visibility")).toHaveTextContent("shown");
      expect(screen.getByTestId("thinking-toggle-state")).toHaveTextContent("off");
    });

    fireEvent.click(screen.getByRole("button", { name: "切换 thinking" }));

    await waitFor(() => {
      expect(screen.getByTestId("thinking-toggle-state")).toHaveTextContent("on");
    });

    fireEvent.click(screen.getByRole("button", { name: "发送测试消息" }));

    await waitFor(() => {
      expect(apiMocks.sendMessage).toHaveBeenCalledWith({
        conversationId: "direct-architect",
        content: "请开始群聊接力",
        attachments: undefined,
        options: {
          thinking: {
            enabled: true,
          },
        },
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "侧栏切换 direct-critic" }));

    await waitFor(() => {
      expect(screen.getByTestId("thinking-toggle-state")).toHaveTextContent("off");
    });

    fireEvent.click(screen.getByRole("button", { name: "侧栏切换 direct-architect" }));

    await waitFor(() => {
      expect(screen.getByTestId("thinking-toggle-state")).toHaveTextContent("on");
    });
  });

  it("单聊 warnings 会显示未生成可展示回复提示", async () => {
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
    apiMocks.sendMessage.mockResolvedValue({
      userMessage: {
        id: "msg-user",
        conversationId: "direct-architect",
        senderType: "user",
        senderId: "user",
        content: "请开始群聊接力",
        createdAt: "2026-05-26T10:00:00.000Z",
      },
      agentMessages: [],
      conversationUpdatedAt: "2026-05-26T10:00:01.000Z",
      usageSummary: null,
      warnings: [
        {
          code: "model_empty_reply",
          message: "Architect 未返回可展示回复",
        },
      ],
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /与 Architect 的对话/ }));
    fireEvent.click(screen.getByRole("button", { name: "发送测试消息" }));

    await waitFor(() => {
      expect(screen.getAllByText("Architect 未返回可展示回复").length).toBeGreaterThan(0);
      expect(screen.getByText("未生成可展示回复")).toBeInTheDocument();
    });
  });

  it("从直聊发起群聊后会提交来源直聊与真实历史迁移语义", async () => {
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
    apiMocks.createGroupConversation.mockResolvedValue({
      id: "group-review",
      type: "group",
      title: "评审群",
      memberIds: ["user", "architect", "critic"],
      sourceConversationId: "direct-architect",
      modelConfigId: null,
      isDisabled: false,
      createdAt: "2026-05-26T01:00:00.000Z",
      updatedAt: "2026-05-26T01:00:00.000Z",
      pinned: false,
      pinnedAt: null,
    });
    apiMocks.getMessages.mockImplementation(async (conversationId: string, limit = 100, offset = 0) => {
      if (conversationId === "group-review") {
        const items = [
          {
            id: "migrated-user-1",
            conversationId: "group-review",
            senderType: "user",
            senderId: "user",
            content: "第一轮问题",
            createdAt: "2026-05-26T00:30:00.000Z",
          },
          {
            id: "migrated-agent-1",
            conversationId: "group-review",
            senderType: "agent",
            senderId: "architect",
            content: "第一轮回答",
            createdAt: "2026-05-26T00:31:00.000Z",
          },
        ];
        return items.slice(offset, offset + limit);
      }
      return [];
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /与 Architect 的对话/ }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "基于当前直聊发起群聊" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "基于当前直聊发起群聊" }));
    fireEvent.click(screen.getByRole("button", { name: "确认创建群聊" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "评审群" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "返回来源直聊" })).toBeInTheDocument();
      expect(screen.getByText("第一轮问题")).toBeInTheDocument();
      expect(screen.getByText("第一轮回答")).toBeInTheDocument();
    });

    expect(apiMocks.createGroupConversation).toHaveBeenCalledWith({
      title: "评审群",
      memberIds: ["architect", "critic"],
      sourceConversationId: "direct-architect",
      historyRounds: 6,
    });
    expect(apiMocks.getMessages).toHaveBeenCalledWith("group-review", 100, 0);

    fireEvent.click(screen.getByRole("button", { name: "返回来源直聊" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "与 Architect 的对话" })).toBeInTheDocument();
    });
  });

  it("刷新后读取到带 sourceConversationId 的群聊时，仍可返回来源直聊", async () => {
    apiMocks.getConversations.mockResolvedValue([
      {
        id: "group-review",
        type: "group",
        title: "评审群",
        memberIds: ["user", "architect", "critic"],
        sourceConversationId: "direct-architect",
        modelConfigId: null,
        isDisabled: false,
        createdAt: "2026-05-26T01:00:00.000Z",
        updatedAt: "2026-05-26T01:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
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

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /评审群/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /与 Architect 的对话/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /评审群/ }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "评审群" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "返回来源直聊" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "返回来源直聊" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "与 Architect 的对话" })).toBeInTheDocument();
    });
  });

  it("群聊发送时走 SSE 并在每个 Agent 完成后立刻合并消息", async () => {
    apiMocks.getConversations.mockResolvedValue([
      {
        id: "group-stream",
        type: "group",
        title: "流式群聊",
        memberIds: ["user", "architect", "critic"],
        modelConfigId: null,
        isDisabled: false,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
    ]);
    apiMocks.getModelConfigs.mockResolvedValue([
      modelConfigs[0],
      {
        ...modelConfigs[1],
        status: "available",
        statusMessage: null,
      },
    ]);
    apiMocks.sendGroupMessageStream.mockImplementation(
      async (
        _payload: { conversationId: string; content: string },
        onEvent: (event: {
          event: string;
          payload: {
            conversationId: string;
            message?: { id: string; content: string; senderId: string; senderType: "user" | "agent"; conversationId: string; createdAt: string };
            conversationUpdatedAt?: string | null;
          };
        }) => void
      ) => {
        onEvent({
          event: "user_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-user",
              conversationId: "group-stream",
              senderType: "user",
              senderId: "user",
              content: "请开始群聊接力",
              createdAt: "2026-05-26T10:00:00.000Z",
            },
          },
        });
        onEvent({
          event: "agent_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-architect",
              conversationId: "group-stream",
              senderType: "agent",
              senderId: "architect",
              content: "先拆结构。",
              createdAt: "2026-05-26T10:00:01.000Z",
            },
            conversationUpdatedAt: "2026-05-26T10:00:01.000Z",
          },
        });
        onEvent({
          event: "agent_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-critic",
              conversationId: "group-stream",
              senderType: "agent",
              senderId: "critic",
              content: "补风险边界。",
              createdAt: "2026-05-26T10:00:02.000Z",
            },
            conversationUpdatedAt: "2026-05-26T10:00:02.000Z",
          },
        });
        onEvent({
          event: "done",
          payload: {
            conversationId: "group-stream",
            conversationUpdatedAt: "2026-05-26T10:00:02.000Z",
          },
        });
      }
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /流式群聊/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /流式群聊/ }));

    await waitFor(() => {
      expect(screen.getByTestId("send-capability")).toHaveTextContent("enabled");
    });

    fireEvent.click(screen.getByRole("button", { name: "发送测试消息" }));

    await waitFor(() => {
      expect(apiMocks.sendGroupMessageStream).toHaveBeenCalledWith(
        {
          conversationId: "group-stream",
          content: "请开始群聊接力",
          attachments: undefined,
        },
        expect.any(Function)
      );
    });

    await waitFor(() => {
      expect(screen.getByText("请开始群聊接力")).toBeInTheDocument();
      expect(screen.getByText("先拆结构。")).toBeInTheDocument();
      expect(screen.getByText("补风险边界。")).toBeInTheDocument();
    });

    expect(apiMocks.sendMessage).not.toHaveBeenCalled();
  });

  it("群聊流中部分成员失败时，仍继续展示后续回复并显示失败提示", async () => {
    apiMocks.getAgents.mockResolvedValue([
      ...agents,
      {
        id: "writer",
        name: "Writer",
        roleSummary: "负责整理表达",
        styleSummary: "偏总结",
        systemPrompt: "你是 Writer。",
        avatar: "W",
        avatarImage: null,
        themeColor: "#7BA89C",
        themeLight: "#E2EFEA",
        themeSoft: "#F4F8F6",
        modelConfigId: "model-openai",
        modelUnavailable: false,
        isTemplate: false,
        pinned: false,
        pinnedAt: null,
      },
    ]);
    apiMocks.getConversations.mockResolvedValue([
      {
        id: "group-stream",
        type: "group",
        title: "流式群聊",
        memberIds: ["user", "architect", "critic", "writer"],
        modelConfigId: null,
        isDisabled: false,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
    ]);
    apiMocks.getModelConfigs.mockResolvedValue([
      modelConfigs[0],
      {
        ...modelConfigs[1],
        status: "available",
        statusMessage: null,
      },
    ]);
    apiMocks.sendGroupMessageStream.mockImplementation(
      async (
        _payload: { conversationId: string; content: string },
        onEvent: (event: {
          event: string;
          payload: {
            conversationId: string;
            message?: {
              id: string;
              content: string;
              senderId: string;
              senderType: "user" | "agent";
              conversationId: string;
              createdAt: string;
            };
            error?: { message: string };
            conversationUpdatedAt?: string | null;
          };
        }) => void
      ) => {
        onEvent({
          event: "user_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-user",
              conversationId: "group-stream",
              senderType: "user",
              senderId: "user",
              content: "请开始群聊接力",
              createdAt: "2026-05-26T10:00:00.000Z",
            },
          },
        });
        onEvent({
          event: "agent_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-architect",
              conversationId: "group-stream",
              senderType: "agent",
              senderId: "architect",
              content: "先拆结构。",
              createdAt: "2026-05-26T10:00:01.000Z",
            },
            conversationUpdatedAt: "2026-05-26T10:00:01.000Z",
          },
        });
        onEvent({
          event: "error",
          payload: {
            conversationId: "group-stream",
            error: {
              message: "Critic 回复失败：模型超时",
            },
            conversationUpdatedAt: "2026-05-26T10:00:01.500Z",
          },
        });
        onEvent({
          event: "agent_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-writer",
              conversationId: "group-stream",
              senderType: "agent",
              senderId: "writer",
              content: "我来补充结论。",
              createdAt: "2026-05-26T10:00:02.000Z",
            },
            conversationUpdatedAt: "2026-05-26T10:00:02.000Z",
          },
        });
        onEvent({
          event: "done",
          payload: {
            conversationId: "group-stream",
            conversationUpdatedAt: "2026-05-26T10:00:02.000Z",
          },
        });
      }
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /流式群聊/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /流式群聊/ }));
    fireEvent.click(screen.getByRole("button", { name: "发送测试消息" }));

    await waitFor(() => {
      expect(screen.getByText("请开始群聊接力")).toBeInTheDocument();
      expect(screen.getByText("先拆结构。")).toBeInTheDocument();
      expect(screen.getByText("我来补充结论。")).toBeInTheDocument();
      expect(screen.getAllByText("Critic 回复失败：模型超时").length).toBeGreaterThan(0);
      expect(screen.getByText("部分成员回复失败")).toBeInTheDocument();
    });
  });

  it("群聊流在没有任何成员成功时显示群聊未完成回复提示", async () => {
    apiMocks.getConversations.mockResolvedValue([
      {
        id: "group-stream",
        type: "group",
        title: "流式群聊",
        memberIds: ["user", "architect", "critic"],
        modelConfigId: null,
        isDisabled: false,
        createdAt: "2026-05-26T00:00:00.000Z",
        updatedAt: "2026-05-26T00:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      },
    ]);
    apiMocks.getModelConfigs.mockResolvedValue([
      modelConfigs[0],
      {
        ...modelConfigs[1],
        status: "available",
        statusMessage: null,
      },
    ]);
    apiMocks.sendGroupMessageStream.mockImplementation(
      async (
        _payload: { conversationId: string; content: string },
        onEvent: (event: {
          event: string;
          payload: {
            conversationId: string;
            message?: {
              id: string;
              content: string;
              senderId: string;
              senderType: "user" | "agent";
              conversationId: string;
              createdAt: string;
            };
            error?: { message: string };
            conversationUpdatedAt?: string | null;
          };
        }) => void
      ) => {
        onEvent({
          event: "user_message",
          payload: {
            conversationId: "group-stream",
            message: {
              id: "msg-user",
              conversationId: "group-stream",
              senderType: "user",
              senderId: "user",
              content: "请开始群聊接力",
              createdAt: "2026-05-26T10:00:00.000Z",
            },
          },
        });
        onEvent({
          event: "error",
          payload: {
            conversationId: "group-stream",
            error: {
              message: "Architect 回复失败：模型超时",
            },
            conversationUpdatedAt: "2026-05-26T10:00:01.000Z",
          },
        });
        onEvent({
          event: "done",
          payload: {
            conversationId: "group-stream",
            conversationUpdatedAt: "2026-05-26T10:00:01.000Z",
          },
        });
      }
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /流式群聊/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /流式群聊/ }));
    fireEvent.click(screen.getByRole("button", { name: "发送测试消息" }));

    await waitFor(() => {
      expect(screen.getAllByText("Architect 回复失败：模型超时").length).toBeGreaterThan(0);
      expect(screen.getByText("群聊未完成回复")).toBeInTheDocument();
    });
  });
});
