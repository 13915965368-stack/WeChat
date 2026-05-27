import type { Agent } from "../types/chat";

type Props = {
  agents: Agent[];
  activeAgentId: string;
  onSelect: (id: string) => void;
};

export function AgentRail({ agents, activeAgentId, onSelect }: Props) {
  return (
    <aside
      style={{ background: "var(--bg-sidebar)" }}
      className="flex h-full w-20 flex-col items-center gap-4 border-r py-6 overflow-y-auto"
    >
      {/* Logo */}
      <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-[#2D2926]">
        <span className="font-display text-lg font-bold text-[#FAF7F2]">A</span>
      </div>

      <div
        style={{ background: "var(--border-light)" }}
        className="mb-2 h-px w-10"
      />

      {agents.map((agent) => {
        const isActive = activeAgentId === agent.id;
        return (
          <button
            key={agent.id}
            onClick={() => onSelect(agent.id)}
            className="group relative flex flex-col items-center gap-1.5 transition-all duration-200"
            title={agent.name}
          >
            <div
              className="flex h-12 w-12 items-center justify-center rounded-2xl text-base font-semibold transition-all duration-200"
              style={{
                background: isActive ? agent.themeColor : agent.themeSoft,
                color: isActive ? "#FFFFFF" : agent.themeColor,
                boxShadow: isActive
                  ? `0 4px 16px ${agent.themeColor}40`
                  : "none",
                transform: isActive ? "scale(1.05)" : "scale(1)",
              }}
            >
              {agent.avatar}
            </div>
            <span
              className="text-[10px] font-medium transition-colors duration-200"
              style={{
                color: isActive
                  ? "var(--text-primary)"
                  : "var(--text-tertiary)",
              }}
            >
              {agent.name}
            </span>
            {isActive && (
              <div
                className="absolute -right-3 top-1/2 h-6 w-1 -translate-y-1/2 rounded-l-full"
                style={{ background: agent.themeColor }}
              />
            )}
          </button>
        );
      })}
    </aside>
  );
}
