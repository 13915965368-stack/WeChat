import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModelConfigModal } from "../components/ModelConfigModal";
import type { ModelConfig } from "../types/chat";

function renderModal(editingModel?: ModelConfig | null) {
  const onSubmit = vi.fn();

  render(
    <ModelConfigModal
      isOpen
      editingModel={editingModel}
      isSaving={false}
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />
  );

  return { onSubmit };
}

describe("ModelConfigModal provider presets", () => {
  it("展示 7 家模型服务商预设", () => {
    renderModal();

    const [providerSelect] = screen.getAllByRole("combobox");
    const optionLabels = Array.from(providerSelect.querySelectorAll("option")).map((option) => option.textContent);

    expect(optionLabels).toEqual([
      "OpenAI",
      "DeepSeek",
      "GLM（智谱）",
      "Kimi（月之暗面）",
      "Gemini",
      "MiniMax",
      "Qwen（通义千问）",
    ]);
  });

  it("切换服务商时会自动回填默认地址和模型", () => {
    const { onSubmit } = renderModal();

    const [providerSelect, modelSelect] = screen.getAllByRole("combobox");
    fireEvent.change(providerSelect, { target: { value: "qwen" } });
    fireEvent.change(screen.getByPlaceholderText("输入 API 密钥"), {
      target: { value: "test-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "添加模型" }));

    expect(modelSelect).toHaveValue("qwen-plus");
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: "qwen",
        model: "qwen-plus",
        baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
        apiFormat: "openai_chat",
        apiKey: "test-key",
      }),
      undefined
    );
  });

  it("自定义配置按 apiFormat 提交正确 provider", () => {
    const { onSubmit } = renderModal();

    fireEvent.click(screen.getByRole("button", { name: "自定义配置" }));

    const [apiFormatSelect] = screen.getAllByRole("combobox");
    fireEvent.change(apiFormatSelect, { target: { value: "gemini_generate_content" } });
    fireEvent.change(screen.getByPlaceholderText("https://api.example.com/v1"), {
      target: { value: "https://generativelanguage.googleapis.com/v1beta" },
    });
    fireEvent.change(screen.getByPlaceholderText("输入模型 ID"), {
      target: { value: "gemini-2.5-flash" },
    });
    fireEvent.change(screen.getByPlaceholderText("输入 API 密钥"), {
      target: { value: "test-key" },
    });

    fireEvent.click(screen.getByRole("button", { name: "添加模型" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: "gemini",
        apiFormat: "gemini_generate_content",
        model: "gemini-2.5-flash",
        baseUrl: "https://generativelanguage.googleapis.com/v1beta",
        apiKey: "test-key",
      }),
      undefined
    );
  });

  it("编辑已有模型时不回显旧 API 密钥", () => {
    renderModal({
      id: "model-deepseek",
      provider: "deepseek",
      model: "deepseek-chat",
      displayName: "DeepSeek - deepseek-chat",
      apiFormat: "openai_chat",
      baseUrl: "https://api.deepseek.com/v1",
      useFullUrl: false,
      status: "available",
      apiKeyConfigured: true,
      supportsImageInput: false,
      supportsFileInput: false,
      supportsSystemPrompt: true,
      supportsStreaming: false,
      contextWindowInput: 64000,
      contextWindowOutput: 8000,
      maxImageCount: null,
      maxImageSizeMb: null,
      defaultTemperature: 0.7,
      lastValidatedAt: "2026-05-27T00:00:00.000Z",
      createdAt: "2026-05-27T00:00:00.000Z",
      updatedAt: "2026-05-27T00:00:00.000Z",
    });

    const apiKeyInput = screen.getByPlaceholderText("已配置，如需覆盖请重新输入") as HTMLInputElement;
    expect(apiKeyInput.value).toBe("");
  });
});
