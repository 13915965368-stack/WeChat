import { useState, useEffect, useCallback, useRef } from "react";
import type { Agent, Conversation } from "../types/chat";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  agents: Agent[];
  currentConversation: Conversation | null;
  mode: "blank" | "context";
  onCreateGroup: (title: string, memberIds: string[], historyRounds: number) => void;
};

const DEFAULT_HISTORY_ROUNDS = 1;

export function CreateGroupModal({
  isOpen,
  onClose,
  agents,
  currentConversation,
  mode,
  onCreateGroup,
}: Props) {
  const [title, setTitle] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [historyRounds, setHistoryRounds] = useState(DEFAULT_HISTORY_ROUNDS);

  // 使用 ref 避免 effect 中同步 setState
  const isOpenRef = useRef(isOpen);
  const modeRef = useRef(mode);
  const currentConversationRef = useRef(currentConversation);

  useEffect(() => {
    isOpenRef.current = isOpen;
    modeRef.current = mode;
    currentConversationRef.current = currentConversation;
  });

  // 根据 mode 和当前会话计算默认选中
  const getDefaultSelectedIds = useCallback(() => {
    const currentMode = modeRef.current;
    const conv = currentConversationRef.current;
    if (currentMode === "context" && conv) {
      if (conv.type === "direct" && conv.agentId) {
        return [conv.agentId];
      }
      if (conv.type === "group") {
        return conv.memberIds.filter((id) => id !== "user");
      }
    }
    return [];
  }, []);

  // 每次打开时重置状态，使用 requestAnimationFrame 避免同步 setState
  useEffect(() => {
    if (isOpen) {
      const defaults = getDefaultSelectedIds();
      requestAnimationFrame(() => {
        setTitle("");
        setSelectedIds(defaults);
        setHistoryRounds(DEFAULT_HISTORY_ROUNDS);
      });
    }
  }, [isOpen, getDefaultSelectedIds]);

  // 全局 Escape 关闭
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") onClose();
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  function toggleAgent(id: string) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function handleCreate() {
    if (selectedIds.length < 2) {
      return;
    }
    const finalTitle = title.trim() || "新群聊";
    onCreateGroup(finalTitle, selectedIds, Math.max(1, Math.floor(historyRounds || DEFAULT_HISTORY_ROUNDS)));
    onClose();
  }

  const modalTitle = mode === "blank" ? "发起空白群聊" : "基于当前直聊发起群聊";
  const modalSubtitle = mode === "blank"
    ? "选择至少 2 个 Agent 创建一个新的群聊"
    : "可选择迁移当前直聊最近几轮历史，群内 Agent 会基于这段迁移记录按顺序回复";
  const memberHint = mode === "blank"
    ? "至少选择 2 个 Agent。"
    : "至少选择 2 个 Agent。基于当前直聊发起时，默认会包含当前直聊的 Agent。";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩 */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* 弹窗 */}
      <div
        className="relative w-full max-w-md rounded-2xl border p-6 shadow-xl"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
        }}
      >
        <h2 className="font-display text-xl font-semibold text-[#2D2926]">
          {modalTitle}
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {modalSubtitle}
        </p>

        {/* 群名称 */}
        <div className="mt-5">
          <label
            htmlFor="create-group-title"
            className="mb-1.5 block text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            群聊名称
          </label>
          <input
            id="create-group-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="给群聊起个名字..."
            className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-shadow focus:shadow-md"
            style={{
              background: "var(--bg-secondary)",
              borderColor: "var(--border-medium)",
              color: "var(--text-primary)",
            }}
          />
        </div>

        {mode === "context" ? (
          <div className="mt-5">
            <label
              htmlFor="create-group-history-rounds"
              className="mb-1.5 block text-sm font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              迁移历史轮次
            </label>
            <p className="mb-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
              1 轮表示最近一问一答。可按需填写更大的轮次数量。
            </p>
            <input
              id="create-group-history-rounds"
              type="number"
              min={1}
              step={1}
              value={historyRounds}
              onChange={(e) => {
                const nextValue = Number(e.target.value);
                if (Number.isNaN(nextValue)) {
                  setHistoryRounds(DEFAULT_HISTORY_ROUNDS);
                  return;
                }
                setHistoryRounds(Math.max(1, Math.floor(nextValue)));
              }}
              className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-shadow focus:shadow-md"
              style={{
                background: "var(--bg-secondary)",
                borderColor: "var(--border-medium)",
                color: "var(--text-primary)",
              }}
            />
          </div>
        ) : null}

        {/* Agent 选择 */}
        <div className="mt-5">
          <label
            className="mb-2 block text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            选择成员
          </label>
          <p className="mb-2 text-xs" style={{ color: "var(--text-tertiary)" }}>{memberHint}</p>
          <div className="space-y-2">
            {agents.filter((agent) => !agent.isTemplate).map((agent) => {
              const isSelected = selectedIds.includes(agent.id);
              return (
                <button
                  key={agent.id}
                  onClick={() => toggleAgent(agent.id)}
                  className="flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all duration-200"
                  style={{
                    background: isSelected ? agent.themeSoft : "var(--bg-secondary)",
                    borderColor: isSelected ? agent.themeColor : "var(--border-light)",
                  }}
                >
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
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: isSelected ? agent.themeColor : "#2D2926" }}>
                      {agent.name}
                    </p>
                    <p className="text-[11px] truncate" style={{ color: "var(--text-tertiary)" }}>
                      {agent.roleSummary}
                    </p>
                  </div>
                  <div
                    className="flex h-5 w-5 items-center justify-center rounded-md border"
                    style={{
                      borderColor: isSelected ? agent.themeColor : "var(--border-medium)",
                      background: isSelected ? agent.themeColor : "transparent",
                    }}
                  >
                    {isSelected && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 按钮 */}
        <div className="mt-6 flex gap-3">
          <button
            onClick={onClose}
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
            onClick={handleCreate}
            disabled={selectedIds.length < 2}
            className="flex-1 rounded-xl px-4 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:shadow-md disabled:opacity-40"
            style={{
              background: "#5B7BA3",
              boxShadow: "0 4px 12px rgba(91, 123, 163, 0.3)",
            }}
          >
            发起群聊 ({selectedIds.length} 人)
          </button>
        </div>
      </div>
    </div>
  );
}
