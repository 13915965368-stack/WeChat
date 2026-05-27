import type { Agent, AgentDto } from "../types/chat";

const defaultThemes: Record<string, Pick<Agent, "themeColor" | "themeLight" | "themeSoft">> = {
  architect: {
    themeColor: "#D4A574",
    themeLight: "#F5E6D3",
    themeSoft: "#FAF3EC",
  },
  critic: {
    themeColor: "#C97B7B",
    themeLight: "#F5DEDE",
    themeSoft: "#FCF5F5",
  },
  writer: {
    themeColor: "#7BA89C",
    themeLight: "#D4E8E2",
    themeSoft: "#F0F7F5",
  },
};

const fallbackTheme = {
  themeColor: "#5B7BA3",
  themeLight: "#DCE6F2",
  themeSoft: "#F4F8FC",
};

export function hydrateAgent(agent: AgentDto): Agent {
  const visualTheme = defaultThemes[agent.id] ?? fallbackTheme;

  return {
    ...agent,
    avatarImage: agent.avatarImage ?? undefined,
    themeColor: agent.themeColor ?? visualTheme.themeColor,
    themeLight: agent.themeLight ?? visualTheme.themeLight,
    themeSoft: agent.themeSoft ?? visualTheme.themeSoft,
  };
}
