import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsPanel } from "../components/SettingsPanel";
import type { ModelConfig } from "../types/chat";

const modelConfigs: ModelConfig[] = [
  {
    id: "model-openai",
    provider: "openai",
    model: "gpt-4o",
    displayName: "OpenAI - gpt-4o",
    apiFormat: "openai_chat",
    baseUrl: "https://api.openai.com/v1",
    useFullUrl: false,
    status: "available",
    apiKeyConfigured: true,
    supportsImageInput: true,
    supportsFileInput: false,
    supportsSystemPrompt: true,
    supportsStreaming: false,
    contextWindowInput: 128000,
    contextWindowOutput: 8192,
    maxImageCount: 5,
    maxImageSizeMb: 10,
    defaultTemperature: 0.7,
    createdAt: "2026-05-25T00:00:00.000Z",
    updatedAt: "2026-05-25T00:00:00.000Z",
  },
];

describe("SettingsPanel 模型管理", () => {
  it("展示模型统计和列表内容", () => {
    render(
      <SettingsPanel
        isOpen
        onClose={vi.fn()}
        modelConfigs={modelConfigs}
        isLoading={false}
        onCreateModelConfig={vi.fn()}
        onUpdateModelConfig={vi.fn()}
        onValidateModelConfig={vi.fn()}
        onDeleteModelConfig={vi.fn()}
        impactedAgentsByModelConfigId={{}}
      />
    );

    expect(screen.getByText("模型管理")).toBeInTheDocument();
    expect(screen.getByText("OpenAI - gpt-4o")).toBeInTheDocument();
    expect(screen.getAllByText("支持图片").length).toBeGreaterThan(0);
  });

  it("删除前会展示受影响 Agent 提示", () => {
    render(
      <SettingsPanel
        isOpen
        onClose={vi.fn()}
        modelConfigs={modelConfigs}
        isLoading={false}
        onCreateModelConfig={vi.fn()}
        onUpdateModelConfig={vi.fn()}
        onValidateModelConfig={vi.fn()}
        onDeleteModelConfig={vi.fn()}
        impactedAgentsByModelConfigId={{ "model-openai": ["Architect", "Writer"] }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    expect(screen.getByText("确认删除模型")).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "• Architect")).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "• Writer")).toBeInTheDocument();
  });
});
