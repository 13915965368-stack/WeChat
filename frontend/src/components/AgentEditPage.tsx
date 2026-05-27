import { useState, useRef, useCallback, useMemo } from "react";
import type { Agent, ModelConfig } from "../types/chat";
import { ModelCapabilityBadges } from "./ModelCapabilityBadges";
import { ModelStatusBadge } from "./ModelStatusBadge";

type Props = {
  agent: Agent;
  modelConfigs: ModelConfig[];
  onBack: () => void;
  onOpenModelSettings: () => void;
  onUpdateModelBinding: (modelConfigId: string | null) => Promise<void> | void;
  onSave: (updates: Partial<Agent>) => Promise<void> | void;
};

export function AgentEditPage({
  agent,
  modelConfigs,
  onBack,
  onOpenModelSettings,
  onUpdateModelBinding,
  onSave,
}: Props) {
  const [name, setName] = useState(agent.name);
  const [avatar, setAvatar] = useState(agent.avatar);
  const [avatarImage, setAvatarImage] = useState(agent.avatarImage);
  const [roleSummary, setRoleSummary] = useState(agent.roleSummary);
  const [styleSummary, setStyleSummary] = useState(agent.styleSummary);
  const [systemPrompt, setSystemPrompt] = useState(agent.systemPrompt);
  const [themeColor, setThemeColor] = useState(agent.themeColor);
  const [cropMode, setCropMode] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [cropPos, setCropPos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isSaving, setIsSaving] = useState(false);
  const [isBindingModel, setIsBindingModel] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const CROP_SIZE = 160;
  const selectedModelConfigId = agent.modelConfigId ?? "";
  const boundModel = useMemo(
    () => modelConfigs.find((modelConfig) => modelConfig.id === selectedModelConfigId) ?? null,
    [modelConfigs, selectedModelConfigId]
  );
  const hasMissingBoundModel = Boolean(selectedModelConfigId && !boundModel);
  const selectableModels = useMemo(
    () =>
      modelConfigs.filter(
        (modelConfig) => modelConfig.status === "available" || modelConfig.id === selectedModelConfigId
      ),
    [modelConfigs, selectedModelConfigId]
  );
  const modelWarningMessage = hasMissingBoundModel
    ? "当前 Agent 绑定的模型配置已被删除，请重新绑定一个可用模型后再继续发送消息。"
    : agent.modelUnavailable
      ? "当前 Agent 绑定的模型已失效，请重新绑定一个可用模型后再继续发送消息。"
      : null;

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);

    try {
      await onSave({
        name,
        avatar,
        avatarImage,
        roleSummary,
        styleSummary,
        systemPrompt,
        themeColor,
        themeLight: themeColor + "20",
        themeSoft: themeColor + "10",
      });
      onBack();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "保存失败，请稍后重试");
    } finally {
      setIsSaving(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("请选择图片文件");
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      const result = event.target?.result as string;
      setPreviewImage(result);
      setCropMode(true);
      setCropPos({ x: 0, y: 0 });
    };
    reader.readAsDataURL(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleCropConfirm() {
    if (!previewImage || !imageRef.current) return;
    const img = imageRef.current;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const scale = img.naturalWidth / img.clientWidth;
    const sourceX = Math.max(0, -cropPos.x * scale);
    const sourceY = Math.max(0, -cropPos.y * scale);
    const sourceSize = CROP_SIZE * scale;

    canvas.width = CROP_SIZE;
    canvas.height = CROP_SIZE;

    ctx.drawImage(
      img,
      sourceX,
      sourceY,
      sourceSize,
      sourceSize,
      0,
      0,
      CROP_SIZE,
      CROP_SIZE
    );

    const croppedDataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setAvatarImage(croppedDataUrl);
    setCropMode(false);
    setPreviewImage(null);
  }

  function handleCropCancel() {
    setCropMode(false);
    setPreviewImage(null);
    setCropPos({ x: 0, y: 0 });
  }

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - cropPos.x, y: e.clientY - cropPos.y });
  }, [cropPos]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging || !containerRef.current) return;
    const container = containerRef.current;
    const rect = container.getBoundingClientRect();
    const maxX = rect.width - CROP_SIZE;
    const maxY = rect.height - CROP_SIZE;
    
    let newX = e.clientX - dragStart.x;
    let newY = e.clientY - dragStart.y;
    
    newX = Math.max(maxX, Math.min(0, newX));
    newY = Math.max(maxY, Math.min(0, newY));
    
    setCropPos({ x: newX, y: newY });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const presetColors = ["#D4A574", "#C97B7B", "#7BA89C", "#5B7BA3", "#9B8AA5", "#E8A87C", "#7BB5A0", "#B5A07B"];

  async function handleModelBindingChange(nextModelConfigId: string) {
    setIsBindingModel(true);
    setSaveError(null);
    try {
      await onUpdateModelBinding(nextModelConfigId || null);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "更新模型绑定失败，请稍后重试");
    } finally {
      setIsBindingModel(false);
    }
  }

  return (
    <section
      className="flex h-full w-80 flex-shrink-0 flex-col border-r"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border-light)",
      }}
    >
      <div
        className="flex min-h-[88px] flex-shrink-0 items-center border-b px-6 py-4"
        style={{ borderColor: "var(--border-light)" }}
      >
        <div className="flex w-full items-center justify-between">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-sm font-medium transition-colors hover:text-[#2D2926]"
            style={{ color: "var(--text-tertiary)" }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            返回
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium text-white transition-all duration-200 hover:shadow-md"
            style={{
              background: agent.themeColor,
              boxShadow: `0 2px 8px ${agent.themeColor}40`,
              opacity: isSaving ? 0.7 : 1,
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            {isSaving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex flex-col gap-5">
          {saveError && (
            <div
              className="rounded-xl border px-3 py-2 text-xs"
              style={{
                background: "#FFF5F5",
                borderColor: "#F3C4C4",
                color: "#A63A3A",
              }}
            >
              {saveError}
            </div>
          )}

          {/* 形象设计区 */}
          <div
            className="rounded-2xl border p-5"
            style={{
              background: "var(--bg-card)",
              borderColor: "var(--border-light)",
              boxShadow: "var(--shadow-soft)",
            }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="h-2 w-2 rounded-full" style={{ background: agent.themeColor }} />
              <span className="text-xs font-medium uppercase tracking-wider text-[#A39E99]">
                形象设计
              </span>
            </div>

            {/* 头像预览 */}
            <div className="flex flex-col items-center gap-3 mb-4">
              <div
                className="flex h-20 w-20 items-center justify-center rounded-3xl text-3xl font-bold text-white shadow-md overflow-hidden"
                style={{ background: avatarImage ? "transparent" : themeColor }}
              >
                {avatarImage ? (
                  <img src={avatarImage} alt="avatar" className="h-full w-full object-cover" />
                ) : (
                  avatar
                )}
              </div>
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                当前头像预览
              </p>
            </div>

            {/* 图片上传 + 裁剪 */}
            <div className="mb-4">
              <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                头像图片
              </label>

              {!cropMode ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
                    style={{
                      background: "var(--bg-secondary)",
                      borderColor: "var(--border-medium)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </svg>
                    {avatarImage ? "更换图片" : "上传图片"}
                  </button>
                  {avatarImage && (
                    <button
                      onClick={() => {
                        setAvatarImage(undefined);
                        setAvatar(agent.avatar);
                      }}
                      className="text-xs transition-colors hover:text-[#C97B7B]"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      恢复默认
                    </button>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border overflow-hidden" style={{ borderColor: "var(--border-medium)" }}>
                  <div
                    ref={containerRef}
                    className="relative overflow-hidden cursor-move"
                    style={{ height: 200 }}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                  >
                    <img
                      ref={imageRef}
                      src={previewImage!}
                      alt="preview"
                      className="absolute max-w-none"
                      style={{
                        left: cropPos.x,
                        top: cropPos.y,
                        width: "auto",
                        height: "100%",
                        minWidth: "100%",
                      }}
                      draggable={false}
                    />
                    <div
                      className="absolute pointer-events-none"
                      style={{
                        left: "50%",
                        top: "50%",
                        width: CROP_SIZE,
                        height: CROP_SIZE,
                        transform: "translate(-50%, -50%)",
                        boxShadow: "0 0 0 9999px rgba(0,0,0,0.5)",
                        borderRadius: 24,
                      }}
                    />
                    <div
                      className="absolute pointer-events-none border-2 border-white"
                      style={{
                        left: "50%",
                        top: "50%",
                        width: CROP_SIZE,
                        height: CROP_SIZE,
                        transform: "translate(-50%, -50%)",
                        borderRadius: 24,
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between px-3 py-2" style={{ background: "var(--bg-secondary)" }}>
                    <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                      拖动图片调整位置
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCropCancel}
                        className="text-xs px-2 py-1 rounded-lg transition-colors hover:bg-[#F5F0E8]"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        取消
                      </button>
                      <button
                        onClick={handleCropConfirm}
                        className="text-xs px-3 py-1.5 rounded-lg text-white transition-all"
                        style={{ background: agent.themeColor }}
                      >
                        确认裁剪
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />
              <p className="mt-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                支持 JPG、PNG 格式，建议上传正方形图片
              </p>
            </div>

            {!avatarImage && (
              <div className="mb-4">
                <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  头像文字
                </label>
                <input
                  type="text"
                  value={avatar}
                  onChange={(e) => setAvatar(e.target.value.slice(0, 2))}
                  maxLength={2}
                  className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-shadow focus:shadow-md"
                  style={{
                    background: "var(--bg-secondary)",
                    borderColor: "var(--border-medium)",
                    color: "var(--text-primary)",
                  }}
                  placeholder="1-2 个字符"
                />
                <p className="mt-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                  支持 1-2 个字符，如字母、Emoji 等
                </p>
              </div>
            )}

            <div className="mb-4">
              <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                名称
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-shadow focus:shadow-md"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-primary)",
                }}
                placeholder="Agent 名称"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                主题色
              </label>
              <div className="flex flex-wrap gap-2">
                {presetColors.map((color) => (
                  <button
                    key={color}
                    onClick={() => setThemeColor(color)}
                    className="h-8 w-8 rounded-lg transition-all duration-200 hover:scale-110"
                    style={{
                      background: color,
                      boxShadow: themeColor === color ? `0 0 0 2px #FFFFFF, 0 0 0 4px ${color}` : "none",
                    }}
                  />
                ))}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <input
                  type="color"
                  value={themeColor}
                  onChange={(e) => setThemeColor(e.target.value)}
                  className="h-8 w-8 rounded cursor-pointer"
                />
                <span className="text-xs text-[#6B6560]">{themeColor}</span>
              </div>
            </div>
          </div>

          {/* 人设编辑区 */}
          <div
            className="rounded-2xl border p-5"
            style={{
              background: "var(--bg-card)",
              borderColor: "var(--border-light)",
              boxShadow: "var(--shadow-soft)",
            }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="h-2 w-2 rounded-full" style={{ background: agent.themeColor }} />
              <span className="text-xs font-medium uppercase tracking-wider text-[#A39E99]">
                人设设定
              </span>
            </div>

            <div className="mb-4">
              <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                角色定位
              </label>
              <textarea
                value={roleSummary}
                onChange={(e) => setRoleSummary(e.target.value)}
                rows={3}
                className="w-full resize-none rounded-xl border px-4 py-3 text-sm leading-relaxed outline-none transition-shadow focus:shadow-md"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-primary)",
                }}
                placeholder="描述这个 Agent 的角色定位..."
              />
            </div>

            <div className="mb-4">
              <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                表达风格
              </label>
              <textarea
                value={styleSummary}
                onChange={(e) => setStyleSummary(e.target.value)}
                rows={3}
                className="w-full resize-none rounded-xl border px-4 py-3 text-sm leading-relaxed outline-none transition-shadow focus:shadow-md"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-primary)",
                }}
                placeholder="描述这个 Agent 的表达风格..."
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                系统提示词
              </label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={4}
                className="w-full resize-none rounded-xl border px-4 py-3 text-sm leading-relaxed outline-none transition-shadow focus:shadow-md"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-primary)",
                }}
                placeholder="输入系统提示词..."
              />
            </div>
          </div>

          <div
            className="rounded-2xl border p-5"
            style={{
              background: "var(--bg-card)",
              borderColor: "var(--border-light)",
              boxShadow: "var(--shadow-soft)",
            }}
          >
            <div className="mb-4 flex items-center gap-2">
              <div className="h-2 w-2 rounded-full" style={{ background: agent.themeColor }} />
              <span className="text-xs font-medium uppercase tracking-wider text-[#A39E99]">
                模型绑定
              </span>
            </div>

            {modelWarningMessage ? (
              <div
                className="mb-4 rounded-xl border px-4 py-3 text-sm"
                style={{
                  background: "#FFF5F5",
                  borderColor: "#F2D5D5",
                  color: "#B85E5E",
                }}
              >
                {modelWarningMessage}
              </div>
            ) : null}

            <div>
              <label className="mb-1.5 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                当前模型
              </label>
              <select
                aria-label="当前模型"
                value={selectedModelConfigId}
                onChange={(event) => {
                  void handleModelBindingChange(event.target.value);
                }}
                disabled={isBindingModel}
                className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition-shadow focus:shadow-md disabled:opacity-70"
                style={{
                  background: "var(--bg-secondary)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-primary)",
                }}
              >
                <option value="">暂不绑定模型</option>
                {hasMissingBoundModel ? (
                  <option value={selectedModelConfigId} disabled>
                    已删除的模型配置（请重新绑定）
                  </option>
                ) : null}
                {selectableModels.map((modelConfig) => (
                  <option key={modelConfig.id} value={modelConfig.id}>
                    {modelConfig.provider} - {modelConfig.model}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                仅展示当前可用模型；已失效模型会通过状态提示单独说明。
              </p>
            </div>

            <div
              className="mt-4 rounded-xl border px-4 py-4"
              style={{
                background: "var(--bg-secondary)",
                borderColor: "var(--border-light)",
              }}
            >
              {boundModel ? (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-[#2D2926]">
                        {boundModel.displayName}
                      </div>
                      <p className="mt-1 truncate text-xs" style={{ color: "var(--text-secondary)" }}>
                        {boundModel.provider} - {boundModel.model}
                      </p>
                    </div>
                    <ModelStatusBadge status={boundModel.status} />
                  </div>
                  <div className="mt-3">
                    <ModelCapabilityBadges model={boundModel} />
                  </div>
                </>
              ) : hasMissingBoundModel ? (
                <div className="text-sm" style={{ color: "#B85E5E" }}>
                  这个 Agent 仍保留原模型绑定记录，但对应模型配置已被删除。请重新选择一个可用模型。
                </div>
              ) : (
                <div className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  当前还没有为这个 Agent 绑定模型，后续发送能力会保持禁用。
                </div>
              )}
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                如果模型列表为空，先去右侧设置里添加并校验模型。
              </p>
                <button
                  type="button"
                  onClick={onOpenModelSettings}
                  className="rounded-xl border px-3 py-2 text-xs font-medium transition-colors"
                  style={{
                    background: "var(--bg-secondary)",
                    borderColor: "var(--border-medium)",
                    color: "var(--text-secondary)",
                  }}
                >
                  前往模型管理
                </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
