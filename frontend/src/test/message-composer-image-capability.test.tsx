import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MessageComposer } from "../components/MessageComposer";

describe("MessageComposer 图片能力", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:preview"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("图片能力禁用时展示原因", () => {
    render(
      <MessageComposer
        onSend={vi.fn()}
        canAttachImage={false}
        imageCapabilityReason="当前模型不支持图片输入。"
      />
    );

    expect(screen.getByLabelText("当前模型不支持图片输入")).toBeDisabled();
    expect(screen.getByText("当前模型不支持图片输入。")).toBeInTheDocument();
  });

  it("模型失效时禁用发送输入并展示原因", () => {
    render(
      <MessageComposer
        onSend={vi.fn()}
        canSend={false}
        sendDisabledReason="当前 Agent 绑定的模型已失效，请先重新绑定。"
      />
    );

    expect(screen.getByLabelText("消息输入")).toBeDisabled();
    expect(screen.getByLabelText("发送消息")).toBeDisabled();
    expect(screen.getByText("当前 Agent 绑定的模型已失效，请先重新绑定。")).toBeInTheDocument();
  });

  it("已选图片会随发送一起提交", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);

    render(
      <MessageComposer
        onSend={onSend}
        canAttachImage
        maxImageCount={3}
        maxImageSizeMb={10}
      />
    );

    const file = new File(["image-bytes"], "demo.png", { type: "image/png" });
    const imageInput = document.querySelector('input[type="file"][accept="image/*"]') as HTMLInputElement;

    fireEvent.change(imageInput, { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("消息输入"), { target: { value: "带图消息" } });
    fireEvent.click(screen.getByLabelText("发送消息"));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith("带图消息", [file], undefined);
    });

    expect(screen.queryByAltText("demo.png")).not.toBeInTheDocument();
  });

  it("单聊下展示 thinking 开关并透传当前状态", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);

    render(
      <MessageComposer
        onSend={onSend}
        showThinkingToggle
        thinkingEnabled
      />
    );

    fireEvent.change(screen.getByLabelText("消息输入"), { target: { value: "带 thinking 的消息" } });
    fireEvent.click(screen.getByLabelText("已开启 thinking"));

    expect(screen.getByLabelText("已开启 thinking")).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByLabelText("发送消息"));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith("带 thinking 的消息", [], {
        thinkingEnabled: true,
      });
    });
  });

  it("群聊下不展示 thinking 开关", () => {
    render(<MessageComposer onSend={vi.fn()} showThinkingToggle={false} />);

    expect(screen.queryByText("Think")).not.toBeInTheDocument();
  });
});
