import type { ModelConfig } from "../types/chat";
import { ModelCapabilityBadges } from "./ModelCapabilityBadges";
import { ModelStatusBadge } from "./ModelStatusBadge";

type Props = {
  modelConfigs: ModelConfig[];
  isLoading: boolean;
  error?: string | null;
  onCreate: () => void;
  onEdit: (modelConfig: ModelConfig) => void;
  onValidate: (modelConfigId: string) => void;
  onDelete: (modelConfig: ModelConfig) => void;
};

export function ModelConfigTable({
  modelConfigs,
  isLoading,
  error,
  onCreate,
  onEdit,
  onValidate,
  onDelete,
}: Props) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[#2D2926]">模型管理</h3>
          <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
            配置 API key，添加可用模型，预置模型默认使用稳定版本。
          </p>
        </div>
        <button
          onClick={onCreate}
          className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:shadow-md whitespace-nowrap shrink-0"
          style={{ background: "#5B7BA3", boxShadow: "0 4px 12px rgba(91, 123, 163, 0.22)" }}
        >
          <span className="text-lg leading-none">+</span>
          添加模型
        </button>
      </div>

      {error ? (
        <div
          className="mt-4 rounded-xl border px-4 py-3 text-sm"
          style={{
            background: "#FFF5F5",
            borderColor: "#F3C4C4",
            color: "#A63A3A",
          }}
        >
          {error}
        </div>
      ) : null}

      <div
        className="mt-4 min-h-0 flex-1 overflow-hidden rounded-2xl border"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
          boxShadow: "var(--shadow-soft)",
        }}
      >
        <div
          className="grid grid-cols-[1.4fr_1.3fr_0.8fr_1.4fr_0.8fr_1fr] items-center gap-4 border-b px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.14em]"
          style={{
            background: "var(--bg-secondary)",
            borderColor: "var(--border-light)",
            color: "var(--text-tertiary)",
          }}
        >
          <span>模型</span>
          <span>提供商</span>
          <span>状态</span>
          <span>能力</span>
          <span>上下文</span>
          <span>操作</span>
        </div>

        <div className="max-h-[calc(100vh-220px)] overflow-y-auto">
          {isLoading ? (
            <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
              正在读取模型配置...
            </div>
          ) : modelConfigs.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-5 py-10 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl" style={{ background: "var(--bg-secondary)" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-muted)" }}>
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="12" y1="8" x2="12" y2="16" />
                  <line x1="8" y1="12" x2="16" y2="12" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[#2D2926]">还没有模型配置</p>
              <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                添加一个模型后，Agent 才能绑定并使用它。
              </p>
              <button
                onClick={onCreate}
                className="mt-4 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:shadow-md whitespace-nowrap shrink-0"
                style={{ background: "#5B7BA3", boxShadow: "0 4px 12px rgba(91, 123, 163, 0.22)" }}
              >
                <span className="text-lg leading-none">+</span>
                添加首个模型
              </button>
            </div>
          ) : (
            modelConfigs.map((modelConfig) => (
              <div
                key={modelConfig.id}
                className="grid grid-cols-[1.4fr_1.3fr_0.8fr_1.4fr_0.8fr_1fr] items-start gap-4 border-b px-5 py-4 last:border-b-0"
                style={{ borderColor: "var(--border-light)" }}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-[#2D2926]">
                    {modelConfig.displayName}
                  </div>
                  {modelConfig.statusMessage ? (
                    <p
                      className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap break-words text-xs"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {modelConfig.statusMessage}
                    </p>
                  ) : null}
                </div>

                <div className="min-w-0">
                  <div className="truncate text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                    {modelConfig.provider} - {modelConfig.model}
                  </div>
                  <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                    {modelConfig.useFullUrl ? "完整 URL" : modelConfig.baseUrl}
                  </p>
                </div>

                <div>
                  <ModelStatusBadge status={modelConfig.status} />
                </div>

                <ModelCapabilityBadges model={modelConfig} />

                <div className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  {modelConfig.contextWindowInput
                    ? `${Math.round(modelConfig.contextWindowInput / 1000)}K`
                    : "未声明"}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => onEdit(modelConfig)}
                    className="rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => onValidate(modelConfig.id)}
                    className="rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
                    style={{
                      background: "#EEF4FA",
                      borderColor: "#D8E4F1",
                      color: "#5B7BA3",
                    }}
                  >
                    重新校验
                  </button>
                  <button
                    onClick={() => onDelete(modelConfig)}
                    className="rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
                    style={{
                      background: "#FFF5F5",
                      borderColor: "#F3D8D8",
                      color: "#B85E5E",
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
