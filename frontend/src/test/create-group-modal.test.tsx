import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CreateGroupModal } from "../components/CreateGroupModal";
import type { Agent, Conversation } from "../types/chat";

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
  {
    id: "critic",
    name: "Critic",
    roleSummary: "风险审查",
    styleSummary: "偏审慎",
    systemPrompt: "你是 Critic。",
    avatar: "C",
    themeColor: "#C97B7B",
    themeLight: "#F5DEDE",
    themeSoft: "#FCF5F5",
  },
];

const directConversation: Conversation = {
  id: "direct-architect",
  type: "direct",
  title: "与 Architect 的对话",
  memberIds: ["user", "architect"],
  agentId: "architect",
  createdAt: "2026-05-26T00:00:00.000Z",
  updatedAt: "2026-05-26T00:00:00.000Z",
};

describe("CreateGroupModal", () => {
  it("基于直聊发起群聊时展示真实历史迁移语义", () => {
    render(
      <CreateGroupModal
        isOpen
        onClose={vi.fn()}
        agents={agents}
        currentConversation={directConversation}
        mode="context"
        onCreateGroup={vi.fn()}
      />
    );

    expect(screen.getByText("可选择迁移当前直聊最近几轮历史，群内 Agent 会基于这段迁移记录按顺序回复")).toBeInTheDocument();
    expect(screen.getByText("至少选择 2 个 Agent。基于当前直聊发起时，默认会包含当前直聊的 Agent。")).toBeInTheDocument();
    expect(screen.getByLabelText("迁移历史轮次")).toHaveValue(1);
  });

  it("context 模式会默认选中当前直聊 Agent，并要求至少 2 名成员才能创建", async () => {
    const onCreateGroup = vi.fn();

    render(
      <CreateGroupModal
        isOpen
        onClose={vi.fn()}
        agents={agents}
        currentConversation={directConversation}
        mode="context"
        onCreateGroup={onCreateGroup}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /发起群聊 \(1 人\)/ })).toBeDisabled();
    });

    const submitButton = screen.getByRole("button", { name: /发起群聊 \(1 人\)/ });
    expect(submitButton).toBeDisabled();
    fireEvent.click(submitButton);
    expect(onCreateGroup).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Critic"));
    fireEvent.change(screen.getByLabelText("迁移历史轮次"), { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: /发起群聊 \(2 人\)/ }));

    expect(onCreateGroup).toHaveBeenCalledWith("新群聊", ["architect", "critic"], 6);
  });
});
