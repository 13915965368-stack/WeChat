import type { Agent } from "../types/chat";

export const mockAgents: Agent[] = [
  {
    id: "architect",
    name: "Architect",
    roleSummary: "擅长结构化拆解与系统设计",
    styleSummary: "表达克制、偏框架化，习惯从整体到局部展开思路",
    systemPrompt: "你是一个偏系统性与结构化思考的智能助手。",
    avatar: "A",
    themeColor: "#D4A574",
    themeLight: "#F5E6D3",
    themeSoft: "#FAF3EC",
  },
  {
    id: "critic",
    name: "Critic",
    roleSummary: "擅长找风险、挑漏洞、做反向检验",
    styleSummary: "偏审慎、偏质疑，善于提出边界条件和反面论证",
    systemPrompt: "你是一个偏风险识别和问题质疑的智能助手。",
    avatar: "C",
    themeColor: "#C97B7B",
    themeLight: "#F5DEDE",
    themeSoft: "#FCF5F5",
  },
  {
    id: "writer",
    name: "Writer",
    roleSummary: "擅长表达、整理和改写",
    styleSummary: "偏自然、偏叙述，善于把复杂想法转化为流畅文字",
    systemPrompt: "你是一个偏表达整理和内容组织的智能助手。",
    avatar: "W",
    themeColor: "#7BA89C",
    themeLight: "#D4E8E2",
    themeSoft: "#F0F7F5",
  },
];
