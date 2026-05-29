import { useState } from "react";

import type { MessageUsagePayload } from "../../types/chat";

type Props = {
  usage?: MessageUsagePayload;
};

export function MessageUsageBadge({ usage }: Props) {
  const [isOpen, setIsOpen] = useState(false);

  if (!usage) {
    return null;
  }

  return (
    <div
      className="relative mt-2 w-full max-w-full"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={() => setIsOpen(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setIsOpen(false);
        }
      }}
    >
      <button
        type="button"
        aria-expanded={isOpen}
        aria-label="查看 Usage 明细"
        className="rounded-full border px-3 py-1.5 text-[11px] font-medium transition-colors"
        style={{
          background: "#F8F6F2",
          borderColor: "var(--border-light)",
          color: "var(--text-secondary)",
        }}
      >
        Usage · 总 {usage.totalTokens} tokens
      </button>
      <div
        className={`absolute left-0 top-full z-10 mt-2 min-w-[220px] rounded-2xl border px-3 py-2 text-xs shadow-lg transition-all ${
          isOpen ? "visible opacity-100" : "invisible opacity-0"
        }`}
        role="tooltip"
        aria-hidden={!isOpen}
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
          color: "var(--text-secondary)",
        }}
      >
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          <span>输入 {usage.promptTokens}</span>
          <span>输出 {usage.completionTokens}</span>
          {typeof usage.reasoningTokens === "number" ? (
            <span>思考 {usage.reasoningTokens}</span>
          ) : null}
          <span>总计 {usage.totalTokens}</span>
        </div>
      </div>
    </div>
  );
}
