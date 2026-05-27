import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Agent, Conversation, Message } from "../types/chat";

type Props = {
  agents: Agent[];
  conversations: Conversation[];
  messages: Message[];
  currentDirectAgentId: string | null;  // 当前单聊对应的 Agent（用于左侧入口高亮）
  activeConversationId: string;
  onSelectAgent: (id: string) => void;
  onSelectConversation: (id: string) => void;
  onCreateAgent: () => void;
  onCreateBlankConversation: () => void;
  onCreateGroup: () => void;
  onDeleteConversation?: (id: string) => void;
  onBulkDeleteConversations?: (ids: string[]) => void;
  onPinConversation?: (id: string, pinned: boolean) => void;
  onPinAgent?: (id: string, pinned: boolean) => void;
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function getLastMessagePreview(messages: Message[], conversationId: string): string | null {
  const convMessages = messages
    .filter((m) => m.conversationId === conversationId)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  if (convMessages.length === 0) return null;
  const last = convMessages[0];
  const prefix = last.senderType === "user" ? "我: " : "";
  const content = last.content.length > 24 ? last.content.slice(0, 24) + "…" : last.content;
  return prefix + content;
}

function MenuContainer({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose: () => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="absolute right-2 top-8 z-50 w-32 rounded-xl border py-1 shadow-lg"
      style={{
        background: "var(--bg-card)",
        borderColor: "var(--border-light)",
      }}
    >
      {children}
    </div>
  );
}

function ConversationMoreMenu({
  conversation,
  onDelete,
  onPin,
  onClose,
}: {
  conversation: Conversation;
  onDelete: (id: string) => void;
  onPin: (id: string, pinned: boolean) => void;
  onClose: () => void;
}) {
  return (
    <MenuContainer onClose={onClose}>
      <button
        onClick={() => {
          onPin(conversation.id, !conversation.pinned);
          onClose();
        }}
        className="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-[#F5F0E8]"
        style={{ color: "var(--text-secondary)" }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="17" x2="12" y2="3" />
          <path d="M5 10l7-7 7 7" />
          <line x1="19" y1="21" x2="5" y2="21" />
        </svg>
        {conversation.pinned ? "取消置顶" : "置顶"}
      </button>
      <div className="mx-2 my-1 h-px" style={{ background: "var(--border-light)" }} />
      <button
        onClick={() => {
          onDelete(conversation.id);
          onClose();
        }}
        className="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-red-50"
        style={{ color: "#C97B7B" }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
        删除
      </button>
    </MenuContainer>
  );
}

function AgentMoreMenu({
  agent,
  onPin,
  onClose,
}: {
  agent: Agent;
  onPin: (id: string, pinned: boolean) => void;
  onClose: () => void;
}) {
  return (
    <MenuContainer onClose={onClose}>
      <button
        onClick={() => {
          onPin(agent.id, !agent.pinned);
          onClose();
        }}
        className="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-[#F5F0E8]"
        style={{ color: "var(--text-secondary)" }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="17" x2="12" y2="3" />
          <path d="M5 10l7-7 7 7" />
          <line x1="19" y1="21" x2="5" y2="21" />
        </svg>
        {agent.pinned ? "取消置顶" : "置顶"}
      </button>
    </MenuContainer>
  );
}

function DeleteConfirmModal({
  mode,
  title,
  count,
  onConfirm,
  onCancel,
}: {
  mode: "single" | "bulk";
  title: string;
  count?: number;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onCancel} />
      <div
        className="relative w-full max-w-sm rounded-2xl border p-6 shadow-xl"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
        }}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-50">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C97B7B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>
          <div>
            <h3 className="font-display text-lg font-semibold text-[#2D2926]">确认删除会话</h3>
          </div>
        </div>
        <p className="text-sm leading-relaxed mb-6" style={{ color: "var(--text-secondary)" }}>
          {mode === "single"
            ? `确定要删除「${title}」吗？删除后消息记录将无法恢复。`
            : `确定要删除已选的 ${count ?? 0} 个会话吗？删除后消息记录将无法恢复。`}
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200"
            style={{
              background: "var(--bg-secondary)",
              borderColor: "var(--border-medium)",
              color: "var(--text-secondary)",
            }}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 rounded-xl px-4 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:shadow-md"
            style={{
              background: "#C97B7B",
              boxShadow: "0 4px 12px rgba(201, 123, 123, 0.3)",
            }}
          >
            删除
          </button>
        </div>
      </div>
    </div>
  );
}

type DeleteTarget =
  | { mode: "single"; title: string; ids: string[] }
  | { mode: "bulk"; title: string; ids: string[] };

export function ConversationSidebar({
  agents,
  conversations,
  messages,
  currentDirectAgentId,
  activeConversationId,
  onSelectAgent,
  onSelectConversation,
  onCreateAgent,
  onCreateBlankConversation,
  onCreateGroup,
  onDeleteConversation,
  onBulkDeleteConversations,
  onPinConversation,
  onPinAgent,
}: Props) {
  const [openConversationMenuId, setOpenConversationMenuId] = useState<string | null>(null);
  const [openAgentMenuId, setOpenAgentMenuId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [isManageMode, setIsManageMode] = useState(false);
  const [selectedConversationIds, setSelectedConversationIds] = useState<string[]>([]);

  function handleDeleteConversation(id: string) {
    const conv = conversations.find((c) => c.id === id);
    if (conv) {
      setDeleteTarget({ mode: "single", title: conv.title, ids: [conv.id] });
    }
  }

  function handleBulkDeleteRequest() {
    if (normalizedSelectedConversationIds.length === 0) return;
    setDeleteTarget({
      mode: "bulk",
      title: "",
      ids: normalizedSelectedConversationIds,
    });
  }

  function confirmDelete() {
    if (!deleteTarget) return;

    if (deleteTarget.mode === "single" && onDeleteConversation) {
      onDeleteConversation(deleteTarget.ids[0]);
    }

    if (deleteTarget.mode === "bulk" && onBulkDeleteConversations) {
      onBulkDeleteConversations(deleteTarget.ids);
      setSelectedConversationIds([]);
      setIsManageMode(false);
    }

    setDeleteTarget(null);
  }

  function toggleConversationSelection(id: string) {
    setSelectedConversationIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  }

  function exitManageMode() {
    setIsManageMode(false);
    setSelectedConversationIds([]);
  }

  const sortedConversations = useMemo(() => {
    return [...conversations].sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      if (a.pinned && b.pinned) {
        const leftPinnedAt = a.pinnedAt ? new Date(a.pinnedAt).getTime() : 0;
        const rightPinnedAt = b.pinnedAt ? new Date(b.pinnedAt).getTime() : 0;
        if (leftPinnedAt !== rightPinnedAt) return rightPinnedAt - leftPinnedAt;
      }
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });
  }, [conversations]);

  const sortedAgents = useMemo(() => {
    return agents
      .filter((agent) => !agent.isTemplate)
      .map((agent, index) => ({ agent, index }))
      .sort((left, right) => {
        if (!!left.agent.pinned !== !!right.agent.pinned) {
          return left.agent.pinned ? -1 : 1;
        }
        if (left.agent.pinned && right.agent.pinned) {
          const leftPinnedAt = left.agent.pinnedAt ? new Date(left.agent.pinnedAt).getTime() : 0;
          const rightPinnedAt = right.agent.pinnedAt ? new Date(right.agent.pinnedAt).getTime() : 0;
          if (leftPinnedAt !== rightPinnedAt) return rightPinnedAt - leftPinnedAt;
        }
        return left.index - right.index;
      })
      .map(({ agent }) => agent);
  }, [agents]);

  const normalizedSelectedConversationIds = selectedConversationIds.filter((id) =>
    conversations.some((conversation) => conversation.id === id)
  );

  return (
    <>
      <aside
        className="flex h-full w-64 flex-col border-r overflow-hidden flex-shrink-0"
        style={{
          background: "var(--bg-sidebar)",
          borderColor: "var(--border-light)",
        }}
      >
        {/* Logo */}
        <div
          className="flex min-h-[88px] flex-shrink-0 items-center gap-3 border-b px-4 py-4"
          style={{ borderColor: "var(--border-light)" }}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#2D2926]">
            <span className="font-display text-lg font-bold text-[#FAF7F2]">A</span>
          </div>
          <div>
            <h1 className="font-display text-base font-semibold text-[#2D2926]">Agent Hub</h1>
            <p className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>多 Agent 协作空间</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-4">
          {/* Agent 区域 */}
          <div className="px-4 mb-2">
            <p
              className="px-2 mb-2 text-[11px] font-medium uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}
            >
              Agent 入口
            </p>
            {sortedAgents.map((agent) => {
              const isHighlighted = currentDirectAgentId === agent.id;
              return (
                <div
                  key={agent.id}
                  className="relative mb-0.5"
                >
                  <button
                    onClick={() => onSelectAgent(agent.id)}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 pr-8 transition-all duration-200"
                    style={{
                      background: "transparent",
                      borderLeft: isHighlighted ? "3px solid " + agent.themeColor : "3px solid transparent",
                    }}
                  >
                    <div
                      className="flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white flex-shrink-0 transition-all duration-200 overflow-hidden"
                      style={{
                        background: agent.avatarImage ? "transparent" : agent.themeColor,
                        color: agent.avatarImage ? undefined : "#FFFFFF",
                        boxShadow: isHighlighted ? `0 2px 8px ${agent.themeColor}40` : "none",
                      }}
                    >
                      {agent.avatarImage ? (
                        <img src={agent.avatarImage} alt={agent.name} className="h-full w-full object-cover" />
                      ) : (
                        agent.avatar
                      )}
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {agent.pinned && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#D4A574" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="12" y1="17" x2="12" y2="3" />
                            <path d="M5 10l7-7 7 7" />
                          </svg>
                        )}
                        <p
                          className="text-sm font-medium truncate"
                          style={{ color: isHighlighted ? agent.themeColor : "#2D2926" }}
                        >
                          {agent.name}
                        </p>
                      </div>
                      <p className="text-[11px] truncate" style={{ color: "var(--text-tertiary)" }}>
                        {agent.roleSummary}
                      </p>
                    </div>
                    {isHighlighted && (
                      <div
                        className="h-2 w-2 rounded-full flex-shrink-0"
                        style={{ background: agent.themeColor }}
                      />
                    )}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenConversationMenuId(null);
                      setOpenAgentMenuId(openAgentMenuId === agent.id ? null : agent.id);
                    }}
                    className="absolute right-1.5 top-2 flex h-7 w-7 items-center justify-center rounded-lg opacity-40 hover:opacity-100 transition-opacity"
                    style={{ color: "var(--text-tertiary)" }}
                    title="Agent 操作"
                    aria-label="Agent 操作"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="5" r="1" />
                      <circle cx="12" cy="12" r="1" />
                      <circle cx="12" cy="19" r="1" />
                    </svg>
                  </button>
                  {openAgentMenuId === agent.id && onPinAgent && (
                    <AgentMoreMenu
                      agent={agent}
                      onPin={onPinAgent}
                      onClose={() => setOpenAgentMenuId(null)}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* 分隔线 */}
          <div className="mx-4 my-3 h-px" style={{ background: "var(--border-light)" }} />

          {/* 会话区域 */}
          <div className="px-4">
            <div className="flex items-center justify-between px-2 mb-2 gap-2">
              {isManageMode ? (
                <>
                  <p
                    className="text-[11px] font-medium uppercase tracking-wider"
                    style={{ color: "var(--text-muted)" }}
                  >
                    已选 {normalizedSelectedConversationIds.length} 项
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleBulkDeleteRequest}
                      disabled={normalizedSelectedConversationIds.length === 0}
                      className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-40"
                      style={{ color: "#C97B7B", background: "rgba(201, 123, 123, 0.08)" }}
                    >
                      删除
                    </button>
                    <button
                      onClick={exitManageMode}
                      className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors"
                      style={{ color: "var(--text-secondary)", background: "var(--bg-secondary)" }}
                    >
                      取消
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p
                    className="text-[11px] font-medium uppercase tracking-wider"
                    style={{ color: "var(--text-muted)" }}
                  >
                    会话
                  </p>
                  <div className="flex items-center gap-2">
                    {conversations.length > 0 && (
                      <button
                        onClick={() => {
                          setOpenConversationMenuId(null);
                          setOpenAgentMenuId(null);
                          setIsManageMode(true);
                        }}
                        className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors"
                        style={{ color: "var(--text-secondary)", background: "var(--bg-secondary)" }}
                      >
                        批量管理
                      </button>
                    )}
                    <span
                      className="text-[11px] font-medium"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {conversations.length}
                    </span>
                  </div>
                </>
              )}
            </div>

            {conversations.length === 0 && (
              <p className="px-2 py-3 text-xs text-center" style={{ color: "var(--text-muted)" }}>
                暂无会话
              </p>
            )}

            {sortedConversations.map((conv) => {
              const isActive = activeConversationId === conv.id;
              const isSelected = normalizedSelectedConversationIds.includes(conv.id);
              const lastPreview = getLastMessagePreview(messages, conv.id);
              const agent = conv.agentId ? agents.find((a) => a.id === conv.agentId) : null;

              return (
                <div
                  key={conv.id}
                  className="relative mb-0.5"
                >
                  <button
                    onClick={() => {
                      if (isManageMode) {
                        toggleConversationSelection(conv.id);
                        return;
                      }
                      onSelectConversation(conv.id);
                    }}
                    className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 pr-8 transition-all duration-200 text-left"
                    style={{
                      background: isManageMode
                        ? (isSelected ? "rgba(91, 123, 163, 0.10)" : "transparent")
                        : "transparent",
                      borderLeft: !isManageMode && isActive
                        ? `3px solid ${conv.type === "group" ? "#7BA89C" : agent?.themeColor || "#D4A574"}`
                        : "3px solid transparent",
                    }}
                  >
                    {isManageMode && (
                      <div className="pt-2">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => toggleConversationSelection(conv.id)}
                          aria-label={`选择会话 ${conv.title}`}
                        />
                      </div>
                    )}
                    {/* 头像 */}
                    <div className="flex-shrink-0 pt-0.5">
                      {conv.type === "group" ? (
                        <div
                          className="flex h-10 w-10 items-center justify-center rounded-xl"
                          style={{
                            background: isActive ? "#7BA89C" : "#E8F0ED",
                          }}
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: isActive ? "#FFFFFF" : "#7BA89C" }}>
                            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                            <circle cx="9" cy="7" r="4" />
                            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                          </svg>
                        </div>
                      ) : agent ? (
                        <div
                          className="flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white overflow-hidden"
                          style={{ background: agent.avatarImage ? "transparent" : agent.themeColor }}
                        >
                          {agent.avatarImage ? (
                            <img src={agent.avatarImage} alt={agent.name} className="h-full w-full object-cover" />
                          ) : (
                            agent.avatar
                          )}
                        </div>
                      ) : null}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          {conv.pinned && (
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#D4A574" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                              <line x1="12" y1="17" x2="12" y2="3" />
                              <path d="M5 10l7-7 7 7" />
                            </svg>
                          )}
                          <p
                            className="text-sm font-medium truncate"
                            style={{ color: isActive ? (conv.type === "group" ? "#7BA89C" : agent?.themeColor || "#2D2926") : "#2D2926" }}
                          >
                            {conv.title}
                          </p>
                        </div>
                        <span
                          className="text-[10px] flex-shrink-0"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {formatTime(conv.updatedAt)}
                        </span>
                      </div>
                      <p className="text-[11px] mt-0.5 truncate" style={{ color: "var(--text-tertiary)" }}>
                        {lastPreview || (conv.type === "group" ? `${conv.memberIds.length - 1} 位 Agent` : `与 ${agent?.name} 对话`)}
                      </p>
                    </div>
                  </button>

                  {!isManageMode && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenAgentMenuId(null);
                        setOpenConversationMenuId(openConversationMenuId === conv.id ? null : conv.id);
                      }}
                      className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-lg opacity-40 hover:opacity-100 transition-opacity"
                      style={{ color: "var(--text-tertiary)" }}
                      title="更多"
                      aria-label="更多操作"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="5" r="1" />
                        <circle cx="12" cy="12" r="1" />
                        <circle cx="12" cy="19" r="1" />
                      </svg>
                    </button>
                  )}

                  {!isManageMode && openConversationMenuId === conv.id && onPinConversation && (
                    <ConversationMoreMenu
                      conversation={conv}
                      onDelete={handleDeleteConversation}
                      onPin={onPinConversation}
                      onClose={() => setOpenConversationMenuId(null)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 底部发起群聊按钮 */}
        <div className="flex-shrink-0 border-t px-4 py-4" style={{ borderColor: "var(--border-light)" }}>
          <div className="grid gap-2">
            <button
              onClick={onCreateAgent}
              className="flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
              style={{
                background: "var(--bg-card)",
                borderColor: "var(--border-medium)",
                color: "var(--text-secondary)",
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
              新建 Agent
            </button>
            <button
              onClick={onCreateBlankConversation}
              className="flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
              style={{
                background: "var(--bg-card)",
                borderColor: "var(--border-medium)",
                color: "var(--text-secondary)",
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
              空白对话
            </button>
            <button
              onClick={onCreateGroup}
              className="flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
              style={{
                background: "var(--bg-card)",
                borderColor: "var(--border-medium)",
                color: "var(--text-secondary)",
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              发起群聊
            </button>
          </div>
        </div>
      </aside>

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <DeleteConfirmModal
          mode={deleteTarget.mode}
          title={deleteTarget.title}
          count={deleteTarget.ids.length}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
