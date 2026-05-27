import type { Agent, Conversation } from "../types/chat";

type Props = {
  conversation: Conversation;
  agents: Agent[];
  activeAgentId: string;
  onSelectAgent: (id: string) => void;
};

export function GroupMemberPanel({ conversation, agents, activeAgentId, onSelectAgent }: Props) {
  const memberAgents = agents.filter((a) => conversation.memberIds.includes(a.id));

  return (
    <aside
      className="flex w-64 flex-col border-r h-full overflow-hidden flex-shrink-0"
      style={{
        background: "var(--bg-sidebar)",
        borderColor: "var(--border-light)",
      }}
    >
      {/* 群信息头部 */}
      <div
        className="flex min-h-[88px] flex-shrink-0 flex-col justify-center border-b px-4 py-4"
        style={{ borderColor: "var(--border-light)" }}
      >
        <div className="flex items-center gap-2 mb-2">
          <div
            className="h-2 w-2 rounded-full"
            style={{ background: "#7BA89C" }}
          />
          <span
            className="text-[11px] font-medium uppercase tracking-[0.15em]"
            style={{ color: "var(--text-tertiary)" }}
          >
            群聊协作
          </span>
        </div>
        <h2 className="font-display text-lg font-semibold text-[#2D2926]">
          {conversation.title}
        </h2>
        <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          {memberAgents.length + 1} 位成员
        </p>
      </div>

      {/* 成员列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p
          className="mb-3 px-2 text-[11px] font-medium uppercase tracking-wider"
          style={{ color: "var(--text-muted)" }}
        >
          群成员
        </p>

        {/* 用户自己 */}
        <div className="mb-1 flex items-center gap-3 rounded-xl px-3 py-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#5B7BA3] text-sm font-bold text-white">
            我
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[#2D2926]">我</p>
            <p className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
              发起者
            </p>
          </div>
        </div>

        {/* Agent 成员 */}
        {memberAgents.map((agent) => {
          const isActive = activeAgentId === agent.id;
          return (
            <button
              key={agent.id}
              onClick={() => onSelectAgent(agent.id)}
              className="mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200"
              style={{
                background: isActive ? agent.themeSoft : "transparent",
              }}
            >
              <div
                className="flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold text-white overflow-hidden"
                style={{ background: agent.avatarImage ? "transparent" : agent.themeColor }}
              >
                {agent.avatarImage ? (
                  <img src={agent.avatarImage} alt={agent.name} className="h-full w-full object-cover" />
                ) : (
                  agent.avatar
                )}
              </div>
              <div className="flex-1 text-left min-w-0">
                <p className="text-sm font-medium" style={{ color: isActive ? agent.themeColor : "#2D2926" }}>
                  {agent.name}
                </p>
                <p className="text-[11px] truncate" style={{ color: "var(--text-tertiary)" }}>
                  {agent.roleSummary}
                </p>
              </div>
              {isActive && (
                <div
                  className="h-2 w-2 rounded-full flex-shrink-0"
                  style={{ background: agent.themeColor }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* 群档案入口 */}
      <div
        className="border-t px-4 py-4"
        style={{ borderColor: "var(--border-light)" }}
      >
        <button
          className="flex w-full items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
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
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          查看群档案
        </button>
      </div>
    </aside>
  );
}
