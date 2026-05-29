import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatMessageList } from "../components/ChatMessageList";
import type { Agent, Message } from "../types/chat";
import { normalizeMarkdownBlocks } from "../utils/messageContent";

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

function createMessage(content: string, overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    conversationId: "direct-architect-default",
    senderType: "user",
    senderId: "user",
    content,
    renderFormat: "plain_text",
    createdAt: "2026-05-19T00:00:00.000Z",
    ...overrides,
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

    const bubble = document.querySelector(".whitespace-pre-wrap.break-words") as HTMLElement;
    expect(bubble).not.toBeNull();
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

  it("按 Markdown 渲染标题、列表、引用、代码块、表格、链接和任务列表，并清理 think 标签", () => {
    render(
      <ChatMessageList
        messages={[
          createMessage(
            "# 结论\n\n- 第一项\n- 第二项\n\n> 引用结论\n\n```ts\nconst answer = 42;\n```\n\n| 列 | 值 |\n| --- | --- |\n| 类型 | Markdown |\n\n- [x] 已完成\n\n这是 **重点** 段落，查看 [详情](https://example.com)。\n<think>不应展示</think>",
            {
              senderType: "agent",
              senderId: "architect",
              renderFormat: "markdown",
            }
          ),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.getByRole("heading", { name: "结论" })).toBeInTheDocument();
    expect(screen.getByText("第一项")).toBeInTheDocument();
    expect(screen.getByText("第二项")).toBeInTheDocument();
    expect(screen.getByText("引用结论").closest("blockquote")?.tagName).toBe("BLOCKQUOTE");
    expect(screen.getByText("const answer = 42;").tagName).toBe("CODE");
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "列" })).toBeInTheDocument();
    expect(screen.getByText("Markdown")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "详情" })).toHaveAttribute("href", "https://example.com");
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.getByText("重点").tagName).toBe("STRONG");
    expect(screen.getByText(/这是/)).toBeInTheDocument();
    expect(screen.queryByText("不应展示")).not.toBeInTheDocument();
  });

  it("弱结构 Markdown 会保留标题和列表，并把单换行渲染为可读断行", () => {
    const { container } = render(
      <ChatMessageList
        messages={[
          createMessage("### 方案概览\n第一行说明\n第二行说明\n- 第一项\n- 第二项", {
            senderType: "agent",
            senderId: "architect",
            renderFormat: "markdown",
          }),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.getByRole("heading", { name: "方案概览" })).toBeInTheDocument();
    expect(screen.getByText("第一项")).toBeInTheDocument();
    expect(screen.getByText("第二项")).toBeInTheDocument();
    const paragraph = container.querySelector("p");
    expect(paragraph).not.toBeNull();
    expect(paragraph).toHaveTextContent("第一行说明");
    expect(paragraph).toHaveTextContent("第二行说明");
    expect(paragraph?.querySelectorAll("br").length).toBeGreaterThan(0);
  });

  it("无空行的标题与表格会先被规范化，再渲染为块级结构", () => {
    render(
      <ChatMessageList
        messages={[
          createMessage("导语\n## 事件背景\n这里是说明\n| 项目 | 内容 |\n| --- | --- |\n| 时间 | 今天 |", {
            senderType: "agent",
            senderId: "architect",
            renderFormat: "markdown",
          }),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.getByRole("heading", { name: "事件背景" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "今天" })).toBeInTheDocument();
  });

  it("块级规范化会跳过代码围栏，不误伤代码中的标题和表格符号", () => {
    const normalized = normalizeMarkdownBlocks(
      "```md\n## 假标题\n| 列 | 值 |\n| --- | --- |\n| A | B |\n```\n结尾说明"
    );

    expect(normalized).toBe("```md\n## 假标题\n| 列 | 值 |\n| --- | --- |\n| A | B |\n```\n结尾说明");
  });

  it("不完整的表格语法会按普通文本退化展示，不伪装成正常表格", () => {
    const { container } = render(
      <ChatMessageList
        messages={[
          createMessage("表格预览如下\n| 列 | 值 |\n| 类型 | Markdown |", {
            senderType: "agent",
            senderId: "architect",
            renderFormat: "markdown",
          }),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(container).toHaveTextContent("表格预览如下");
    expect(container).toHaveTextContent("| 列 | 值 |");
    expect(container).toHaveTextContent("| 类型 | Markdown |");
  });

  it("纯文本消息也会清理 think 标签，不把推理内容混入正文", () => {
    render(
      <ChatMessageList
        messages={[
          createMessage("<think>隐藏推理</think>\n保留正文", {
            senderType: "agent",
            senderId: "architect",
            renderFormat: "plain_text",
          }),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.getByText("保留正文")).toBeInTheDocument();
    expect(screen.queryByText("隐藏推理")).not.toBeInTheDocument();
  });

  it("默认折叠 thinking，并允许展开和收起", () => {
    render(
      <ChatMessageList
        messages={[
          createMessage("正文内容", {
            senderType: "agent",
            senderId: "architect",
            renderFormat: "markdown",
            thinking: {
              available: true,
              content: "这里是思考过程",
              defaultCollapsed: true,
            },
          }),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.queryByText("这里是思考过程")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "展开思考过程" }));
    expect(screen.getByText("这里是思考过程")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "收起思考过程" }));
    expect(screen.queryByText("这里是思考过程")).not.toBeInTheDocument();
  });

  it("thinking 为空时不展示折叠区，usage 通过 hover/focus 展示明细", () => {
    render(
      <ChatMessageList
        messages={[
          createMessage("正文内容", {
            senderType: "agent",
            senderId: "architect",
            renderFormat: "markdown",
            thinking: {
              available: true,
              content: "",
              defaultCollapsed: true,
            },
            usage: {
              promptTokens: 12,
              completionTokens: 18,
              totalTokens: 30,
            },
          }),
        ]}
        agents={agents}
        activeAgentName="Architect"
        activeAgentId="architect"
      />
    );

    expect(screen.queryByText("思考过程")).not.toBeInTheDocument();
    const trigger = screen.getByRole("button", { name: "查看 Usage 明细" });
    const tooltip = screen.getByRole("tooltip", { hidden: true });

    expect(screen.getByText("Usage · 总 30 tokens")).toBeInTheDocument();
    expect(tooltip).toHaveAttribute("aria-hidden", "true");

    fireEvent.focus(trigger);

    expect(tooltip).toHaveAttribute("aria-hidden", "false");
    expect(screen.getByText("输入 12")).toBeInTheDocument();
    expect(screen.getByText("输出 18")).toBeInTheDocument();
    expect(screen.getByText("总计 30")).toBeInTheDocument();
  });
});
