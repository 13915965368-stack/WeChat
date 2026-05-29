import { useState } from "react";

import type { MessageThinkingPayload } from "../../types/chat";

type Props = {
  thinking?: MessageThinkingPayload;
};

export function ThinkingCollapse({ thinking }: Props) {
  if (!thinking?.available || !thinking.content.trim()) {
    return null;
  }

  const [isCollapsed, setIsCollapsed] = useState(thinking.defaultCollapsed);
  const displayContent = thinking.content
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (!displayContent) {
    return null;
  }

  return (
    <div
      className="mt-2 w-full rounded-2xl border px-3 py-3"
      style={{
        background: "#F8F6F2",
        borderColor: "var(--border-light)",
      }}
    >
      <button
        type="button"
        onClick={() => setIsCollapsed((prev) => !prev)}
        className="flex w-full items-center justify-between gap-3 text-left"
        aria-expanded={!isCollapsed}
        aria-label={isCollapsed ? "展开思考过程" : "收起思考过程"}
      >
        <span className="text-xs font-medium uppercase tracking-[0.12em]" style={{ color: "var(--text-tertiary)" }}>
          思考过程
        </span>
        <span className="text-xs font-medium" style={{ color: "#5B7BA3" }}>
          {isCollapsed ? "展开" : "收起"}
        </span>
      </button>

      {!isCollapsed ? (
        <pre
          className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed [overflow-wrap:anywhere]"
          style={{ color: "var(--text-secondary)", fontFamily: "inherit" }}
        >
          {displayContent}
        </pre>
      ) : null}
    </div>
  );
}
