import type { ModelConfig } from "../types/chat";

type Props = {
  model: Pick<
    ModelConfig,
    | "supportsImageInput"
    | "supportsFileInput"
    | "supportsStreaming"
  >;
};

function SmallBadge({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "success" | "muted";
}) {
  const toneMap = {
    neutral: {
      background: "var(--bg-secondary)",
      border: "var(--border-light)",
      color: "var(--text-secondary)",
    },
    success: {
      background: "#F0F7F5",
      border: "#D2E7E0",
      color: "#3D7A66",
    },
    muted: {
      background: "#F5F3F0",
      border: "#E2DBD2",
      color: "#8C847C",
    },
  } as const;

  const token = toneMap[tone];

  return (
    <span
      className="inline-flex items-center rounded-full border px-2 py-1 text-[10px] font-medium"
      style={{
        background: token.background,
        borderColor: token.border,
        color: token.color,
      }}
    >
      {label}
    </span>
  );
}

export function ModelCapabilityBadges({ model }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <SmallBadge
        label={model.supportsImageInput ? "支持图片" : "仅文字"}
        tone={model.supportsImageInput ? "success" : "muted"}
      />
      <SmallBadge
        label={model.supportsFileInput ? "支持文件" : "无文件"}
        tone={model.supportsFileInput ? "success" : "muted"}
      />
      <SmallBadge
        label={model.supportsStreaming ? "Streaming" : "非流式"}
        tone={model.supportsStreaming ? "neutral" : "muted"}
      />
    </div>
  );
}
