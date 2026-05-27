import { useState, useRef, useEffect } from "react";
import type { FormEvent } from "react";

type ComposerImage = {
  id: string;
  file: File;
  previewUrl: string;
};

type Props = {
  onSend: (content: string, imageFiles: File[]) => Promise<void> | void;
  canSend?: boolean;
  sendDisabledReason?: string;
  canAttachImage?: boolean;
  imageCapabilityReason?: string;
  maxImageCount?: number | null;
  maxImageSizeMb?: number | null;
};

export function MessageComposer({
  onSend,
  canSend = true,
  sendDisabledReason,
  canAttachImage = true,
  imageCapabilityReason,
  maxImageCount = 5,
  maxImageSizeMb = 10,
}: Props) {
  const [value, setValue] = useState("");
  const [selectedImages, setSelectedImages] = useState<ComposerImage[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectedImagesRef = useRef<ComposerImage[]>([]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  useEffect(() => {
    selectedImagesRef.current = selectedImages;
  }, [selectedImages]);

  useEffect(() => {
    return () => {
      selectedImagesRef.current.forEach((image) => URL.revokeObjectURL(image.previewUrl));
    };
  }, []);

  async function doSend() {
    const trimmed = value.trim();
    if (!canSend || (!trimmed && selectedImages.length === 0) || isSending) return;

    setIsSending(true);
    try {
      await onSend(
        trimmed,
        selectedImages.map((image) => image.file)
      );
      selectedImages.forEach((image) => URL.revokeObjectURL(image.previewUrl));
      setSelectedImages([]);
      setValue("");
      setImageError(null);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    } finally {
      setIsSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void doSend();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void doSend();
    }
  }

  function handleImageClick() {
    if (!canAttachImage) return;
    imageInputRef.current?.click();
  }

  function handleFileClick() {
    fileInputRef.current?.click();
  }

  function handleImageChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      if (!canAttachImage) {
        setImageError(imageCapabilityReason ?? "当前模型不支持图片输入。");
      } else if (!file.type.startsWith("image/")) {
        setImageError("请选择图片文件。");
      } else if (maxImageSizeMb && file.size > maxImageSizeMb * 1024 * 1024) {
        setImageError(`单张图片不能超过 ${maxImageSizeMb}MB。`);
      } else if (selectedImages.length >= (maxImageCount ?? 5)) {
        setImageError(`最多只能添加 ${maxImageCount ?? 5} 张图片。`);
      } else {
        const previewUrl = URL.createObjectURL(file);
        setSelectedImages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            file,
            previewUrl,
          },
        ]);
        setImageError(null);
      }
    }
    if (imageInputRef.current) imageInputRef.current.value = "";
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      console.log("选择的文件:", file.name);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleVoiceClick() {
    console.log("语音输入");
  }

  function removeImage(imageId: string) {
    setSelectedImages((prev) => {
      const target = prev.find((image) => image.id === imageId);
      if (target) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return prev.filter((image) => image.id !== imageId);
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex-shrink-0 border-t px-4 py-4"
      style={{
        background: "var(--bg-card)",
        borderColor: "var(--border-light)",
      }}
    >
      {selectedImages.length > 0 ? (
        <div
          className="mb-3 flex flex-wrap gap-3 rounded-2xl border p-3"
          style={{
            background: "var(--bg-secondary)",
            borderColor: "var(--border-light)",
          }}
        >
          {selectedImages.map((image) => (
            <div key={image.id} className="relative">
              <img
                src={image.previewUrl}
                alt={image.file.name}
                className="h-20 w-20 rounded-xl object-cover"
              />
              <button
                type="button"
                onClick={() => removeImage(image.id)}
                className="absolute -right-2 -top-2 rounded-full border bg-white p-1 shadow-sm"
                style={{ borderColor: "var(--border-light)", color: "var(--text-secondary)" }}
                aria-label={`移除图片 ${image.file.name}`}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {/* 输入框容器：图标嵌入其中 */}
      <div
        className="flex items-center gap-2 rounded-2xl border px-3 py-3 transition-shadow duration-200 focus-within:shadow-md"
        style={{
          background: "var(--bg-secondary)",
          borderColor: "var(--border-medium)",
        }}
      >
        {/* 左侧功能图标组 */}
        <div className="flex items-center gap-1">
          {/* 图片上传 */}
          <button
            type="button"
            onClick={handleImageClick}
            disabled={!canAttachImage}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 hover:bg-white/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5B7BA3]/40 disabled:cursor-not-allowed disabled:opacity-40"
            style={{ color: "var(--text-tertiary)" }}
            title={canAttachImage ? "上传图片" : imageCapabilityReason || "当前模型不支持图片输入"}
            aria-label={canAttachImage ? "上传图片" : "当前模型不支持图片输入"}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          </button>
          <input ref={imageInputRef} type="file" accept="image/*" onChange={handleImageChange} className="hidden" />

          {/* 文件上传 */}
          <button
            type="button"
            onClick={handleFileClick}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 hover:bg-white/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5B7BA3]/40"
            style={{ color: "var(--text-tertiary)" }}
            title="上传文件 (Markdown 等)"
            aria-label="上传文件（即将支持）"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <input ref={fileInputRef} type="file" accept=".md,.txt,.doc,.docx,.pdf" onChange={handleFileChange} className="hidden" />
        </div>

        {/* 输入框 */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
            placeholder={canSend ? "输入你的想法..." : sendDisabledReason || "当前暂不可发送"}
          rows={1}
          aria-label="消息输入"
            disabled={!canSend}
          className="max-h-[160px] min-h-[48px] flex-1 resize-none bg-transparent py-3 text-sm leading-relaxed outline-none placeholder:text-[#A39E99] focus-visible:outline-none"
          style={{ color: "var(--text-primary)" }}
        />

        {/* 右侧功能图标组 */}
        <div className="flex items-center gap-1">
          {/* 语音输入 */}
          <button
            type="button"
            onClick={handleVoiceClick}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 hover:bg-white/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5B7BA3]/40"
            style={{ color: "var(--text-tertiary)" }}
            title="语音输入"
            aria-label="语音输入（即将支持）"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>

          {/* 发送按钮 */}
          <button
            type="submit"
            disabled={!canSend || (!value.trim() && selectedImages.length === 0) || isSending}
            aria-label="发送消息"
            title={canSend ? "发送消息" : sendDisabledReason || "当前暂不可发送"}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-white transition-all duration-200 hover:scale-105 disabled:scale-100 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5B7BA3]/40"
            style={{
              background: value.trim() || selectedImages.length > 0 ? "#5B7BA3" : "#C4BFB9",
              boxShadow:
                value.trim() || selectedImages.length > 0
                  ? "0 2px 8px rgba(91, 123, 163, 0.3)"
                  : "none",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>

      {imageError ? (
        <p className="mt-2 text-center text-[11px]" style={{ color: "#B85E5E" }}>
          {imageError}
        </p>
      ) : !canSend && sendDisabledReason ? (
        <p className="mt-2 text-center text-[11px]" style={{ color: "var(--text-tertiary)" }}>
          {sendDisabledReason}
        </p>
      ) : !canAttachImage && imageCapabilityReason ? (
        <p className="mt-2 text-center text-[11px]" style={{ color: "var(--text-tertiary)" }}>
          {imageCapabilityReason}
        </p>
      ) : null}

      <p className="mt-2 text-center text-[11px] text-[#C4BFB9]">
        按 Enter 发送 · Shift + Enter 换行
      </p>
    </form>
  );
}
