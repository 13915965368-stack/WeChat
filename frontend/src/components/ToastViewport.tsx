export type ToastItem = {
  id: string;
  title: string;
  description?: string;
  tone?: "success" | "error" | "warning";
};

type Props = {
  toasts: ToastItem[];
  onDismiss: (toastId: string) => void;
};

const TONE_STYLE = {
  success: {
    background: "#F0F7F5",
    border: "#D2E7E0",
    title: "#2D2926",
    text: "#3D7A66",
  },
  error: {
    background: "#FFF5F5",
    border: "#F2D5D5",
    title: "#2D2926",
    text: "#B85E5E",
  },
  warning: {
    background: "#FFF8EE",
    border: "#EFDDBA",
    title: "#2D2926",
    text: "#9A6A16",
  },
} as const;

export function ToastViewport({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[95] flex w-full max-w-sm flex-col gap-3">
      {toasts.map((toast) => {
        const tone = TONE_STYLE[toast.tone ?? "success"];
        return (
          <div
            key={toast.id}
            className="pointer-events-auto rounded-2xl border p-4 shadow-xl"
            style={{
              background: tone.background,
              borderColor: tone.border,
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold" style={{ color: tone.title }}>
                  {toast.title}
                </div>
                {toast.description ? (
                  <p className="mt-1 text-xs leading-relaxed" style={{ color: tone.text }}>
                    {toast.description}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                className="rounded-full p-1 transition-colors hover:bg-white/60"
                aria-label="关闭提示"
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={tone.text}
                  strokeWidth="2"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
