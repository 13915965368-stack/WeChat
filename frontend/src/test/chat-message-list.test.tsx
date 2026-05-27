import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatMessageList } from "../components/ChatMessageList";
import type { Agent, Message } from "../types/chat";

const agents: Agent[] = [
  {
    id: "architect",
    name: "Architect",
    roleSummary: "擅长结构化拆解",
    styleSummary: "偏框架化",
    systemPrompt: "你是 Architect。",
    avatar: "A",
    themeColor: "#D4A574",
    themeLight: "#F5E6D3",
    themeSoft: "#FAF3EC",
  },
];

function createMessage(content: string): Message {
  return {
    id: "msg-1",
    conversationId: "direct-architect-default",
    senderType: "user",
    senderId: "user",
    content,
    createdAt: "2026-05-19T00:00:00.000Z",
  };
}

describe("ChatMessageList", () => {
  it("保留换行并为超长文本启用断行样式", () => {
    const content = `第一段内容\n第二段内容\n${"A".repeat(120)}`;

    render(
      <ChatMessageList
        messages={[createMessage(content)]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    const bubble = screen.getByText((_, element) => {
      return element?.textContent === content;
    });
    expect(bubble).toHaveClass("whitespace-pre-wrap");
    expect(bubble).toHaveClass("break-words");
    expect(bubble.className).toContain("[overflow-wrap:anywhere]");
    expect(bubble).toHaveTextContent("第一段内容");
    expect(bubble.textContent).toContain("第二段内容");
  });

  it("展示图片附件预览和元数据", () => {
    render(
      <ChatMessageList
        messages={[
          {
            ...createMessage("请看这张图"),
            attachments: [
              {
                id: "att-1",
                attachmentId: "att-1",
                type: "image",
                mimeType: "image/png",
                previewUrl: "/api/v1/attachments/images/att-1/preview",
                name: "wireframe.png",
                size: 2048,
              },
            ],
          },
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.getByAltText("wireframe.png")).toHaveAttribute(
      "src",
      "/api/v1/attachments/images/att-1/preview"
    );
    expect(screen.getByText("wireframe.png")).toBeInTheDocument();
    expect(screen.getByText("image/png · 2.0 KB")).toBeInTheDocument();
  });
});
