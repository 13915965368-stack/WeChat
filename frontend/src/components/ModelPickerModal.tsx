import type { ModelConfig } from "../types/chat";
import { ModelCapabilityBadges } from "./ModelCapabilityBadges";
import { ModelStatusBadge } from "./ModelStatusBadge";

type Props = {
  isOpen: boolean;
  models: ModelConfig[];
  isSubmitting?: boolean;
  onClose: () => void;
  onSelect: (modelConfigId: string) => void;
};

export function ModelPickerModal({
  isOpen,
  models,
  isSubmitting = false,
  onClose,
  onSelect,
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-2xl rounded-[28px] border p-6 shadow-2xl"
        style={{ background: "var(--bg-card)", borderColor: "var(--border-light)" }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p
              className="text-[11px] font-medium uppercase tracking-[0.15em]"
              style={{ color: "var(--text-tertiary)" }}
            >
              空白对话
            </p>
            <h3 className="mt-1 text-2xl font-semibold text-[#2D2926]">选择模型</h3>
            <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>
              空白对话不带预设提示词，需要先选择一个可用模型。
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 transition-colors hover:bg-[#F5F0E8]"
            aria-label="关闭模型选择"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="mt-5 max-h-[420px] space-y-3 overflow-y-auto pr-1">
          {models.map((model) => (
            <button
              key={model.id}
              type="button"
              disabled={isSubmitting}
              onClick={() => onSelect(model.id)}
              className="w-full rounded-2xl border p-4 text-left transition-all hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
              style={{
                background: "var(--bg-secondary)",
                borderColor: "var(--border-light)",
              }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-[#2D2926]">
                    {model.displayName}
                  </div>
                  <div className="mt-1 truncate text-xs" style={{ color: "var(--text-secondary)" }}>
                    {model.provider} - {model.model}
                  </div>
                </div>
                <ModelStatusBadge status={model.status} />
              </div>
              <div className="mt-3 flex items-center justify-between gap-4">
                <ModelCapabilityBadges model={model} />
                <span className="text-xs font-medium" style={{ color: "#5B7BA3" }}>
                  以此模型开始
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
