import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AgentEditPage } from "../components/AgentEditPage";
import type { Agent, ModelConfig } from "../types/chat";

const agent: Agent = {
  id: "architect",
  name: "Architect",
  roleSummary: "结构化拆解",
  styleSummary: "偏框架化",
  systemPrompt: "你是 Architect。",
  avatar: "A",
  themeColor: "#D4A574",
  themeLight: "#F5E6D3",
  themeSoft: "#FAF3EC",
  modelConfigId: "model-openai",
  modelUnavailable: true,
};

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
  {
    id: "model-anthropic",
    provider: "anthropic",
    model: "claude-3-5-sonnet-latest",
    displayName: "Anthropic - claude-3-5-sonnet-latest",
    apiFormat: "anthropic_messages",
    baseUrl: "https://api.anthropic.com",
    useFullUrl: false,
    status: "available",
    apiKeyConfigured: true,
    supportsImageInput: true,
    supportsFileInput: false,
    supportsSystemPrompt: true,
    supportsStreaming: false,
    contextWindowInput: 200000,
    contextWindowOutput: 8192,
    maxImageCount: 5,
    maxImageSizeMb: 10,
    defaultTemperature: 0.7,
    createdAt: "2026-05-25T00:00:00.000Z",
    updatedAt: "2026-05-25T00:00:00.000Z",
  },
];

describe("AgentEditPage 模型绑定", () => {
  it("展示模型失效提示并允许重新绑定", () => {
    const onUpdateModelBinding = vi.fn();

    render(
      <AgentEditPage
        agent={agent}
        modelConfigs={modelConfigs}
        onBack={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onUpdateModelBinding={onUpdateModelBinding}
        onSave={vi.fn()}
      />
    );

    expect(screen.getByText("当前 Agent 绑定的模型已失效，请重新绑定一个可用模型后再继续发送消息。")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("当前模型"), {
      target: { value: "model-anthropic" },
    });

    expect(onUpdateModelBinding).toHaveBeenCalledWith("model-anthropic");
  });

  it("区分展示已删除的模型配置并提示重新绑定", () => {
    render(
      <AgentEditPage
        agent={{ ...agent, modelConfigId: "model-deleted" }}
        modelConfigs={modelConfigs}
        onBack={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onUpdateModelBinding={vi.fn()}
        onSave={vi.fn()}
      />
    );

    expect(
      screen.getByText("当前 Agent 绑定的模型配置已被删除，请重新绑定一个可用模型后再继续发送消息。")
    ).toBeInTheDocument();
    expect(screen.getByText("这个 Agent 仍保留原模型绑定记录，但对应模型配置已被删除。请重新选择一个可用模型。")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "已删除的模型配置（请重新绑定）" })).toBeDisabled();
  });
});
