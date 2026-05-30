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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold text-[#2D2926]">模型管理</h3>
          <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
            配置 API key，添加可用模型，预置模型默认使用稳定版本。
          </p>
        </div>
        <button
          onClick={onCreate}
          className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium text-white transition-shadow duration-200 hover:shadow-md"
          style={{ background: "#5B7BA3", boxShadow: "0 4px 12px rgba(91, 123, 163, 0.22)" }}
        >
          <span aria-hidden="true" className="text-lg leading-none">+</span>
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
        <div className="max-h-[calc(100vh-240px)] overflow-y-auto p-4">
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
                className="mt-4 inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium text-white transition-shadow duration-200 hover:shadow-md"
                style={{ background: "#5B7BA3", boxShadow: "0 4px 12px rgba(91, 123, 163, 0.22)" }}
              >
                <span aria-hidden="true" className="text-lg leading-none">+</span>
                添加首个模型
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {modelConfigs.map((modelConfig) => (
                <article
                  key={modelConfig.id}
                  className="rounded-2xl border px-4 py-4"
                  style={{
                    background: "var(--bg-card)",
                    borderColor: "var(--border-light)",
                    boxShadow: "0 8px 20px rgba(45, 41, 38, 0.04)",
                  }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <h4 className="break-words text-sm font-semibold text-[#2D2926]">
                        {modelConfig.displayName}
                      </h4>
                      <p className="mt-1 break-words text-sm" style={{ color: "var(--text-secondary)" }}>
                        {modelConfig.provider} - {modelConfig.model}
                      </p>
                    </div>
                    <div className="shrink-0">
                      <ModelStatusBadge status={modelConfig.status} />
                    </div>
                  </div>

                  {modelConfig.statusMessage ? (
                    <p
                      className="mt-3 whitespace-pre-wrap break-words rounded-xl border px-3 py-2 text-xs"
                      style={{
                        background: "var(--bg-secondary)",
                        borderColor: "var(--border-light)",
                        color: "var(--text-tertiary)",
                      }}
                    >
                      {modelConfig.statusMessage}
                    </p>
                  ) : null}

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="min-w-0">
                      <p
                        className="text-[11px] font-semibold uppercase tracking-[0.12em]"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        地址
                      </p>
                      <p className="mt-1 break-all text-xs" style={{ color: "var(--text-secondary)" }}>
                        {modelConfig.useFullUrl ? "完整 URL" : modelConfig.baseUrl}
                      </p>
                    </div>
                    <div className="min-w-0">
                      <p
                        className="text-[11px] font-semibold uppercase tracking-[0.12em]"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        输入上下文
                      </p>
                      <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                        {modelConfig.contextWindowInput
                          ? `${Math.round(modelConfig.contextWindowInput / 1000)}K`
                          : "未声明"}
                      </p>
                    </div>
                    <div className="min-w-0 sm:col-span-2">
                      <p
                        className="text-[11px] font-semibold uppercase tracking-[0.12em]"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        能力
                      </p>
                      <div className="mt-2">
                        <ModelCapabilityBadges model={modelConfig} />
                      </div>
                    </div>
                  </div>

                  <div
                    className="mt-4 flex flex-wrap items-center gap-2 border-t pt-4"
                    style={{ borderColor: "var(--border-light)" }}
                  >
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
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
