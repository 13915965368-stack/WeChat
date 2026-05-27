import type { ModelConfigStatus } from "../types/chat";

type Props = {
  status: ModelConfigStatus;
};

const STATUS_STYLE: Record<
  ModelConfigStatus,
  { label: string; background: string; color: string; border: string }
> = {
  draft: {
    label: "草稿",
    background: "#F7F2EB",
    color: "#8B6F47",
    border: "#E7D7C0",
  },
  validating: {
    label: "校验中",
    background: "#EEF4FA",
    color: "#5B7BA3",
    border: "#D8E4F1",
  },
  available: {
    label: "可用",
    background: "#F0F7F5",
    color: "#3D7A66",
    border: "#D2E7E0",
  },
  failed: {
    label: "失败",
    background: "#FFF5F5",
    color: "#B85E5E",
    border: "#F2D5D5",
  },
  disabled: {
    label: "停用",
    background: "#F5F3F0",
    color: "#8C847C",
    border: "#E2DBD2",
  },
};

export function ModelStatusBadge({ status }: Props) {
  const token = STATUS_STYLE[status];

  return (
    <span
      className="inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium"
      style={{
        background: token.background,
        color: token.color,
        borderColor: token.border,
      }}
    >
      {token.label}
    </span>
  );
}
