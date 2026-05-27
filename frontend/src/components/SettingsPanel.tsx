import { useMemo, useState } from "react";
import type { ModelConfig, ModelConfigPayload } from "../types/chat";
import { ModelConfigModal } from "./ModelConfigModal";
import { ModelConfigTable } from "./ModelConfigTable";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  modelConfigs: ModelConfig[];
  isLoading: boolean;
  error?: string | null;
  onCreateModelConfig: (payload: ModelConfigPayload) => Promise<void> | void;
  onUpdateModelConfig: (id: string, payload: Partial<ModelConfigPayload>) => Promise<void> | void;
  onValidateModelConfig: (id: string) => Promise<void> | void;
  onDeleteModelConfig: (id: string) => Promise<void> | void;
  impactedAgentsByModelConfigId?: Record<string, string[]>;
};

type DeleteState = {
  id: string;
  name: string;
  impactedAgents: string[];
};

function DeleteModelConfigModal({
  modelConfigName,
  impactedAgents,
  isDeleting,
  onCancel,
  onConfirm,
}: {
  modelConfigName: string;
  impactedAgents: string[];
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onCancel} />
      <div
        className="relative w-full max-w-md rounded-[28px] border p-6 shadow-2xl"
        style={{ background: "var(--bg-card)", borderColor: "var(--border-light)" }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-red-50 text-[#B85E5E]">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18" />
              <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[#2D2926]">确认删除模型</h3>
            <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>
              删除后不会删除 Agent 和历史对话，但相关 Agent 会进入模型失效状态。
            </p>
          </div>
        </div>

        <div className="mt-5 rounded-2xl border px-4 py-3" style={{ background: "var(--bg-secondary)", borderColor: "var(--border-light)" }}>
          <p className="text-sm font-medium text-[#2D2926]">{modelConfigName}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
            将影响 {impactedAgents.length} 个 Agent
          </p>
          {impactedAgents.length > 0 ? (
            <ul className="mt-3 space-y-1 text-xs" style={{ color: "var(--text-secondary)" }}>
              {impactedAgents.slice(0, 4).map((agentName) => (
                <li key={agentName}>• {agentName}</li>
              ))}
              {impactedAgents.length > 4 ? <li>• 还有 {impactedAgents.length - 4} 个 Agent</li> : null}
            </ul>
          ) : null}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
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
            onClick={onConfirm}
            disabled={isDeleting}
            className="rounded-xl px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "#B85E5E" }}
          >
            {isDeleting ? "删除中..." : "确认删除"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function SettingsPanel({
  isOpen,
  onClose,
  modelConfigs,
  isLoading,
  error,
  onCreateModelConfig,
  onUpdateModelConfig,
  onValidateModelConfig,
  onDeleteModelConfig,
  impactedAgentsByModelConfigId = {},
}: Props) {
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingModel, setDeletingModel] = useState<DeleteState | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const capabilitySummary = useMemo(() => {
    const availableCount = modelConfigs.filter((item) => item.status === "available").length;
    const imageCount = modelConfigs.filter((item) => item.supportsImageInput).length;
    return { availableCount, imageCount };
  }, [modelConfigs]);

  async function handleSubmitModelConfig(payload: ModelConfigPayload, editingId?: string) {
    setIsSaving(true);
    try {
      if (editingId) {
        await onUpdateModelConfig(editingId, payload);
      } else {
        await onCreateModelConfig(payload);
      }
      setIsModalOpen(false);
      setEditingModel(null);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConfirmDelete() {
    if (!deletingModel) return;
    setIsDeleting(true);
    try {
      await onDeleteModelConfig(deletingModel.id);
      setDeletingModel(null);
    } finally {
      setIsDeleting(false);
    }
  }

  if (!isOpen) return null;

  return (
    <>
      <aside
        className="flex w-[420px] flex-col border-l"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
        }}
      >
        <div
          className="flex min-h-[88px] items-center justify-between border-b px-4 py-4"
          style={{ borderColor: "var(--border-light)" }}
        >
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.15em]" style={{ color: "var(--text-tertiary)" }}>
              设置
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-[#2D2926]">模型</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border px-3 py-1.5 text-xs font-medium"
            style={{
              background: "var(--bg-secondary)",
              borderColor: "var(--border-medium)",
              color: "var(--text-secondary)",
            }}
          >
            关闭
          </button>
        </div>

        <div className="flex-1 overflow-hidden px-4 py-4">
          <div className="grid grid-cols-2 gap-3">
          <div
            className="rounded-2xl border px-4 py-3"
            style={{ background: "var(--bg-secondary)", borderColor: "var(--border-light)" }}
          >
            <p className="text-[11px] font-medium uppercase tracking-[0.14em]" style={{ color: "var(--text-tertiary)" }}>
              可用模型
            </p>
            <p className="mt-2 text-2xl font-semibold text-[#2D2926]">
              {capabilitySummary.availableCount}
            </p>
          </div>
          <div
            className="rounded-2xl border px-4 py-3"
            style={{ background: "var(--bg-secondary)", borderColor: "var(--border-light)" }}
          >
            <p className="text-[11px] font-medium uppercase tracking-[0.14em]" style={{ color: "var(--text-tertiary)" }}>
              支持图片
            </p>
            <p className="mt-2 text-2xl font-semibold text-[#2D2926]">
              {capabilitySummary.imageCount}
            </p>
          </div>
        </div>

        <div className="mt-4 min-h-0 flex-1 overflow-hidden">
          <ModelConfigTable
            modelConfigs={modelConfigs}
            isLoading={isLoading}
            error={error}
            onCreate={() => {
              setEditingModel(null);
              setIsModalOpen(true);
            }}
            onEdit={(modelConfig) => {
              setEditingModel(modelConfig);
              setIsModalOpen(true);
            }}
            onValidate={(modelConfigId) => {
              void onValidateModelConfig(modelConfigId);
            }}
            onDelete={(modelConfig) => {
              setDeletingModel({
                id: modelConfig.id,
                name: modelConfig.displayName,
                impactedAgents: impactedAgentsByModelConfigId[modelConfig.id] ?? [],
              });
            }}
          />
        </div>
        </div>
      </aside>

      <ModelConfigModal
        isOpen={isModalOpen}
        editingModel={editingModel}
        isSaving={isSaving}
        onClose={() => {
          setIsModalOpen(false);
          setEditingModel(null);
        }}
        onSubmit={(payload, editingId) => {
          void handleSubmitModelConfig(payload, editingId);
        }}
      />

      {deletingModel ? (
        <DeleteModelConfigModal
          modelConfigName={deletingModel.name}
          impactedAgents={deletingModel.impactedAgents}
          isDeleting={isDeleting}
          onCancel={() => setDeletingModel(null)}
          onConfirm={() => {
            void handleConfirmDelete();
          }}
        />
      ) : null}
    </>
  );
}
