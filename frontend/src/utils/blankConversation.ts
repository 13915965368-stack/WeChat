import type { Agent, Conversation } from "../types/chat";

const LEGACY_BLANK_TEMPLATE_IDS = new Set(["blank-agent", "blank_agent"]);

export function isBlankTemplateAgent(agent: Pick<Agent, "id" | "isTemplate" | "systemPrompt"> | null | undefined) {
  if (!agent) {
    return false;
  }

  if (LEGACY_BLANK_TEMPLATE_IDS.has(agent.id)) {
    return true;
  }

  return agent.isTemplate === true && agent.systemPrompt.trim() === "";
}

export function findBlankTemplateAgent(agents: Agent[]) {
  return agents.find((agent) => isBlankTemplateAgent(agent)) ?? null;
}

export function resolveConversationModelConfigId(
  conversation: Conversation | null,
  targetAgent: Agent | null
) {
  if (conversation?.type === "direct" && isBlankTemplateAgent(targetAgent)) {
    return conversation.modelConfigId ?? null;
  }

  return conversation?.modelConfigId ?? targetAgent?.modelConfigId ?? null;
}
