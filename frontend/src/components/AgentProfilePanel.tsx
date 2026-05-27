import type { Agent } from "../types/chat";

type Props = {
  agent: Agent;
  onEdit: () => void;
  onNewConversation: () => void;
};

export function AgentProfilePanel({ agent, onEdit, onNewConversation }: Props) {
  return (
    <section
      className="flex h-full w-80 flex-shrink-0 flex-col border-r"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border-light)",
      }}
    >
      {/* 头部 */}
      <div
        className="flex min-h-[88px] flex-shrink-0 items-center border-b px-4 py-3"
        style={{ borderColor: "var(--border-light)" }}
      >
        <div className="flex w-full items-center gap-4">
          <div
            className="flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-2xl text-lg font-bold text-white shadow-sm"
            style={{ background: agent.avatarImage ? "transparent" : agent.themeColor }}
          >
            {agent.avatarImage ? (
              <img src={agent.avatarImage} alt={agent.name} className="h-full w-full object-cover" />
            ) : (
              agent.avatar
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-display text-xl font-semibold text-[#2D2926]">
                {agent.name}
              </h2>
              <button
                onClick={onEdit}
                className="flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-200 hover:scale-110"
                style={{
                  background: agent.themeSoft,
                  color: agent.themeColor,
                }}
                title="编辑人设"
                aria-label="编辑人设"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
            </div>
            <button
              onClick={onNewConversation}
              className="mt-1.5 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 hover:shadow-sm"
              style={{
                background: agent.themeSoft,
                color: agent.themeColor,
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              打开对话
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex min-h-full flex-col gap-5">
          {/* 角色定位 */}
          <div
            className="rounded-2xl border p-5"
            style={{
              background: "var(--bg-card)",
              borderColor: "var(--border-light)",
              boxShadow: "var(--shadow-soft)",
            }}
          >
            <div className="flex items-center gap-2">
              <div
                className="h-2 w-2 rounded-full"
                style={{ background: agent.themeColor }}
              />
              <span className="text-xs font-medium uppercase tracking-wider text-[#A39E99]">
                角色定位
              </span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-[#6B6560]">
              {agent.roleSummary}
            </p>
          </div>

          {/* 表达风格 */}
          <div
            className="rounded-2xl border p-5"
            style={{
              background: "var(--bg-card)",
              borderColor: "var(--border-light)",
              boxShadow: "var(--shadow-soft)",
            }}
          >
            <div className="flex items-center gap-2">
              <div
                className="h-2 w-2 rounded-full"
                style={{ background: agent.themeColor }}
              />
              <span className="text-xs font-medium uppercase tracking-wider text-[#A39E99]">
                表达风格
              </span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-[#6B6560]">
              {agent.styleSummary}
            </p>
          </div>

          {/* 记忆区域占位 */}
          <div
            className="mt-auto rounded-2xl border border-dashed p-5"
            style={{
              background: agent.themeSoft,
              borderColor: agent.themeLight,
            }}
          >
            <div className="flex items-center gap-2">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke={agent.themeColor}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
              <span
                className="text-xs font-medium"
                style={{ color: agent.themeColor }}
              >
                正式记忆
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed" style={{ color: "#A39E99" }}>
              群聊中沉淀的内容可以手动提升到这里，影响该 Agent 的长期行为。此功能将在后续版本中开放。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
