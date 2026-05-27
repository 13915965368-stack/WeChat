import { useEffect, useMemo, useState } from "react";
import type { ModelApiFormat, ModelConfig, ModelConfigPayload } from "../types/chat";

type Props = {
  isOpen: boolean;
  editingModel?: ModelConfig | null;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (payload: ModelConfigPayload, editingId?: string) => void;
};

type TabMode = "provider" | "custom";

const PROVIDER_PRESETS = {
  openai: {
    label: "OpenAI",
    apiFormat: "openai_chat" as const,
    baseUrl: "https://api.openai.com/v1",
    models: ["gpt-4o", "gpt-4.1-mini", "gpt-4o-mini"],
  },
  deepseek: {
    label: "DeepSeek",
    apiFormat: "openai_chat" as const,
    baseUrl: "https://api.deepseek.com/v1",
    models: ["deepseek-chat", "deepseek-reasoner"],
  },
  glm: {
    label: "GLM（智谱）",
    apiFormat: "openai_chat" as const,
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    models: ["glm-5.1", "glm-4.5-air"],
  },
  moonshot: {
    label: "Kimi（月之暗面）",
    apiFormat: "openai_chat" as const,
    baseUrl: "https://api.moonshot.cn/v1",
    models: ["kimi-k2.6"],
  },
  gemini: {
    label: "Gemini",
    apiFormat: "gemini_generate_content" as const,
    baseUrl: "https://generativelanguage.googleapis.com/v1beta",
    models: ["gemini-2.5-flash", "gemini-2.5-pro"],
  },
  minimax: {
    label: "MiniMax",
    apiFormat: "openai_chat" as const,
    baseUrl: "https://api.minimaxi.com/v1",
    models: ["MiniMax-M2.7", "MiniMax-M2.7-highspeed"],
  },
  qwen: {
    label: "Qwen（通义千问）",
    apiFormat: "openai_chat" as const,
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    models: ["qwen-plus", "qwen3.6-plus-2026-04-02"],
  },
} as const;

function resolveCustomProvider(apiFormat: ModelApiFormat): string {
  switch (apiFormat) {
    case "anthropic_messages":
      return "anthropic";
    case "gemini_generate_content":
      return "gemini";
    case "openai_chat":
    default:
      return "custom_openai_compatible";
  }
}

function mapModelToPayload(model: ModelConfig): ModelConfigPayload {
  return {
    provider: model.provider,
    model: model.model,
    displayName: model.displayName,
    apiFormat: model.apiFormat,
    baseUrl: model.baseUrl,
    useFullUrl: model.useFullUrl,
    supportsImageInput: model.supportsImageInput,
    supportsFileInput: model.supportsFileInput,
    supportsSystemPrompt: model.supportsSystemPrompt,
    supportsStreaming: model.supportsStreaming,
    contextWindowInput: model.contextWindowInput ?? null,
    contextWindowOutput: model.contextWindowOutput ?? null,
    maxImageCount: model.maxImageCount ?? null,
    maxImageSizeMb: model.maxImageSizeMb ?? null,
    defaultTemperature: model.defaultTemperature ?? null,
  };
}

export function ModelConfigModal({
  isOpen,
  editingModel,
  isSaving,
  onClose,
  onSubmit,
}: Props) {
  const [tab, setTab] = useState<TabMode>("provider");
  const [provider, setProvider] = useState<keyof typeof PROVIDER_PRESETS>("openai");
  const [apiFormat, setApiFormat] = useState<ModelApiFormat>("openai_chat");
  const [model, setModel] = useState<string>(PROVIDER_PRESETS.openai.models[0]);
  const [baseUrl, setBaseUrl] = useState<string>(PROVIDER_PRESETS.openai.baseUrl);
  const [useFullUrl, setUseFullUrl] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [supportsImageInput, setSupportsImageInput] = useState(false);
  const [contextWindowInput, setContextWindowInput] = useState("128000");
  const [contextWindowOutput, setContextWindowOutput] = useState("8192");
  const [defaultTemperature, setDefaultTemperature] = useState("0.7");
  const [maxImageCount, setMaxImageCount] = useState("5");
  const [maxImageSizeMb, setMaxImageSizeMb] = useState("10");
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  const providerPreset = PROVIDER_PRESETS[provider];

  useEffect(() => {
    if (!isOpen) return;

    if (editingModel) {
      const payload = mapModelToPayload(editingModel);
      setTab(editingModel.provider in PROVIDER_PRESETS ? "provider" : "custom");
      if (editingModel.provider in PROVIDER_PRESETS) {
        setProvider(editingModel.provider as keyof typeof PROVIDER_PRESETS);
      }
      setApiFormat(payload.apiFormat);
      setModel(payload.model);
      setBaseUrl(payload.baseUrl);
      setUseFullUrl(payload.useFullUrl);
      setApiKey("");
      setDisplayName(payload.displayName ?? "");
      setSupportsImageInput(payload.supportsImageInput ?? false);
      setContextWindowInput(String(payload.contextWindowInput ?? ""));
      setContextWindowOutput(String(payload.contextWindowOutput ?? ""));
      setDefaultTemperature(String(payload.defaultTemperature ?? ""));
      setMaxImageCount(String(payload.maxImageCount ?? ""));
      setMaxImageSizeMb(String(payload.maxImageSizeMb ?? ""));
      setIsAdvancedOpen(true);
      return;
    }

    setTab("provider");
    setProvider("openai");
    setApiFormat(PROVIDER_PRESETS.openai.apiFormat);
    setModel(PROVIDER_PRESETS.openai.models[0]);
    setBaseUrl(PROVIDER_PRESETS.openai.baseUrl);
    setUseFullUrl(false);
    setApiKey("");
    setDisplayName("");
      setSupportsImageInput(false);
    setContextWindowInput("128000");
    setContextWindowOutput("8192");
    setDefaultTemperature("0.7");
    setMaxImageCount("5");
    setMaxImageSizeMb("10");
    setIsAdvancedOpen(false);
  }, [editingModel, isOpen]);

  useEffect(() => {
    if (tab !== "provider" || editingModel) return;
    setApiFormat(providerPreset.apiFormat);
    setBaseUrl(providerPreset.baseUrl);
    setModel(providerPreset.models[0]);
    setSupportsImageInput(false);
  }, [provider, providerPreset, tab, editingModel]);

  const computedDisplayName = useMemo(() => {
    if (displayName.trim()) return displayName.trim();
    const providerLabel = tab === "provider" ? providerPreset.label : "自定义";
    return `${providerLabel} - ${model || "未命名模型"}`;
  }, [displayName, model, providerPreset.label, tab]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center px-4 py-8">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      <div
        className="relative max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-[28px] border shadow-2xl"
        style={{
          background: "var(--bg-card)",
          borderColor: "var(--border-light)",
        }}
      >
        <div className="flex items-center justify-between border-b px-6 py-5" style={{ borderColor: "var(--border-light)" }}>
          <div>
            <h3 className="text-2xl font-semibold text-[#2D2926]">
              {editingModel ? "编辑模型" : "添加模型"}
            </h3>
            <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>
              配置模型连接信息，保存后系统会立即校验可用状态。
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 transition-colors hover:bg-[#F5F0E8]"
            aria-label="关闭模型弹窗"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="flex max-h-[calc(90vh-88px)] flex-col overflow-y-auto px-6 py-5">
          <div
            className="grid grid-cols-2 rounded-2xl border p-1"
            style={{ background: "var(--bg-secondary)", borderColor: "var(--border-light)" }}
          >
            <button
              onClick={() => setTab("provider")}
              className="rounded-[14px] px-4 py-3 text-sm font-medium transition-all"
              style={{
                background: tab === "provider" ? "var(--bg-card)" : "transparent",
                color: tab === "provider" ? "#2D2926" : "var(--text-tertiary)",
                boxShadow: tab === "provider" ? "var(--shadow-soft)" : "none",
              }}
            >
              模型服务商
            </button>
            <button
              onClick={() => setTab("custom")}
              className="rounded-[14px] px-4 py-3 text-sm font-medium transition-all"
              style={{
                background: tab === "custom" ? "var(--bg-card)" : "transparent",
                color: tab === "custom" ? "#2D2926" : "var(--text-tertiary)",
                boxShadow: tab === "custom" ? "var(--shadow-soft)" : "none",
              }}
            >
              自定义配置
            </button>
          </div>

          <div className="mt-6 grid gap-4">
            {tab === "provider" ? (
              <>
                <label className="text-sm">
                  <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    服务商
                  </span>
                  <select
                    value={provider}
                    onChange={(event) => setProvider(event.target.value as keyof typeof PROVIDER_PRESETS)}
                    className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-primary)",
                    }}
                  >
                    {Object.entries(PROVIDER_PRESETS).map(([key, value]) => (
                      <option key={key} value={key}>
                        {value.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-sm">
                  <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    模型
                  </span>
                  <select
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-primary)",
                    }}
                  >
                    {providerPreset.models.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : (
              <>
                <label className="text-sm">
                  <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    API 格式
                  </span>
                  <select
                    value={apiFormat}
                    onChange={(event) => setApiFormat(event.target.value as ModelApiFormat)}
                    className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-primary)",
                    }}
                  >
                    <option value="openai_chat">OpenAI Chat Completions 格式</option>
                    <option value="anthropic_messages">Anthropic Messages 格式</option>
                    <option value="gemini_generate_content">Gemini Generate Content 格式</option>
                  </select>
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    自定义请求地址
                  </span>
                  <input
                    value={baseUrl}
                    onChange={(event) => setBaseUrl(event.target.value)}
                    className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-primary)",
                    }}
                    placeholder="https://api.example.com/v1"
                  />
                </label>
                <label className="flex items-center justify-between rounded-2xl border px-4 py-3 text-sm" style={{ background: "var(--bg-secondary)", borderColor: "var(--border-medium)" }}>
                  <span style={{ color: "var(--text-secondary)" }}>完整 URL</span>
                  <button
                    type="button"
                    onClick={() => setUseFullUrl((value) => !value)}
                    className="relative h-6 w-11 rounded-full transition-colors"
                    style={{ background: useFullUrl ? "#5B7BA3" : "#D9D2C8" }}
                    aria-pressed={useFullUrl}
                  >
                    <span
                      className="absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform"
                      style={{ transform: useFullUrl ? "translateX(22px)" : "translateX(2px)" }}
                    />
                  </button>
                </label>
                <div
                  className="rounded-2xl border px-4 py-3 text-sm"
                  style={{ background: "#EEF4FA", borderColor: "#D8E4F1", color: "#5B7BA3" }}
                >
                  {useFullUrl
                    ? "当前把输入视为完整请求 URL，后端不会再自动拼接路径。"
                    : "当前把输入视为服务根地址，后端会按 provider 自动补默认 path。"}
                </div>
                <label className="text-sm">
                  <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    模型 ID
                  </span>
                  <input
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-primary)",
                    }}
                    placeholder="输入模型 ID"
                  />
                </label>
                <label className="flex items-center justify-between rounded-2xl border px-4 py-3 text-sm" style={{ background: "var(--bg-secondary)", borderColor: "var(--border-medium)" }}>
                  <span style={{ color: "var(--text-secondary)" }}>支持图片输入</span>
                  <button
                    type="button"
                    onClick={() => setSupportsImageInput((value) => !value)}
                    className="relative h-6 w-11 rounded-full transition-colors"
                    style={{ background: supportsImageInput ? "#7BA89C" : "#D9D2C8" }}
                    aria-pressed={supportsImageInput}
                  >
                    <span
                      className="absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform"
                      style={{ transform: supportsImageInput ? "translateX(22px)" : "translateX(2px)" }}
                    />
                  </button>
                </label>
              </>
            )}

            <label className="text-sm">
              <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                API 密钥
              </span>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={editingModel?.apiKeyConfigured ? "已配置，如需覆盖请重新输入" : "输入 API 密钥"}
                className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-primary)",
                }}
              />
            </label>

            <button
              type="button"
              onClick={() => setIsAdvancedOpen((value) => !value)}
              className="flex items-center justify-between rounded-2xl border px-4 py-3 text-left text-sm"
              style={{
                background: "var(--bg-secondary)",
                borderColor: "var(--border-light)",
                color: "var(--text-secondary)",
              }}
            >
              <span>高级配置</span>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ transform: isAdvancedOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
              >
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>

            {isAdvancedOpen ? (
              <div
                className="grid gap-4 rounded-2xl border p-4"
                style={{
                  background: "var(--bg-card)",
                  borderColor: "var(--border-light)",
                }}
              >
                <label className="text-sm">
                  <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    模型展示名称
                  </span>
                  <input
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-primary)",
                    }}
                    placeholder={computedDisplayName}
                  />
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <label className="text-sm">
                    <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                      输入上下文窗口
                    </span>
                    <input
                      value={contextWindowInput}
                      onChange={(event) => setContextWindowInput(event.target.value)}
                      className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                      style={{
                        background: "var(--bg-secondary)",
                        borderColor: "var(--border-medium)",
                        color: "var(--text-primary)",
                      }}
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                      输出窗口
                    </span>
                    <input
                      value={contextWindowOutput}
                      onChange={(event) => setContextWindowOutput(event.target.value)}
                      className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                      style={{
                        background: "var(--bg-secondary)",
                        borderColor: "var(--border-medium)",
                        color: "var(--text-primary)",
                      }}
                    />
                  </label>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <label className="text-sm">
                    <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                      默认温度
                    </span>
                    <input
                      value={defaultTemperature}
                      onChange={(event) => setDefaultTemperature(event.target.value)}
                      className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                      style={{
                        background: "var(--bg-secondary)",
                        borderColor: "var(--border-medium)",
                        color: "var(--text-primary)",
                      }}
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                      最大图片数
                    </span>
                    <input
                      value={maxImageCount}
                      onChange={(event) => setMaxImageCount(event.target.value)}
                      className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                      style={{
                        background: "var(--bg-secondary)",
                        borderColor: "var(--border-medium)",
                        color: "var(--text-primary)",
                      }}
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                      单图大小 MB
                    </span>
                    <input
                      value={maxImageSizeMb}
                      onChange={(event) => setMaxImageSizeMb(event.target.value)}
                      className="w-full rounded-2xl border px-4 py-3 text-sm outline-none"
                      style={{
                        background: "var(--bg-secondary)",
                        borderColor: "var(--border-medium)",
                        color: "var(--text-primary)",
                      }}
                    />
                  </label>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-6 flex items-center justify-between gap-3 border-t pt-5" style={{ borderColor: "var(--border-light)" }}>
            <div className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              当前将以 <span className="font-medium text-[#2D2926]">{computedDisplayName}</span> 保存
            </div>
            <div className="flex items-center gap-3">
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
                onClick={() =>
                  onSubmit(
                    {
                      provider: tab === "provider" ? provider : resolveCustomProvider(apiFormat),
                      model,
                      displayName: computedDisplayName,
                      apiFormat,
                      baseUrl,
                      useFullUrl,
                      apiKey: apiKey || undefined,
                      supportsImageInput,
                      supportsFileInput: false,
                      supportsSystemPrompt: true,
                      supportsStreaming: false,
                      contextWindowInput: contextWindowInput ? Number(contextWindowInput) : null,
                      contextWindowOutput: contextWindowOutput ? Number(contextWindowOutput) : null,
                      maxImageCount: maxImageCount ? Number(maxImageCount) : null,
                      maxImageSizeMb: maxImageSizeMb ? Number(maxImageSizeMb) : null,
                      defaultTemperature: defaultTemperature ? Number(defaultTemperature) : null,
                    },
                    editingModel?.id
                  )
                }
                disabled={
                  isSaving ||
                  !model.trim() ||
                  !baseUrl.trim() ||
                  (!editingModel && !apiKey.trim()) ||
                  (!!editingModel && !editingModel.apiKeyConfigured && !apiKey.trim())
                }
                className="rounded-xl px-5 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:shadow-md disabled:opacity-50"
                style={{
                  background: "#5B7BA3",
                  boxShadow: "0 4px 12px rgba(91, 123, 163, 0.22)",
                }}
              >
                {isSaving ? "保存中..." : editingModel ? "保存修改" : "添加模型"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
