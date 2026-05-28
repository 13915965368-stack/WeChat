import { useMemo, useState, useRef, useCallback, useEffect } from "react";
import { AgentProfilePanel } from "./components/AgentProfilePanel";
import { AgentDetailPage } from "./components/AgentDetailPage";
import { AgentEditPage } from "./components/AgentEditPage";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { ChatMessageList } from "./components/ChatMessageList";
import { MessageComposer } from "./components/MessageComposer";
import { GroupMemberPanel } from "./components/GroupMemberPanel";
import { CreateGroupModal } from "./components/CreateGroupModal";
import { ToolPanel, useToolActivities } from "./components/ToolPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { ModelPickerModal } from "./components/ModelPickerModal";
import { ToastViewport, type ToastItem } from "./components/ToastViewport";
import { CreateAgentModal, type CreateAgentPayload } from "./components/CreateAgentModal";
import { ApiError } from "./api/client";
import {
  bulkDeleteConversations,
  createAgent,
  createModelConfig,
  createDirectConversation,
  createGroupConversation,
  deleteModelConfig,
  deleteConversation,
  getAgents,
  getConversations,
  getMessages,
  getModelConfigs,
  sendGroupMessageStream,
  sendMessage,
  updateAgentModelBinding,
  updateAgent,
  updateModelConfig,
  updateAgentPin,
  updateConversationPin,
  uploadImageAttachment,
  validateModelConfig,
} from "./api/chat";
import { hydrateAgent } from "./data/agentVisualDefaults";
import type { Agent, AgentDto, Attachment, Conversation, Message, ModelConfig, ModelConfigPayload } from "./types/chat";
import { findBlankTemplateAgent, resolveConversationModelConfigId } from "./utils/blankConversation";
import { mergeMessageList, replaceOptimisticMessage } from "./utils/messageFlow";

type MiddlePanelState =
  | { type: "profile" }
  | { type: "groupMembers" }
  | { type: "agentDetail"; agentId: string }
  | { type: "agentEdit"; agentId: string };

type PendingReply = {
  timeoutId: ReturnType<typeof setTimeout>;
  flush: () => void;
};

type ComposerTargetAgent = Agent | null;

const BUSINESS_ERROR_MESSAGES: Record<string, string> = {
  IMAGE_NOT_SUPPORTED: "当前模型不支持图片输入，请切换到支持图片的模型后再试。",
};
const DEFAULT_HISTORY_MIGRATION_ROUNDS = 1;
const MESSAGE_PAGE_SIZE = 100;

function upsertConversation(list: Conversation[], conversation: Conversation, prepend = false) {
  const others = list.filter((item) => item.id !== conversation.id);
  return prepend ? [conversation, ...others] : [...others, conversation];
}

function upsertModelConfig(list: ModelConfig[], modelConfig: ModelConfig) {
  const others = list.filter((item) => item.id !== modelConfig.id);
  return [modelConfig, ...others].sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
  );
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.code) {
    return BUSINESS_ERROR_MESSAGES[error.code] ?? error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

async function loadHydratedAgents() {
  const rawAgents = await getAgents();
  return rawAgents.map(hydrateAgent);
}

async function loadConversationMessages(conversationId: string) {
  const loadedMessages: Message[] = [];
  let offset = 0;

  while (true) {
    const page = await getMessages(conversationId, MESSAGE_PAGE_SIZE, offset);
    loadedMessages.push(...page);
    if (page.length < MESSAGE_PAGE_SIZE) {
      break;
    }
    offset += MESSAGE_PAGE_SIZE;
  }

  return loadedMessages;
}

function sortConversations(list: Conversation[]): Conversation[] {
  return [...list].sort((left, right) => {
    if (!!left.pinned !== !!right.pinned) {
      return left.pinned ? -1 : 1;
    }
    if (left.pinned && right.pinned) {
      const leftPinnedAt = left.pinnedAt ? new Date(left.pinnedAt).getTime() : 0;
      const rightPinnedAt = right.pinnedAt ? new Date(right.pinnedAt).getTime() : 0;
      if (leftPinnedAt !== rightPinnedAt) {
        return rightPinnedAt - leftPinnedAt;
      }
    }
    return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
  });
}

function sortAgentsForDisplay(list: Agent[]): Agent[] {
  return list
    .filter((agent) => !agent.isTemplate)
    .map((agent, index) => ({ agent, index }))
    .sort((left, right) => {
      if (!!left.agent.pinned !== !!right.agent.pinned) {
        return left.agent.pinned ? -1 : 1;
      }
      if (left.agent.pinned && right.agent.pinned) {
        const leftPinnedAt = left.agent.pinnedAt ? new Date(left.agent.pinnedAt).getTime() : 0;
        const rightPinnedAt = right.agent.pinnedAt ? new Date(right.agent.pinnedAt).getTime() : 0;
        if (leftPinnedAt !== rightPinnedAt) {
          return rightPinnedAt - leftPinnedAt;
        }
      }
      return left.index - right.index;
    })
    .map(({ agent }) => agent);
}

function getPrimaryAgentId(list: Agent[]): string {
  return sortAgentsForDisplay(list)[0]?.id ?? "";
}

export default function App() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string>("");
  const [activeAgentId, setActiveAgentId] = useState<string>("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createModalMode, setCreateModalMode] = useState<"blank" | "context">("blank");
  const [middlePanel, setMiddlePanel] = useState<MiddlePanelState>({ type: "profile" });
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const { activities: toolActivities, handleToolCall, handleToolResult, clearActivities } = useToolActivities();
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false);
  const [isCreatingBlankConversation, setIsCreatingBlankConversation] = useState(false);
  const [isCreateAgentModalOpen, setIsCreateAgentModalOpen] = useState(false);
  const [isCreatingAgent, setIsCreatingAgent] = useState(false);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isModelConfigsLoading, setIsModelConfigsLoading] = useState(true);
  const [modelConfigError, setModelConfigError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pendingTimeoutsRef = useRef<PendingReply[]>([]);
  const activeConversationIdRef = useRef(activeConversationId);
  const toastTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  const clearPendingReplies = useCallback(() => {
    pendingTimeoutsRef.current.forEach(({ timeoutId, flush }) => {
      clearTimeout(timeoutId);
      flush();
    });
    pendingTimeoutsRef.current = [];
  }, []);

  const dismissToast = useCallback((toastId: string) => {
    const timer = toastTimersRef.current[toastId];
    if (timer) {
      clearTimeout(timer);
      delete toastTimersRef.current[toastId];
    }
    setToasts((prev) => prev.filter((toast) => toast.id !== toastId));
  }, []);

  const pushToast = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, ...toast }]);
      toastTimersRef.current[id] = setTimeout(() => {
        dismissToast(id);
      }, 3200);
    },
    [dismissToast]
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setIsBootstrapping(true);
      setErrorMessage(null);

      try {
        setIsModelConfigsLoading(true);
        setModelConfigError(null);

        const [hydratedAgents, loadedConversations, loadedModelConfigs] = await Promise.all([
          loadHydratedAgents(),
          getConversations(),
          getModelConfigs().catch((error) => {
            if (!cancelled) {
              setModelConfigError(getErrorMessage(error, "读取模型配置失败"));
            }
            return [];
          }),
        ]);
        if (cancelled) return;

        const messagesByConversation = await Promise.all(
          loadedConversations.map((conversation) =>
            getMessages(conversation.id).catch(() => [])
          )
        );
        if (cancelled) return;

        const loadedMessages = messagesByConversation.flat();
        const primaryAgentId = getPrimaryAgentId(hydratedAgents);

        setAgents(hydratedAgents);
        setModelConfigs(loadedModelConfigs);
        setConversations(loadedConversations);
        setMessages(loadedMessages);
        setActiveConversationId("");
        setActiveAgentId(primaryAgentId);
        setMiddlePanel({ type: "profile" });
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(getErrorMessage(error, "初始化数据失败，请确认后端已启动"));
        }
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
          setIsModelConfigsLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
      clearPendingReplies();
      Object.values(toastTimersRef.current).forEach((timer) => clearTimeout(timer));
    };
  }, [clearPendingReplies]);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? null,
    [activeConversationId, conversations]
  );

  const activeAgent = useMemo(
    () => agents.find((agent) => agent.id === activeAgentId) ?? agents[0] ?? null,
    [activeAgentId, agents]
  );

  const blankTemplateAgent = useMemo(
    () => findBlankTemplateAgent(agents),
    [agents]
  );

  const availableModelConfigs = useMemo(
    () => modelConfigs.filter((modelConfig) => modelConfig.status === "available"),
    [modelConfigs]
  );

  const impactedAgentsByModelConfigId = useMemo(() => {
    return agents.reduce<Record<string, string[]>>((acc, agent) => {
      if (agent.isTemplate) return acc;
      if (!agent.modelConfigId) return acc;
      if (!acc[agent.modelConfigId]) {
        acc[agent.modelConfigId] = [];
      }
      acc[agent.modelConfigId].push(agent.name);
      return acc;
    }, {});
  }, [agents]);

  const visibleAgents = useMemo(
    () => agents.filter((agent) => !agent.isTemplate),
    [agents]
  );

  const recentConversations = useMemo(
    () => sortConversations(conversations).slice(0, 4),
    [conversations]
  );

  const currentMessages = useMemo(
    () =>
      messages
        .filter((message) => message.conversationId === activeConversationId)
        .sort(
          (left, right) =>
            new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime()
        ),
    [messages, activeConversationId]
  );

  const currentDirectAgentId = useMemo(() => {
    if (activeConversation?.type === "direct" && activeConversation.agentId) {
      return activeConversation.agentId;
    }
    return activeAgentId || null;
  }, [activeAgentId, activeConversation]);

  const directConversationAgent = useMemo<ComposerTargetAgent>(() => {
    if (activeConversation?.type === "direct" && activeConversation.agentId) {
      return agents.find((agent) => agent.id === activeConversation.agentId) ?? null;
    }
    return null;
  }, [activeConversation, agents]);

  const activeConversationModelConfig = useMemo(() => {
    const modelConfigId = resolveConversationModelConfigId(activeConversation, directConversationAgent);
    if (!modelConfigId) return null;
    return (
      modelConfigs.find((modelConfig) => modelConfig.id === modelConfigId) ??
      null
    );
  }, [activeConversation, directConversationAgent, modelConfigs]);

  const groupConversationAgents = useMemo(() => {
    if (activeConversation?.type !== "group") {
      return [];
    }
    return activeConversation.memberIds
      .filter((memberId) => memberId !== "user")
      .map((memberId) => agents.find((agent) => agent.id === memberId) ?? null)
      .filter((agent): agent is Agent => agent !== null);
  }, [activeConversation, agents]);

  const groupConversationModelConfigs = useMemo(() => {
    if (activeConversation?.type !== "group") {
      return [];
    }
    return groupConversationAgents.map((agent) => {
      const modelConfigId = resolveConversationModelConfigId(activeConversation, agent);
      const modelConfig = modelConfigId
        ? modelConfigs.find((item) => item.id === modelConfigId) ?? null
        : null;
      return {
        agent,
        modelConfigId,
        modelConfig,
      };
    });
  }, [activeConversation, groupConversationAgents, modelConfigs]);

  const sendCapability = useMemo(() => {
    if (!activeConversation) {
      return { enabled: false, reason: "请先进入一个可发送的会话。" };
    }
    if (activeConversation.type === "group") {
      if (groupConversationAgents.length === 0) {
        return { enabled: false, reason: "当前群聊还没有可用的 Agent 成员。" };
      }

      const missingBinding = groupConversationModelConfigs.find((entry) => !entry.modelConfigId);
      if (missingBinding) {
        return {
          enabled: false,
          reason: `${missingBinding.agent.name} 尚未绑定模型，请先补齐后再发送。`,
        };
      }

      const unavailableAgent = groupConversationModelConfigs.find(
        (entry) => entry.agent.modelUnavailable && !activeConversation.modelConfigId
      );
      if (unavailableAgent) {
        return {
          enabled: false,
          reason: `${unavailableAgent.agent.name} 绑定的模型已失效，请先重新绑定。`,
        };
      }

      const deletedModel = groupConversationModelConfigs.find((entry) => !entry.modelConfig);
      if (deletedModel) {
        return {
          enabled: false,
          reason: `${deletedModel.agent.name} 的模型配置不存在或已被删除，请先重新绑定。`,
        };
      }

      const unavailableModel = groupConversationModelConfigs.find(
        (entry) => entry.modelConfig?.status !== "available"
      );
      if (unavailableModel) {
        return {
          enabled: false,
          reason: `${unavailableModel.agent.name} 的模型暂不可用，请先校验或更换模型。`,
        };
      }

      return { enabled: true, reason: undefined };
    }

    const resolvedModelConfigId = resolveConversationModelConfigId(activeConversation, directConversationAgent);
    if (!directConversationAgent) {
      return { enabled: false, reason: "请先进入一个可发送的会话。" };
    }
    if (!resolvedModelConfigId) {
      return { enabled: false, reason: "请先为当前会话绑定模型。" };
    }
    if (directConversationAgent.modelUnavailable && !activeConversation.modelConfigId) {
      return { enabled: false, reason: "当前 Agent 绑定的模型已失效，请先重新绑定。" };
    }
    if (!activeConversationModelConfig) {
      return { enabled: false, reason: "当前模型配置不存在或已被删除，请先重新绑定。" };
    }
    if (activeConversationModelConfig.status !== "available") {
      return { enabled: false, reason: "当前模型暂不可用，请先校验或更换模型。" };
    }
    return { enabled: true, reason: undefined };
  }, [
    activeConversation,
    activeConversationModelConfig,
    directConversationAgent,
    groupConversationAgents.length,
    groupConversationModelConfigs,
  ]);

  const imageCapability = useMemo(() => {
    if (!sendCapability.enabled) {
      return sendCapability;
    }
    if (activeConversation?.type === "group") {
      const unsupportedAgent = groupConversationModelConfigs.find(
        (entry) => !entry.modelConfig?.supportsImageInput
      );
      if (unsupportedAgent) {
        return {
          enabled: false,
          reason: `${unsupportedAgent.agent.name} 当前模型不支持图片输入。`,
        };
      }
      return { enabled: true, reason: undefined };
    }
    if (!activeConversationModelConfig) {
      return { enabled: false, reason: "当前模型配置不存在或已被删除，请先重新绑定。" };
    }
    if (!activeConversationModelConfig.supportsImageInput) {
      return { enabled: false, reason: "当前模型不支持图片输入。" };
    }
    return { enabled: true, reason: undefined };
  }, [activeConversation, activeConversationModelConfig, groupConversationModelConfigs, sendCapability]);

  const groupImageLimits = useMemo(() => {
    if (activeConversation?.type !== "group") {
      return {
        maxImageCount: activeConversationModelConfig?.maxImageCount ?? 5,
        maxImageSizeMb: activeConversationModelConfig?.maxImageSizeMb ?? 10,
      };
    }

    const maxImageCount = groupConversationModelConfigs.reduce<number | null>((minValue, entry) => {
      const nextValue = entry.modelConfig?.maxImageCount ?? null;
      if (nextValue === null) {
        return minValue;
      }
      if (minValue === null) {
        return nextValue;
      }
      return Math.min(minValue, nextValue);
    }, null);

    const maxImageSizeMb = groupConversationModelConfigs.reduce<number | null>((minValue, entry) => {
      const nextValue = entry.modelConfig?.maxImageSizeMb ?? null;
      if (nextValue === null) {
        return minValue;
      }
      if (minValue === null) {
        return nextValue;
      }
      return Math.min(minValue, nextValue);
    }, null);

    return {
      maxImageCount: maxImageCount ?? 5,
      maxImageSizeMb: maxImageSizeMb ?? 10,
    };
  }, [activeConversation, activeConversationModelConfig, groupConversationModelConfigs]);

  async function refreshAgentsAfterModelMutation() {
    try {
      setAgents(await loadHydratedAgents());
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "刷新 Agent 状态失败"));
    }
  }

  function handleSelectConversation(id: string) {
    clearPendingReplies();
    setActiveConversationId(id);
    const conversation = conversations.find((item) => item.id === id);
    if (!conversation) return;

    if (conversation.type === "direct" && conversation.agentId) {
      setActiveAgentId(conversation.agentId);
      setMiddlePanel({ type: "profile" });
      return;
    }

    if (conversation.type === "group") {
      const firstAgentId = conversation.memberIds.find((memberId) => memberId !== "user");
      if (firstAgentId) {
        setActiveAgentId(firstAgentId);
      }
      setMiddlePanel({ type: "groupMembers" });
    }
  }

  async function handleSelectAgent(agentId: string) {
    clearPendingReplies();
    setErrorMessage(null);

    const recentDirectConversation = conversations
      .filter((conversation) => conversation.type === "direct" && conversation.agentId === agentId)
      .sort(
        (left, right) =>
          new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
      )[0];

    if (recentDirectConversation) {
      handleSelectConversation(recentDirectConversation.id);
      return;
    }

    try {
      const conversation = await createDirectConversation(agentId);
      setConversations((prev) => upsertConversation(prev, conversation, true));
      setActiveConversationId(conversation.id);
      setActiveAgentId(agentId);
      setMiddlePanel({ type: "profile" });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "创建单聊失败"));
    }
  }

  async function handleNewDirectConversation(agentId: string) {
    clearPendingReplies();
    setErrorMessage(null);

    try {
      const conversation = await createDirectConversation(agentId);
      setConversations((prev) => upsertConversation(prev, conversation, true));
      setActiveConversationId(conversation.id);
      setActiveAgentId(agentId);
      setMiddlePanel({ type: "profile" });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "创建单聊失败"));
    }
  }

  function handleViewAgentDetail(agentId: string) {
    setActiveAgentId(agentId);
    setMiddlePanel({ type: "agentDetail", agentId });
  }

  async function handleSaveAgent(agentId: string, updates: Partial<Agent>) {
    const currentAgent = agents.find((agent) => agent.id === agentId);
    if (!currentAgent) return;

    const nextAgent: Agent = { ...currentAgent, ...updates };
    const payload: AgentDto = {
      id: nextAgent.id,
      name: nextAgent.name,
      roleSummary: nextAgent.roleSummary,
      styleSummary: nextAgent.styleSummary,
      systemPrompt: nextAgent.systemPrompt,
      avatar: nextAgent.avatar,
      avatarImage: nextAgent.avatarImage ?? null,
      themeColor: nextAgent.themeColor,
      themeLight: nextAgent.themeLight,
      themeSoft: nextAgent.themeSoft,
    };

    const updated = await updateAgent(agentId, payload);
    const hydrated = hydrateAgent(updated);
    setAgents((prev) =>
      prev.map((agent) => (agent.id === agentId ? hydrated : agent))
    );
  }

  async function handleUpdateAgentBinding(agentId: string, modelConfigId: string | null) {
    const updated = hydrateAgent(await updateAgentModelBinding(agentId, modelConfigId));
    setAgents((prev) => prev.map((agent) => (agent.id === agentId ? updated : agent)));
    const boundModel = modelConfigs.find((modelConfig) => modelConfig.id === modelConfigId);
    pushToast({
      title: "模型绑定已更新",
      description: boundModel
        ? `当前 Agent 已切换到 ${boundModel.provider} - ${boundModel.model}。`
        : "当前 Agent 已取消模型绑定。",
      tone: "success",
    });
  }

  async function handleCreateAgent(payload: CreateAgentPayload) {
    setIsCreatingAgent(true);
    setErrorMessage(null);
    try {
      const createdAgent = hydrateAgent(
        await createAgent({
          name: payload.name,
          roleSummary: payload.roleSummary,
          styleSummary: payload.styleSummary,
          systemPrompt: payload.systemPrompt,
          avatar: payload.name.trim().charAt(0).toUpperCase() || "A",
          modelConfigId: payload.modelConfigId,
        })
      );

      setAgents((prev) => [...prev, createdAgent]);
      setIsCreateAgentModalOpen(false);
      pushToast({
        title: "Agent 已创建",
        description: `${createdAgent.name} 已加入左侧列表，并已打开它的对话入口。`,
        tone: "success",
      });
      await handleNewDirectConversation(createdAgent.id);
    } catch (error) {
      const message = getErrorMessage(error, "创建 Agent 失败");
      setErrorMessage(message);
      pushToast({ title: "创建 Agent 失败", description: message, tone: "error" });
    } finally {
      setIsCreatingAgent(false);
    }
  }

  async function handleCreateModelConfig(payload: ModelConfigPayload) {
    setModelConfigError(null);
    try {
      const modelConfig = await createModelConfig(payload);
      setModelConfigs((prev) => upsertModelConfig(prev, modelConfig));
      pushToast({
        title: "模型已保存",
        description:
          modelConfig.status === "available"
            ? "模型连接已可用。"
            : "模型已加入列表，当前状态会继续展示。",
        tone: modelConfig.status === "failed" ? "warning" : "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "保存模型失败");
      setModelConfigError(message);
      pushToast({ title: "保存模型失败", description: message, tone: "error" });
      throw error;
    }
  }

  async function handleUpdateModelConfig(id: string, payload: Partial<ModelConfigPayload>) {
    setModelConfigError(null);
    try {
      const modelConfig = await updateModelConfig(id, payload);
      setModelConfigs((prev) => upsertModelConfig(prev, modelConfig));
      await refreshAgentsAfterModelMutation();
      pushToast({
        title: "模型已更新",
        description: "变更已保存，最新状态已同步到列表。",
        tone: "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "更新模型失败");
      setModelConfigError(message);
      pushToast({ title: "更新模型失败", description: message, tone: "error" });
      throw error;
    }
  }

  async function handleValidateModelConfig(id: string) {
    try {
      const modelConfig = await validateModelConfig(id);
      setModelConfigs((prev) => upsertModelConfig(prev, modelConfig));
      await refreshAgentsAfterModelMutation();
      pushToast({
        title: modelConfig.status === "available" ? "模型校验成功" : "模型校验完成",
        description:
          modelConfig.status === "failed"
            ? modelConfig.statusMessage ?? "当前连接仍不可用。"
            : "模型状态已更新。",
        tone: modelConfig.status === "failed" ? "warning" : "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "校验模型失败");
      setModelConfigError(message);
      pushToast({ title: "校验模型失败", description: message, tone: "error" });
    }
  }

  async function handleDeleteModelConfig(id: string) {
    try {
      await deleteModelConfig(id);
      setModelConfigs((prev) => prev.filter((modelConfig) => modelConfig.id !== id));
      await refreshAgentsAfterModelMutation();
      const impactedAgents = agents.filter((agent) => agent.modelConfigId === id);
      pushToast({
        title: "模型已删除",
        description:
          impactedAgents.length > 0
            ? "相关 Agent 已标记为模型失效，需要重新绑定。"
            : "模型配置已从列表移除。",
        tone: impactedAgents.length > 0 ? "warning" : "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "删除模型失败");
      setModelConfigError(message);
      pushToast({ title: "删除模型失败", description: message, tone: "error" });
      throw error;
    }
  }

  function queueAgentReplies(
    conversationId: string,
    agentMessages: Message[],
    conversationUpdatedAt: string
  ) {
    agentMessages.forEach((agentMessage, index) => {
      let flushed = false;

      const flush = () => {
        if (flushed) return;
        flushed = true;
        setMessages((prev) => mergeMessageList(prev, agentMessage));
        if (index === agentMessages.length - 1) {
          setConversations((prev) =>
            prev.map((conversation) =>
              conversation.id === conversationId
                ? { ...conversation, updatedAt: conversationUpdatedAt }
                : conversation
            )
          );
        }
      };

      const timeoutId = setTimeout(() => {
        flush();
        pendingTimeoutsRef.current = pendingTimeoutsRef.current.filter(
          (entry) => entry.timeoutId !== timeoutId
        );
      }, 500 + index * 500);

      pendingTimeoutsRef.current.push({ timeoutId, flush });
    });
  }

  async function handleSendRequest(content: string, imageFiles: File[] = []) {
    clearPendingReplies();
    if (!activeConversation) return;

    const targetConversationId = activeConversation.id;
    const previousUpdatedAt = activeConversation.updatedAt;
    const optimisticUpdatedAt = new Date().toISOString();
    let uploadedAttachments: Attachment[] = [];

    if (imageFiles.length > 0) {
      try {
        uploadedAttachments = await Promise.all(
          imageFiles.map(async (file) => {
            const uploaded = await uploadImageAttachment(file, targetConversationId);
            return {
              id: uploaded.id,
              attachmentId: uploaded.attachmentId ?? uploaded.id,
              type: "image" as const,
              kind: "image" as const,
              source: "upload" as const,
              mimeType: uploaded.mimeType,
              previewUrl: uploaded.previewUrl,
              expiresAt: uploaded.expiresAt,
              name: file.name,
              size: file.size,
            };
          })
        );
      } catch (error) {
        const message = getErrorMessage(error, "图片上传失败");
        setErrorMessage(message);
        pushToast({ title: "图片上传失败", description: message, tone: "error" });
        return;
      }
    }

    const tempMessageId = `temp-${crypto.randomUUID()}`;
    const optimisticMessage: Message = {
      id: tempMessageId,
      conversationId: targetConversationId,
      senderType: "user",
      senderId: "user",
      content,
      attachments: uploadedAttachments.length > 0 ? uploadedAttachments : undefined,
      createdAt: optimisticUpdatedAt,
    };

    setErrorMessage(null);
    setMessages((prev) => mergeMessageList(prev, optimisticMessage));
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === targetConversationId
          ? { ...conversation, updatedAt: optimisticUpdatedAt }
          : conversation
      )
    );

    try {
      if (activeConversation.type === "group") {
        let persistedUserMessage = false;
        let deliveredAgentReply = false;
        const streamErrorMessages: string[] = [];

        const syncConversationUpdatedAt = (updatedAt?: string | null) => {
          if (!updatedAt) return;
          setConversations((prev) =>
            prev.map((conversation) =>
              conversation.id === targetConversationId
                ? { ...conversation, updatedAt }
                : conversation
            )
          );
        };

        await sendGroupMessageStream(
          {
            conversationId: targetConversationId,
            content,
            attachments: uploadedAttachments.length > 0 ? uploadedAttachments : undefined,
          },
          (event) => {
            if (event.payload.conversationId !== targetConversationId) {
              return;
            }
            switch (event.event) {
              case "user_message":
                persistedUserMessage = true;
                setMessages((prev) =>
                  replaceOptimisticMessage(prev, tempMessageId, event.payload.message)
                );
                syncConversationUpdatedAt(event.payload.conversationUpdatedAt);
                break;
              case "agent_message":
                deliveredAgentReply = true;
                setMessages((prev) => mergeMessageList(prev, event.payload.message));
                syncConversationUpdatedAt(event.payload.conversationUpdatedAt);
                break;
              case "conversation_updated":
              case "done":
                syncConversationUpdatedAt(event.payload.conversationUpdatedAt);
                break;
              case "error":
                if (event.payload.error.message.trim()) {
                  streamErrorMessages.push(event.payload.error.message.trim());
                }
                syncConversationUpdatedAt(event.payload.conversationUpdatedAt);
                break;
              case "tool_call":
                handleToolCall(event.payload);
                syncConversationUpdatedAt(event.payload.conversationUpdatedAt);
                break;
              case "tool_result":
                handleToolResult(event.payload);
                syncConversationUpdatedAt(event.payload.conversationUpdatedAt);
                break;
              default:
                break;
            }
          }
        );

        const combinedStreamErrorMessage = Array.from(new Set(streamErrorMessages)).join("\n");
        if (combinedStreamErrorMessage) {
          setErrorMessage(combinedStreamErrorMessage);
          pushToast({
            title: deliveredAgentReply ? "部分成员回复失败" : "群聊未完成回复",
            description: combinedStreamErrorMessage,
            tone: deliveredAgentReply ? "warning" : "error",
          });
        }
        if (!persistedUserMessage) {
          setMessages((prev) => prev.filter((message) => message.id !== tempMessageId));
          setConversations((prev) =>
            prev.map((conversation) =>
              conversation.id === targetConversationId
                ? { ...conversation, updatedAt: previousUpdatedAt }
                : conversation
            )
          );
        } else if (!deliveredAgentReply) {
          syncConversationUpdatedAt(new Date().toISOString());
        }
        return;
      }

      const result = await sendMessage({
        conversationId: targetConversationId,
        content,
        attachments: uploadedAttachments.length > 0 ? uploadedAttachments : undefined,
      });

      setMessages((prev) =>
        replaceOptimisticMessage(prev, tempMessageId, result.userMessage)
      );

      if (result.agentMessages.length === 0) {
        setConversations((prev) =>
          prev.map((conversation) =>
            conversation.id === targetConversationId
              ? { ...conversation, updatedAt: result.conversationUpdatedAt }
              : conversation
          )
        );
        return;
      }

      queueAgentReplies(
        targetConversationId,
        result.agentMessages,
        result.conversationUpdatedAt
      );
    } catch (error) {
      setMessages((prev) => prev.filter((message) => message.id !== tempMessageId));
      setConversations((prev) =>
        prev.map((conversation) =>
          conversation.id === targetConversationId
            ? { ...conversation, updatedAt: previousUpdatedAt }
            : conversation
        )
      );
      setErrorMessage(getErrorMessage(error, "发送消息失败"));
      pushToast({
        title: "发送消息失败",
        description: getErrorMessage(error, "发送消息失败"),
        tone: "error",
      });
    }
  }

  function handleSend(content: string, imageFiles: File[] = []) {
    void handleSendRequest(content, imageFiles);
  }

  async function handleCreateGroup(title: string, memberIds: string[], historyRounds: number) {
    clearPendingReplies();
    setErrorMessage(null);
    if (memberIds.length < 2) {
      setErrorMessage("创建群聊至少需要 2 个 Agent 成员");
      return;
    }
    const sourceConversationId =
      createModalMode === "context" && activeConversation?.type === "direct"
        ? activeConversation.id
        : null;

    try {
      const conversation = await createGroupConversation({
        title: title.trim() || "新群聊",
        memberIds,
        sourceConversationId,
        historyRounds: sourceConversationId
          ? Math.max(1, Math.floor(historyRounds || DEFAULT_HISTORY_MIGRATION_ROUNDS))
          : 0,
      });
      const migratedMessages = await loadConversationMessages(conversation.id);

      setConversations((prev) => upsertConversation(prev, conversation, true));
      setMessages((prev) => mergeMessageList(prev, ...migratedMessages));
      setActiveConversationId(conversation.id);
      setMiddlePanel({ type: "groupMembers" });
      if (memberIds[0]) {
        setActiveAgentId(memberIds[0]);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "创建群聊失败"));
    }
  }

  function syncSelectionAfterConversationChange(nextConversations: Conversation[]) {
    const sorted = sortConversations(nextConversations);
    const nextActiveConversation = sorted[0] ?? null;

    setActiveConversationId(nextActiveConversation?.id ?? "");
    if (!nextActiveConversation) {
      setMiddlePanel({ type: "profile" });
      return;
    }

    if (nextActiveConversation.type === "direct" && nextActiveConversation.agentId) {
      setActiveAgentId(nextActiveConversation.agentId);
      setMiddlePanel({ type: "profile" });
      return;
    }

    const firstAgentId = nextActiveConversation.memberIds.find((memberId) => memberId !== "user");
    if (firstAgentId) {
      setActiveAgentId(firstAgentId);
    }
    setMiddlePanel({ type: "groupMembers" });
  }

  async function handleDeleteConversation(conversationId: string) {
    setErrorMessage(null);
    try {
      await deleteConversation(conversationId);
      const deletingActiveConversation = activeConversationId === conversationId;
      const nextConversations = conversations.filter((conversation) => conversation.id !== conversationId);

      setConversations(nextConversations);
      setMessages((prev) => prev.filter((message) => message.conversationId !== conversationId));

      if (deletingActiveConversation) {
        syncSelectionAfterConversationChange(nextConversations);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "删除会话失败"));
    }
  }

  async function handleBulkDeleteConversations(conversationIds: string[]) {
    setErrorMessage(null);
    try {
      await bulkDeleteConversations(conversationIds);
      const deletedIds = new Set(conversationIds);
      const deletingActiveConversation = deletedIds.has(activeConversationId);
      const nextConversations = conversations.filter(
        (conversation) => !deletedIds.has(conversation.id)
      );

      setConversations(nextConversations);
      setMessages((prev) =>
        prev.filter((message) => !deletedIds.has(message.conversationId))
      );

      if (deletingActiveConversation) {
        syncSelectionAfterConversationChange(nextConversations);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "批量删除会话失败"));
    }
  }

  async function handlePinConversation(conversationId: string, pinned: boolean) {
    setErrorMessage(null);
    try {
      const updatedConversation = await updateConversationPin(conversationId, pinned);
      setConversations((prev) =>
        prev.map((conversation) =>
          conversation.id === conversationId ? updatedConversation : conversation
        )
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, pinned ? "置顶会话失败" : "取消置顶失败"));
    }
  }

  async function handlePinAgent(agentId: string, pinned: boolean) {
    setErrorMessage(null);
    try {
      const updatedAgent = hydrateAgent(await updateAgentPin(agentId, pinned));
      setAgents((prev) =>
        prev.map((agent) => (agent.id === agentId ? updatedAgent : agent))
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, pinned ? "置顶 Agent 失败" : "取消置顶 Agent 失败"));
    }
  }

  function openCreateModal(mode: "blank" | "context") {
    setCreateModalMode(mode);
    setIsCreateModalOpen(true);
  }

  async function handleCreateBlankConversation(modelConfigId?: string) {
    if (!blankTemplateAgent) {
      pushToast({
        title: "缺少空白模板",
        description: "当前还没有 blank-agent 模板，暂时无法创建空白对话。",
        tone: "warning",
      });
      return;
    }

    setIsCreatingBlankConversation(true);
    setErrorMessage(null);

    try {
      const conversation = await createDirectConversation(blankTemplateAgent.id, "空白对话", {
        modelConfigId: modelConfigId ?? null,
      });
      setConversations((prev) => upsertConversation(prev, conversation, true));
      setActiveConversationId(conversation.id);
      setActiveAgentId(blankTemplateAgent.id);
      setMiddlePanel({ type: "profile" });
      setIsModelPickerOpen(false);
      pushToast({
        title: "空白对话已创建",
        description: "你现在可以直接开始一段无预设提示词的对话。",
        tone: "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "创建空白对话失败");
      setErrorMessage(message);
      pushToast({ title: "创建空白对话失败", description: message, tone: "error" });
    } finally {
      setIsCreatingBlankConversation(false);
    }
  }

  function handleOpenBlankConversation() {
    if (availableModelConfigs.length === 0) {
      setActiveTool("settings");
      pushToast({
        title: "暂无可用模型",
        description: "请先在模型管理中添加并校验一个可用模型。",
        tone: "warning",
      });
      return;
    }

    if (availableModelConfigs.length === 1) {
      void handleCreateBlankConversation(availableModelConfigs[0].id);
      return;
    }

    setIsModelPickerOpen(true);
  }

  function renderMiddlePanel() {
    if (!activeAgent) return null;

    switch (middlePanel.type) {
      case "agentDetail": {
        const agent = agents.find((item) => item.id === middlePanel.agentId);
        if (!agent) return null;
        return (
          <AgentDetailPage
            agent={agent}
            onBack={() => {
              if (activeConversation?.type === "group") {
                setMiddlePanel({ type: "groupMembers" });
              } else {
                setMiddlePanel({ type: "profile" });
              }
            }}
            onEdit={() => setMiddlePanel({ type: "agentEdit", agentId: agent.id })}
          />
        );
      }
      case "agentEdit": {
        const agent = agents.find((item) => item.id === middlePanel.agentId);
        if (!agent) return null;
        return (
          <AgentEditPage
            agent={agent}
            modelConfigs={modelConfigs}
            onOpenModelSettings={() => setActiveTool("settings")}
            onBack={() => setMiddlePanel({ type: "agentDetail", agentId: agent.id })}
            onUpdateModelBinding={(modelConfigId) => handleUpdateAgentBinding(agent.id, modelConfigId)}
            onSave={(updates) => handleSaveAgent(agent.id, updates)}
          />
        );
      }
      case "groupMembers":
        if (!activeConversation || activeConversation.type !== "group") return null;
        return (
          <GroupMemberPanel
            conversation={activeConversation}
            agents={agents}
            activeAgentId={activeAgentId}
            onSelectAgent={handleViewAgentDetail}
          />
        );
      case "profile":
      default:
        return (
          <AgentProfilePanel
            agent={activeAgent}
            onEdit={() => setMiddlePanel({ type: "agentEdit", agentId: activeAgent.id })}
            onNewConversation={() => handleNewDirectConversation(activeAgent.id)}
          />
        );
    }
  }

  function handleReturnFromGroup() {
    if (!activeConversation || activeConversation.type !== "group") {
      return;
    }

    const sourceConversationId = activeConversation.sourceConversationId;
    if (sourceConversationId && conversations.some((conversation) => conversation.id === sourceConversationId)) {
      handleSelectConversation(sourceConversationId);
      return;
    }

    const firstAgentId = activeConversation.memberIds.find((memberId) => memberId !== "user");
    if (firstAgentId) {
      void handleSelectAgent(firstAgentId);
    }
  }

  function renderHomeDefaultState() {
    if (!activeAgent) {
      return (
        <div
          className="flex flex-1 items-center justify-center px-8 text-center"
          style={{ color: "var(--text-secondary)" }}
        >
          <div>
            <p className="text-sm font-medium text-[#2D2926]">当前还没有可用的 Agent</p>
            <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
              你可以先创建一个 Agent，或进入设置页准备模型后再开始。
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
        <section
          className="rounded-3xl border p-6"
          style={{
            background: "var(--bg-card)",
            borderColor: "var(--border-light)",
            boxShadow: "var(--shadow-soft)",
          }}
        >
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="flex min-w-0 items-start gap-4">
              <div
                className="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-3xl text-xl font-bold text-white"
                style={{ background: activeAgent.avatarImage ? "transparent" : activeAgent.themeColor }}
              >
                {activeAgent.avatarImage ? (
                  <img src={activeAgent.avatarImage} alt={activeAgent.name} className="h-full w-full object-cover" />
                ) : (
                  activeAgent.avatar
                )}
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-medium uppercase tracking-[0.15em]" style={{ color: "var(--text-tertiary)" }}>
                  当前 Agent
                </p>
                <h2 className="mt-1 truncate font-display text-2xl font-semibold text-[#2D2926]">
                  {activeAgent.name}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {activeAgent.roleSummary}
                </p>
                <p className="mt-2 max-w-2xl text-xs leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
                  {activeAgent.styleSummary}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => {
                  void handleSelectAgent(activeAgent.id);
                }}
                className="rounded-xl px-4 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:shadow-md"
                style={{ background: activeAgent.themeColor }}
              >
                打开对话
              </button>
              <button
                onClick={() => openCreateModal("blank")}
                className="rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
                style={{
                  background: "var(--bg-card)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-secondary)",
                }}
              >
                发起群聊
              </button>
            </div>
          </div>
        </section>

        <section className="mt-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="font-display text-lg font-semibold text-[#2D2926]">最近对话</h3>
              <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>
                从最近线程继续，避免默认自动跳入任意会话。
              </p>
            </div>
          </div>

          {recentConversations.length > 0 ? (
            <div className="mt-4 grid gap-3">
              {recentConversations.map((conversation) => {
                const directAgent =
                  conversation.type === "direct"
                    ? agents.find((agent) => agent.id === conversation.agentId) ?? null
                    : null;
                const summary =
                  conversation.type === "group"
                    ? `${conversation.memberIds.filter((memberId) => memberId !== "user").length} 位 Agent 依次响应`
                    : directAgent
                      ? `与 ${directAgent.name} 的直聊`
                      : "继续当前直聊";

                return (
                  <button
                    key={conversation.id}
                    type="button"
                    onClick={() => handleSelectConversation(conversation.id)}
                    className="flex items-center justify-between gap-4 rounded-2xl border px-4 py-4 text-left transition-all duration-200 hover:shadow-sm"
                    style={{
                      background: "var(--bg-card)",
                      borderColor: "var(--border-light)",
                    }}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[#2D2926]">{conversation.title}</p>
                      <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                        {summary}
                      </p>
                    </div>
                    <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                      进入
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div
              className="mt-4 rounded-2xl border border-dashed px-4 py-5 text-sm"
              style={{
                background: "var(--bg-card)",
                borderColor: "var(--border-light)",
                color: "var(--text-secondary)",
              }}
            >
              还没有最近会话。你可以从左侧 Agent 入口打开直聊，或先发起一场新的群聊。
            </div>
          )}
        </section>
      </div>
    );
  }

  if (isBootstrapping) {
    return (
      <div
        className="flex h-full w-full items-center justify-center"
        style={{ background: "var(--bg-primary)", color: "var(--text-primary)" }}
      >
        <div className="text-center">
          <p className="text-sm font-medium text-[#2D2926]">正在连接后端并加载工作台数据...</p>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            默认使用真实后端 API；如加载失败，请确认本地后端服务与代理配置可用
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex h-full w-full flex-1 overflow-hidden"
      style={{ background: "var(--bg-primary)", color: "var(--text-primary)" }}
    >
      <ConversationSidebar
        agents={visibleAgents}
        conversations={conversations}
        messages={messages}
        currentDirectAgentId={currentDirectAgentId}
        activeConversationId={activeConversationId}
        onSelectAgent={(agentId) => {
          void handleSelectAgent(agentId);
        }}
        onSelectConversation={handleSelectConversation}
        onCreateAgent={() => setIsCreateAgentModalOpen(true)}
        onCreateGroup={() => openCreateModal("blank")}
        onCreateBlankConversation={handleOpenBlankConversation}
        onDeleteConversation={(conversationId) => {
          void handleDeleteConversation(conversationId);
        }}
        onBulkDeleteConversations={(conversationIds) => {
          void handleBulkDeleteConversations(conversationIds);
        }}
        onPinConversation={(conversationId, pinned) => {
          void handlePinConversation(conversationId, pinned);
        }}
        onPinAgent={(agentId, pinned) => {
          void handlePinAgent(agentId, pinned);
        }}
      />

      {renderMiddlePanel()}

      <main className="flex min-w-0 flex-1 flex-col h-full overflow-hidden">
        <header
          className="flex-shrink-0 border-b px-4 py-4"
          style={{
            background: "var(--bg-card)",
            borderColor: "var(--border-light)",
          }}
        >
          <div className="flex min-h-[56px] items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div
                  className="h-2 w-2 rounded-full"
                  style={{
                    background:
                      activeConversation?.type === "group"
                        ? "#7BA89C"
                        : activeAgent?.themeColor ?? "#D4A574",
                  }}
                />
                <span
                  className="text-[11px] font-medium uppercase tracking-[0.15em]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {activeConversation?.type === "group" ? "群聊会话" : activeConversation ? "直接对话" : "首页默认态"}
                </span>
              </div>
              <h1 className="mt-1.5 truncate font-display text-2xl font-semibold text-[#2D2926]">
                {activeConversation?.title || "首页"}
              </h1>
            </div>
            <div className="flex flex-shrink-0 items-center gap-3">
              {activeConversation?.type === "group" && (
                <button
                  onClick={handleReturnFromGroup}
                  className="flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
                  style={{
                    background: "var(--bg-card)",
                    borderColor: "var(--border-medium)",
                    color: "var(--text-secondary)",
                  }}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="19" y1="12" x2="5" y2="12" />
                    <polyline points="12 19 5 12 12 5" />
                  </svg>
                  {activeConversation.sourceConversationId ? "返回来源直聊" : "返回成员直聊"}
                </button>
              )}
              <button
                onClick={() => openCreateModal("context")}
                disabled={!activeConversation || activeConversation.type !== "direct"}
                className="flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:shadow-md"
                style={{
                  background: "var(--bg-card)",
                  borderColor: "var(--border-medium)",
                  color: "var(--text-secondary)",
                  opacity: activeConversation?.type === "direct" ? 1 : 0.5,
                }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                基于当前直聊发起群聊
              </button>
            </div>
          </div>

          {errorMessage && (
            <div
              className="mt-4 whitespace-pre-wrap rounded-xl border px-4 py-2.5 text-sm"
              style={{
                background: "#FFF5F5",
                borderColor: "#F3C4C4",
                color: "#A63A3A",
              }}
            >
              {errorMessage}
            </div>
          )}
        </header>

        {activeConversation && activeAgent ? (
          <>
            <ChatMessageList
              messages={currentMessages}
              agents={agents}
              activeAgentName={activeAgent.name}
              activeAgentId={activeAgent.id}
              isGroup={activeConversation.type === "group"}
            />
            <MessageComposer
              canSend={sendCapability.enabled}
              sendDisabledReason={sendCapability.reason}
              canAttachImage={imageCapability.enabled}
              imageCapabilityReason={imageCapability.reason}
              maxImageCount={groupImageLimits.maxImageCount}
              maxImageSizeMb={groupImageLimits.maxImageSizeMb}
              onSend={handleSend}
            />
          </>
        ) : (
          renderHomeDefaultState()
        )}
      </main>

      <CreateGroupModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        agents={visibleAgents}
        currentConversation={activeConversation}
        mode={createModalMode}
        onCreateGroup={(title, memberIds, historyRounds) => {
          void handleCreateGroup(title, memberIds, historyRounds);
        }}
      />
      <CreateAgentModal
        isOpen={isCreateAgentModalOpen}
        isSubmitting={isCreatingAgent}
        modelConfigs={modelConfigs}
        onClose={() => setIsCreateAgentModalOpen(false)}
        onSubmit={(payload) => {
          void handleCreateAgent(payload);
        }}
      />

      <SettingsPanel
        isOpen={activeTool === "settings"}
        onClose={() => setActiveTool(null)}
        modelConfigs={modelConfigs}
        isLoading={isModelConfigsLoading}
        error={modelConfigError}
        onCreateModelConfig={(payload) => handleCreateModelConfig(payload)}
        onUpdateModelConfig={(id, payload) => handleUpdateModelConfig(id, payload)}
        onValidateModelConfig={(id) => handleValidateModelConfig(id)}
        onDeleteModelConfig={(id) => handleDeleteModelConfig(id)}
        impactedAgentsByModelConfigId={impactedAgentsByModelConfigId}
      />
      <ModelPickerModal
        isOpen={isModelPickerOpen}
        models={availableModelConfigs}
        isSubmitting={isCreatingBlankConversation}
        onClose={() => setIsModelPickerOpen(false)}
        onSelect={(modelConfigId) => {
          void handleCreateBlankConversation(modelConfigId);
        }}
      />
      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
      <ToolPanel
        activeTool={activeTool}
        onSelectTool={(toolId) => setActiveTool(toolId || null)}
        toolActivities={toolActivities}
      />
    </div>
  );
}
