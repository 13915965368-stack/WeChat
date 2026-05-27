import { describe, expect, it } from "vitest";
import { hydrateAgent } from "../data/agentVisualDefaults";
import type { AgentDto } from "../types/chat";

describe("Agent 适配层", () => {
  it("会为后端缺失的视觉字段补默认值", () => {
    const agent: AgentDto = {
      id: "architect",
      name: "Architect",
      roleSummary: "结构化拆解",
      styleSummary: "偏框架",
      systemPrompt: "你是 Architect",
      avatar: "A",
      avatarImage: null,
      themeColor: null,
      themeLight: null,
      themeSoft: null,
    };

    const hydrated = hydrateAgent(agent);

    expect(hydrated.themeColor).toBe("#D4A574");
    expect(hydrated.themeLight).toBe("#F5E6D3");
    expect(hydrated.themeSoft).toBe("#FAF3EC");
    expect(hydrated.avatarImage).toBeUndefined();
  });
});
