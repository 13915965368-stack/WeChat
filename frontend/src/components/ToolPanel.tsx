import { useState } from "react";

type Props = {
  activeTool: string | null;
  onSelectTool: (toolId: string) => void;
};

export function ToolPanel({ activeTool, onSelectTool }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  const tools = [
    {
      id: "search",
      name: "知识检索",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      ),
      description: "搜索知识库",
    },
    {
      id: "memory",
      name: "记忆管理",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      ),
      description: "管理长期记忆",
    },
    {
      id: "analytics",
      name: "数据分析",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      ),
      description: "查看对话统计",
    },
    {
      id: "settings",
      name: "设置",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      ),
      description: "系统设置",
    },
  ];

  return (
    <aside
      className="flex h-full flex-col border-l transition-all duration-300"
      style={{
        width: isExpanded ? "240px" : "48px",
        background: "var(--bg-sidebar)",
        borderColor: "var(--border-light)",
      }}
    >
      {/* 展开/收起按钮 */}
      <div
        className="flex min-h-[88px] flex-shrink-0 items-center justify-center border-b px-2 py-4"
        style={{ borderColor: "var(--border-light)" }}
      >
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 hover:scale-105"
          style={{
            background: isExpanded ? "var(--bg-card)" : "transparent",
            border: isExpanded ? "1px solid var(--border-medium)" : "none",
          }}
          title={isExpanded ? "收起工具栏" : "展开工具栏"}
          aria-label={isExpanded ? "收起工具栏" : "展开工具栏"}
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
            style={{
              color: "var(--text-secondary)",
              transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.3s",
            }}
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
      </div>

      {/* 工具列表 */}
      <div className="flex-1 overflow-y-auto py-2">
        {tools.map((tool) => (
          <button
            key={tool.id}
            onClick={() => onSelectTool(activeTool === tool.id ? "" : tool.id)}
            className="flex w-full items-center gap-2 px-2 py-2 transition-all duration-200 hover:bg-white/50"
            style={{
              background: activeTool === tool.id ? "rgba(91, 123, 163, 0.1)" : "transparent",
            }}
            title={!isExpanded ? tool.name : undefined}
            aria-label={tool.name}
          >
            <div
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
              style={{
                background: activeTool === tool.id ? "#5B7BA3" : "var(--bg-card)",
                color: activeTool === tool.id ? "#FFFFFF" : "var(--text-secondary)",
                boxShadow: activeTool === tool.id ? "0 2px 8px rgba(91, 123, 163, 0.3)" : "none",
              }}
            >
              {tool.icon}
            </div>
            {isExpanded && (
              <div className="min-w-0 text-left">
                <p
                  className="text-sm font-medium"
                  style={{
                    color: activeTool === tool.id ? "#5B7BA3" : "var(--text-primary)",
                  }}
                >
                  {tool.name}
                </p>
                <p className="text-[11px] truncate" style={{ color: "var(--text-tertiary)" }}>
                  {tool.description}
                </p>
              </div>
            )}
          </button>
        ))}
      </div>

      {/* 底部信息 */}
      {isExpanded && (
        <div className="border-t p-3" style={{ borderColor: "var(--border-light)" }}>
          <p className="text-center text-[10px]" style={{ color: "var(--text-muted)" }}>
            工具面板 v1.0
          </p>
        </div>
      )}
    </aside>
  );
}
