import { useState } from "react";
import type { ToolCallPayload, ToolResultPayload } from "../types/chat";

type ToolActivity = {
  toolCallId: string;
  toolName: string;
  agentName: string;
  status: "calling" | "done";
  resultPreview?: string;
};

type Props = {
  activeTool: string | null;
  onSelectTool: (toolId: string) => void;
  toolActivities?: ToolActivity[];
};

export function ToolPanel({ activeTool, onSelectTool, toolActivities = [] }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  const tools = [
    {
      id: "search",
      name: "网页搜索",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      ),
      description: "搜索互联网获取最新信息",
    },
    {
      id: "knowledge",
      name: "知识检索",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      ),
      description: "从知识库检索信息",
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

      {/* 工具调用活动 */}
      {toolActivities.length > 0 && (
        <div className="border-t py-2" style={{ borderColor: "var(--border-light)" }}>
          {isExpanded && (
            <p className="mb-1 px-3 text-[11px] font-medium" style={{ color: "var(--text-tertiary)" }}>
              工具调用
            </p>
          )}
          {toolActivities.slice(-3).map((activity) => (
            <div
              key={activity.toolCallId}
              className="flex items-center gap-2 px-2 py-1"
              title={isExpanded ? undefined : `${activity.agentName}: ${activity.toolName}`}
            >
              <div
                className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded"
                style={{
                  background: activity.status === "calling"
                    ? "rgba(59, 130, 246, 0.1)"
                    : "rgba(34, 197, 94, 0.1)",
                  color: activity.status === "calling" ? "#3B82F6" : "#22C55E",
                }}
              >
                {activity.status === "calling" ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              {isExpanded && (
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] truncate" style={{ color: "var(--text-primary)" }}>
                    {activity.agentName}: {activity.toolName}
                  </p>
                  {activity.status === "calling" && (
                    <p className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                      正在执行...
                    </p>
                  )}
                  {activity.status === "done" && activity.resultPreview && (
                    <p className="text-[10px] truncate" style={{ color: "var(--text-tertiary)" }}>
                      {activity.resultPreview.slice(0, 60)}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 底部信息 */}
      {isExpanded && (
        <div className="border-t p-3" style={{ borderColor: "var(--border-light)" }}>
          <p className="text-center text-[10px]" style={{ color: "var(--text-muted)" }}>
            工具面板 v2.0
          </p>
        </div>
      )}
    </aside>
  );
}

export function useToolActivities() {
  const [activities, setActivities] = useState<ToolActivity[]>([]);

  function handleToolCall(payload: ToolCallPayload) {
    setActivities((prev) => [
      ...prev,
      {
        toolCallId: payload.toolCallId,
        toolName: payload.toolName,
        agentName: payload.agentName,
        status: "calling" as const,
      },
    ]);
  }

  function handleToolResult(payload: ToolResultPayload) {
    setActivities((prev) =>
      prev.map((a) =>
        a.toolCallId === payload.toolCallId
          ? { ...a, status: "done" as const, resultPreview: payload.resultPreview }
          : a
      )
    );
  }

  function clearActivities() {
    setActivities([]);
  }

  return { activities, handleToolCall, handleToolResult, clearActivities };
}
