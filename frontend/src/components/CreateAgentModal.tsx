import { useEffect, useMemo, useState } from "react";
import type { ModelConfig } from "../types/chat";

type CreateAgentPayload = {
  name: string;
  roleSummary: string;
  styleSummary: string;
  systemPrompt: string;
  modelConfigId: string | null;
};

type Props = {
  isOpen: boolean;
  isSubmitting?: boolean;
  modelConfigs: ModelConfig[];
  onClose: () => void;
  onSubmit: (payload: CreateAgentPayload) => Promise<void> | void;
};

export function CreateAgentModal({
  isOpen,
  isSubmitting = false,
  modelConfigs,
  onClose,
  onSubmit,
}: Props) {
  const [name, setName] = useState("");
  const [roleSummary, setRoleSummary] = useState("");
  const [styleSummary, setStyleSummary] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [modelConfigId, setModelConfigId] = useState("");

  const availableModels = useMemo(
    () => modelConfigs.filter((modelConfig) => modelConfig.status === "available"),
    [modelConfigs]
  );

  useEffect(() => {
    if (!isOpen) return;
    setName("");
    setRoleSummary("");
    setStyleSummary("");
    setSystemPrompt("");
    setModelConfigId("");
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[82] flex items-center justify-center px-4 py-8">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      <div
        className="relative max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-[28px] border shadow-2xl"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
        }}
      >
        <div className="flex items-center justify-between border-b px-6 py-5" style={{ borderColor: "var(--border-light)" }}>
          <div>
            <h3 className="text-2xl font-semibold text-[#2D2926]">新建 Agent</h3>
            <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>
              先在前端本地创建一个可编辑 Agent，后续接真后端时再切换底层实现。
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 transition-colors hover:bg-[#F5F0E8]"
            aria-label="关闭新建 Agent 弹窗"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="max-h-[calc(90vh-88px)] overflow-y-auto px-6 py-5">
          <div className="grid gap-4">
            <label className="text-sm">
              <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                名称
              </span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：Researcher"
                className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-light)",
                  color: "var(--text-primary)",
                }}
              />
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                角色定位
              </span>
              <input
                value={roleSummary}
                onChange={(event) => setRoleSummary(event.target.value)}
                placeholder="例如：擅长资料查找与信息归纳"
                className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-light)",
                  color: "var(--text-primary)",
                }}
              />
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                表达风格
              </span>
              <input
                value={styleSummary}
                onChange={(event) => setStyleSummary(event.target.value)}
                placeholder="例如：偏简洁、偏结论先行"
                className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-light)",
                  color: "var(--text-primary)",
                }}
              />
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                系统提示词
              </span>
              <textarea
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
                rows={5}
                placeholder="可以为空；留空时就是偏纯净 Agent。"
                className="w-full resize-none rounded-2xl border px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-light)",
                  color: "var(--text-primary)",
                }}
              />
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                初始模型绑定
              </span>
              <select
                value={modelConfigId}
                onChange={(event) => setModelConfigId(event.target.value)}
                className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-light)",
                  color: "var(--text-primary)",
                }}
              >
                <option value="">暂不绑定模型</option>
                {availableModels.map((modelConfig) => (
                  <option key={modelConfig.id} value={modelConfig.id}>
                    {modelConfig.provider} - {modelConfig.model}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                当前只展示本地已校验通过的模型配置。
              </p>
            </label>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              onClick={onClose}
              className="rounded-xl border px-4 py-2.5 text-sm font-medium"
              style={{
                background: "var(--bg-secondary)",
                borderColor: "var(--border-medium)",
                color: "var(--text-secondary)",
              }}
            >
              取消
            </button>
            <button
              onClick={() => {
                void onSubmit({
                  name,
                  roleSummary,
                  styleSummary,
                  systemPrompt,
                  modelConfigId: modelConfigId || null,
                });
              }}
              disabled={isSubmitting || !name.trim() || !roleSummary.trim() || !styleSummary.trim()}
              className="rounded-xl px-5 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:shadow-md disabled:opacity-50"
              style={{
                background: "#5B7BA3",
                boxShadow: "0 8px 24px rgba(91, 123, 163, 0.22)",
              }}
            >
              {isSubmitting ? "创建中..." : "创建 Agent"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export type { CreateAgentPayload };
