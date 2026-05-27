import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConversationSidebar } from "../components/ConversationSidebar";
import type { Agent, Conversation, Message } from "../types/chat";

const agents: Agent[] = [
  {
    id: "architect",
    name: "Architect",
    roleSummary: "擅长结构化拆解",
    styleSummary: "偏框架化",
    systemPrompt: "你是 Architect。",
    avatar: "A",
    themeColor: "#D4A574",
    themeLight: "#F5E6D3",
    themeSoft: "#FAF3EC",
    pinned: false,
    pinnedAt: null,
  },
  {
    id: "critic",
    name: "Critic",
    roleSummary: "擅长找风险",
    styleSummary: "偏审慎",
    systemPrompt: "你是 Critic。",
    avatar: "C",
    themeColor: "#C97B7B",
    themeLight: "#F5DEDE",
    themeSoft: "#FCF5F5",
    pinned: true,
    pinnedAt: "2026-05-18T10:00:00.000Z",
  },
];

const conversations: Conversation[] = [
  {
    id: "conv-pinned",
    type: "group",
    title: "已置顶群聊",
    memberIds: ["user", "architect", "critic"],
    createdAt: "2026-05-18T08:00:00.000Z",
    updatedAt: "2026-05-18T09:00:00.000Z",
    pinned: true,
    pinnedAt: "2026-05-18T10:00:00.000Z",
  },
  {
    id: "conv-normal",
    type: "direct",
    title: "普通单聊",
    memberIds: ["user", "architect"],
    agentId: "architect",
    createdAt: "2026-05-18T07:00:00.000Z",
    updatedAt: "2026-05-18T08:30:00.000Z",
    pinned: false,
    pinnedAt: null,
  },
];

const messages: Message[] = [
  {
    id: "msg-1",
    conversationId: "conv-pinned",
    senderType: "user",
    senderId: "user",
    content: "已置顶群聊的最后一条消息",
    createdAt: "2026-05-18T09:00:00.000Z",
  },
];

function renderSidebar() {
  return render(
    <ConversationSidebar
      agents={agents}
      conversations={conversations}
      messages={messages}
      currentDirectAgentId="architect"
      activeConversationId="conv-pinned"
      onSelectAgent={vi.fn()}
      onSelectConversation={vi.fn()}
      onCreateAgent={vi.fn()}
      onCreateBlankConversation={vi.fn()}
      onCreateGroup={vi.fn()}
      onDeleteConversation={vi.fn()}
      onBulkDeleteConversations={vi.fn()}
      onPinConversation={vi.fn()}
      onPinAgent={vi.fn()}
    />
  );
}

describe("ConversationSidebar", () => {
  it("已置顶会话菜单显示取消置顶", () => {
    renderSidebar();

    fireEvent.click(screen.getAllByLabelText("更多操作")[0]);

    expect(screen.getByText("取消置顶")).toBeInTheDocument();
  });

  it("未置顶 Agent 菜单显示置顶", () => {
    renderSidebar();

    fireEvent.click(screen.getAllByLabelText("Agent 操作")[1]);

    expect(screen.getByRole("button", { name: "置顶" })).toBeInTheDocument();
  });

  it("批量管理模式支持勾选并弹出批量删除确认", () => {
    renderSidebar();

    fireEvent.click(screen.getByText("批量管理"));
    fireEvent.click(screen.getByLabelText("选择会话 已置顶群聊"));
    fireEvent.click(screen.getByText("删除"));

    expect(screen.getByRole("heading", { name: "确认删除会话" })).toBeInTheDocument();
    expect(
      screen.getByText("确定要删除已选的 1 个会话吗？删除后消息记录将无法恢复。")
    ).toBeInTheDocument();
  });

  it("底部提供新建 Agent 入口", () => {
    const onCreateAgent = vi.fn();

    render(
      <ConversationSidebar
        agents={agents}
        conversations={conversations}
        messages={messages}
        currentDirectAgentId="architect"
        activeConversationId="conv-pinned"
        onSelectAgent={vi.fn()}
        onSelectConversation={vi.fn()}
        onCreateAgent={onCreateAgent}
        onCreateBlankConversation={vi.fn()}
        onCreateGroup={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "新建 Agent" }));

    expect(onCreateAgent).toHaveBeenCalled();
  });
});
