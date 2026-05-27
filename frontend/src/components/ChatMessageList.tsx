import { useMemo } from "react";
import type { Message, Agent } from "../types/chat";

type Props = {
  messages: Message[];
  agents: Agent[];
  activeAgentName: string;
  activeAgentId: string;
  isGroup?: boolean;
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatAttachmentSize(size?: number): string | null {
  if (size === undefined || size === null || Number.isNaN(size)) {
    return null;
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    const kb = size / 1024;
    return `${kb >= 10 ? kb.toFixed(0) : kb.toFixed(1)} KB`;
  }
  const mb = size / (1024 * 1024);
  return `${mb >= 10 ? mb.toFixed(0) : mb.toFixed(1)} MB`;
}

export function ChatMessageList({ messages, agents, activeAgentName, activeAgentId, isGroup = false }: Props) {
  const agentMap = useMemo(() => {
    const map: Record<string, Agent> = {};
    agents.forEach((a) => (map[a.id] = a));
    return map;
  }, [agents]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 min-h-0" style={{ scrollbarGutter: "stable" }}>
      <div className="space-y-5">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div
              className="mb-4 flex h-16 w-16 items-center justify-center rounded-3xl"
              style={{
                background: agentMap[activeAgentId]?.themeSoft || "#F5F0E8",
              }}
            >
              <span
                className="font-display text-2xl font-bold"
                style={{ color: agentMap[activeAgentId]?.themeColor || "#6B6560" }}
              >
                {isGroup ? "👥" : agentMap[activeAgentId]?.avatar || "A"}
              </span>
            </div>
            <h3 className="font-display text-lg font-semibold text-[#2D2926]">
              {isGroup ? "群聊开始" : `和 ${activeAgentName} 开始对话`}
            </h3>
            <p className="mt-2 max-w-xs text-sm leading-relaxed text-[#A39E99]">
              {isGroup
                ? "群成员会共享当前消息流，并按固定顺序依次响应你的输入。"
                : `你可以直接输入想法，${activeAgentName} 会根据它的角色风格来回应你。`}
            </p>
          </div>
        )}

        {messages.map((message, index) => {
          const isUser = message.senderType === "user";
          const agent = !isUser ? agentMap[message.senderId] : null;
          const showAvatar =
            index === 0 || messages[index - 1].senderId !== message.senderId;
          const attachments = message.attachments ?? [];
          const hasTextContent = message.content.trim().length > 0;

          return (
            <div
              key={message.id}
              className={`flex ${isUser ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`flex max-w-[75%] gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
              >
                {/* Avatar - 用户和Agent都显示 */}
                <div className="flex-shrink-0 pt-1">
                  {showAvatar ? (
                    isUser ? (
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#5B7BA3] text-sm font-bold text-white">
                        我
                      </div>
                    ) : agent ? (
                      <div
                        className="flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold text-white overflow-hidden"
                        style={{ background: agent.avatarImage ? "transparent" : agent.themeColor }}
                      >
                        {agent.avatarImage ? (
                          <img src={agent.avatarImage} alt={agent.name} className="h-full w-full object-cover" />
                        ) : (
                          agent.avatar
                        )}
                      </div>
                    ) : null
                  ) : (
                    <div className="h-9 w-9" />
                  )}
                </div>

                {/* 消息内容 */}
                <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                  {/* 发送者名称 */}
                  <div className="mb-1 flex items-center gap-2">
                    {showAvatar && (
                      <span
                        className="text-xs font-medium"
                        style={{
                          color: isUser ? "#5B7BA3" : agent?.themeColor || "#6B6560",
                        }}
                      >
                        {isUser ? "我" : agent?.name}
                      </span>
                    )}
                    <span className="text-[11px] text-[#C4BFB9]">
                      {formatTime(message.createdAt)}
                    </span>
                  </div>

                  {attachments.length > 0 ? (
                    <div className="mb-2 flex max-w-full flex-wrap gap-3">
                      {attachments.map((attachment, attachmentIndex) => {
                        const attachmentLabel = attachment.name || `图片附件 ${attachmentIndex + 1}`;
                        const attachmentMeta = [
                          attachment.mimeType,
                          formatAttachmentSize(attachment.size),
                        ]
                          .filter(Boolean)
                          .join(" · ");

                        return (
                          <div
                            key={`${message.id}-${attachment.attachmentId ?? attachment.id}-${attachmentIndex}`}
                            className="w-[220px] overflow-hidden rounded-2xl border bg-white/95 shadow-sm"
                            style={{
                              borderColor: isUser ? "#D6E0EC" : "var(--border-light)",
                            }}
                          >
                            {attachment.previewUrl ? (
                              <img
                                src={attachment.previewUrl}
                                alt={attachmentLabel}
                                className="h-40 w-full object-cover"
                              />
                            ) : (
                              <div
                                className="flex h-40 items-center justify-center text-sm"
                                style={{ background: "#F5F0E8", color: "#6B6560" }}
                              >
                                图片附件
                              </div>
                            )}
                            <div className="px-3 py-2">
                              <p className="truncate text-xs font-medium text-[#2D2926]">
                                {attachmentLabel}
                              </p>
                              {attachmentMeta ? (
                                <p className="mt-1 text-[11px] text-[#A39E99]">
                                  {attachmentMeta}
                                </p>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}

                  {hasTextContent ? (
                    <div
                      className="relative rounded-2xl px-5 py-3.5 text-sm leading-relaxed whitespace-pre-wrap break-words [overflow-wrap:anywhere]"
                      style={
                        isUser
                          ? {
                              background: "#5B7BA3",
                              color: "#FFFFFF",
                              borderBottomRightRadius: "6px",
                            }
                          : {
                              background: "#FFFFFF",
                              color: "#2D2926",
                              borderLeft: `3px solid ${agent?.themeColor || "#D9D2C8"}`,
                              borderBottomLeftRadius: "6px",
                              boxShadow: "var(--shadow-soft)",
                            }
                      }
                    >
                      {message.content}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
