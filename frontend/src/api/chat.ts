import { ApiError, requestEventStream, requestJson } from "./client";
import type {
  AgentDto,
  Attachment,
  BulkDeleteConversationsResponse,
  Conversation,
  ConversationRuntimeMetadata,
  CurrentGroupRuntimeDispatchStrategy,
  CurrentGroupRuntimeEventType,
  GroupRuntimeHooks,
  GroupRuntimeDispatchStrategy,
  GroupRuntimeEventType,
  GroupMessageStreamEvent,
  ImageAttachmentUploadResponse,
  LlmSettings,
  LlmSettingsUpdate,
  Message,
  ModelApiFormat,
  ModelConfig,
  ModelConfigPayload,
  ReservedFutureGroupRuntimeDispatchStrategy,
  ReservedFutureGroupRuntimeEventType,
  SendMessagePayload,
  SendMessageResponse,
} from "../types/chat";

type CreateAgentPayload = Omit<AgentDto, "id"> & { id?: string };

type BackendAttachment = {
  attachmentId: string;
  kind: "image";
  mimeType: string;
  name?: string | null;
  size?: number | null;
  previewUrl?: string | null;
  expiresAt?: string | null;
  metadata?: Record<string, unknown>;
};

type BackendAgent = {
  id: string;
  name: string;
  roleSummary: string;
  styleSummary: string;
  systemPrompt: string;
  avatar: string;
  avatarImage?: string | null;
  themeColor?: string | null;
  themeLight?: string | null;
  themeSoft?: string | null;
  modelConfigId?: string | null;
  modelUnavailable?: boolean;
  isTemplate?: boolean;
  pinned?: boolean;
  pinnedAt?: string | null;
};

type BackendConversation = {
  id: string;
  type: "direct" | "group";
  title: string;
  memberIds: string[];
  agentId?: string | null;
  sourceConversationId?: string | null;
  modelConfigId?: string | null;
  runtimeMetadata?: BackendConversationRuntimeMetadata;
  isDisabled?: boolean;
  createdAt: string;
  updatedAt: string;
  pinned?: boolean;
  pinnedAt?: string | null;
};

type BackendGroupRuntimeEvent = {
  event_id: string;
  event_type: string;
  visibility: string;
  sender_type: string;
  sender_id: string;
  speaker_name: string;
  speaker_role?: string | null;
  position?: number | null;
  content: string;
  created_at?: string | null;
  [key: string]: unknown;
};

type BackendGroupRuntimeProtocol = {
  version: string;
  mode: string;
  thread_id: string;
  scope: string;
  [key: string]: unknown;
};

type BackendGroupRuntimeModeratorNote = {
  status: string;
  content?: string | null;
  generated_by_agent_id?: string | null;
  generated_at?: string | null;
  input?: string | null;
  [key: string]: unknown;
};

type BackendGroupRuntimeEventWindow = {
  version: string;
  events: BackendGroupRuntimeEvent[];
  last_event_id?: string | null;
  last_event_type?: string | null;
  [key: string]: unknown;
};

type BackendGroupRuntimeDispatchState = {
  status: string;
  strategy: string;
  trigger_event_id?: string | null;
  cursor: number;
  pending_member_ids: string[];
  completed_member_ids: string[];
  last_completed_event_id?: string | null;
  [key: string]: unknown;
};

type BackendGroupRuntimeThread = {
  thread_id: string;
  kind: string;
  moderator_note: BackendGroupRuntimeModeratorNote;
  event_window: BackendGroupRuntimeEventWindow;
  dispatch_state: BackendGroupRuntimeDispatchState;
  [key: string]: unknown;
};

type BackendGroupRuntimeMetadata = {
  protocol: BackendGroupRuntimeProtocol;
  default_thread: BackendGroupRuntimeThread;
  [key: string]: unknown;
};

type BackendConversationRuntimeMetadata = {
  group_runtime?: BackendGroupRuntimeMetadata;
  [key: string]: unknown;
};

type BackendMessage = {
  id: string;
  conversationId: string;
  senderType: "user" | "agent";
  senderId: string;
  content: string;
  attachments: BackendAttachment[];
  createdAt: string;
};

type BackendMessagesPageResponse = {
  items: BackendMessage[];
  limit: number;
  offset: number;
  hasMore: boolean;
};

type BackendModelConfigCapabilities = {
  supportsImageInput?: boolean;
  supportsFileInput?: boolean;
  supportsStreaming?: boolean;
  contextWindow?: number | null;
};

type BackendModelConfig = {
  id: string;
  provider: string;
  model: string;
  displayName: string;
  apiFormat: string;
  baseUrl?: string | null;
  useFullUrl: boolean;
  status: string;
  statusMessage?: string | null;
  capabilities?: BackendModelConfigCapabilities;
  apiKeyConfigured: boolean;
  lastValidatedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

type BackendMessageSendResponse = {
  userMessage: BackendMessage;
  agentMessages: BackendMessage[];
  conversationUpdatedAt: string;
};

type BackendStreamErrorDetail = {
  code?: string;
  message: string;
};

type BackendGroupRuntimeHooks = {
  dispatch_strategy: GroupRuntimeDispatchStrategy;
  trigger_event_type: GroupRuntimeEventType;
  reserved_event_types?: CurrentGroupRuntimeEventType[];
  reserved_dispatch_strategies?: CurrentGroupRuntimeDispatchStrategy[];
  reserved_future_event_types?: ReservedFutureGroupRuntimeEventType[];
  reserved_future_dispatch_strategies?: ReservedFutureGroupRuntimeDispatchStrategy[];
  [key: string]: unknown;
};

type BackendMessageStreamPayload = {
  conversationId: string;
  message?: BackendMessage | null;
  conversationUpdatedAt?: string | null;
  error?: BackendStreamErrorDetail | null;
  runtimeHooks?: BackendGroupRuntimeHooks | null;
};

type BackendMessageStreamEvent = {
  event: GroupRuntimeEventType;
  payload: BackendMessageStreamPayload;
};

const MODEL_STATUS_SET = new Set(["draft", "validating", "available", "failed", "disabled"]);
const MODEL_API_FORMAT_SET = new Set<ModelApiFormat>([
  "openai_chat",
  "anthropic_messages",
  "gemini_generate_content",
]);
const RESERVED_FUTURE_GROUP_MESSAGE_EVENT_SET = new Set<ReservedFutureGroupRuntimeEventType>([
  "agent_thinking",
  "dispatch_progress",
]);

function toApiError(error: unknown, fallbackMessage: string): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof SyntaxError) {
    return new ApiError("后端响应格式错误，请稍后重试", 0, "invalid_response");
  }
  if (error instanceof TypeError) {
    return new ApiError("无法连接后端服务，请确认后端已启动", 0, "network_error");
  }
  if (error instanceof Error) {
    return new ApiError(error.message || fallbackMessage, 0, "unknown_error");
  }
  return new ApiError(fallbackMessage, 0, "unknown_error");
}

async function withErrorConversion<T>(action: () => Promise<T>, fallbackMessage: string): Promise<T> {
  try {
    return await action();
  } catch (error) {
    throw toApiError(error, fallbackMessage);
  }
}

function mapAgent(agent: BackendAgent): AgentDto {
  return {
    id: agent.id,
    name: agent.name,
    roleSummary: agent.roleSummary,
    styleSummary: agent.styleSummary,
    systemPrompt: agent.systemPrompt,
    avatar: agent.avatar,
    avatarImage: agent.avatarImage ?? null,
    themeColor: agent.themeColor ?? null,
    themeLight: agent.themeLight ?? null,
    themeSoft: agent.themeSoft ?? null,
    modelConfigId: agent.modelConfigId ?? null,
    modelUnavailable: agent.modelUnavailable ?? false,
    isTemplate: agent.isTemplate ?? false,
    pinned: agent.pinned ?? false,
    pinnedAt: agent.pinnedAt ?? null,
  };
}

function mapConversation(conversation: BackendConversation): Conversation {
  return {
    id: conversation.id,
    type: conversation.type,
    title: conversation.title,
    memberIds: conversation.memberIds,
    agentId: conversation.agentId ?? undefined,
    sourceConversationId: conversation.sourceConversationId ?? null,
    modelConfigId: conversation.modelConfigId ?? null,
    runtimeMetadata: mapConversationRuntimeMetadata(conversation.runtimeMetadata),
    isDisabled: conversation.isDisabled ?? false,
    createdAt: conversation.createdAt,
    updatedAt: conversation.updatedAt,
    pinned: conversation.pinned ?? false,
    pinnedAt: conversation.pinnedAt ?? null,
  };
}

function mapAttachment(attachment: BackendAttachment): Attachment {
  return {
    id: attachment.attachmentId,
    attachmentId: attachment.attachmentId,
    type: "image",
    kind: "image",
    source: "upload",
    mimeType: attachment.mimeType,
    previewUrl: attachment.previewUrl ?? undefined,
    expiresAt: attachment.expiresAt ?? null,
    name: attachment.name ?? undefined,
    size: attachment.size ?? undefined,
    metadata: attachment.metadata ?? {},
  };
}

function mapGroupRuntimeEvent(event: BackendGroupRuntimeEvent) {
  const {
    event_id,
    event_type,
    sender_type,
    sender_id,
    speaker_name,
    speaker_role,
    created_at,
    ...rest
  } = event;

  return {
    ...rest,
    eventId: event_id,
    eventType: event_type,
    senderType: sender_type,
    senderId: sender_id,
    speakerName: speaker_name,
    speakerRole: speaker_role ?? null,
    createdAt: created_at ?? null,
  };
}

function mapConversationRuntimeMetadata(
  runtimeMetadata?: BackendConversationRuntimeMetadata
): ConversationRuntimeMetadata {
  if (!runtimeMetadata?.group_runtime) {
    return runtimeMetadata ?? {};
  }

  const { group_runtime, ...restMetadata } = runtimeMetadata;
  const { protocol, default_thread, ...restGroupRuntime } = group_runtime;
  const { thread_id: protocolThreadId, ...restProtocol } = protocol;
  const {
    thread_id: defaultThreadId,
    moderator_note,
    event_window,
    dispatch_state,
    ...restDefaultThread
  } = default_thread;
  const {
    generated_by_agent_id,
    generated_at,
    ...restModeratorNote
  } = moderator_note;
  const {
    last_event_id,
    last_event_type,
    events,
    ...restEventWindow
  } = event_window;
  const {
    trigger_event_id,
    pending_member_ids,
    completed_member_ids,
    last_completed_event_id,
    ...restDispatchState
  } = dispatch_state;

  return {
    ...restMetadata,
    groupRuntime: {
      ...restGroupRuntime,
      protocol: {
        ...restProtocol,
        threadId: protocolThreadId,
      },
      defaultThread: {
        ...restDefaultThread,
        threadId: defaultThreadId,
        moderatorNote: {
          ...restModeratorNote,
          generatedByAgentId: generated_by_agent_id ?? null,
          generatedAt: generated_at ?? null,
        },
        eventWindow: {
          ...restEventWindow,
          events: events.map(mapGroupRuntimeEvent),
          lastEventId: last_event_id ?? null,
          lastEventType: last_event_type ?? null,
        },
        dispatchState: {
          ...restDispatchState,
          triggerEventId: trigger_event_id ?? null,
          pendingMemberIds: pending_member_ids,
          completedMemberIds: completed_member_ids,
          lastCompletedEventId: last_completed_event_id ?? null,
        },
      },
    },
  };
}

function mapGroupRuntimeHooks(runtimeHooks?: BackendGroupRuntimeHooks | null): GroupRuntimeHooks | null {
  if (!runtimeHooks) {
    return null;
  }

  const {
    dispatch_strategy,
    trigger_event_type,
    reserved_event_types,
    reserved_dispatch_strategies,
  } = runtimeHooks;

  return {
    dispatchStrategy: dispatch_strategy,
    triggerEventType: trigger_event_type,
    reservedEventTypes: reserved_event_types ?? [],
    reservedDispatchStrategies: reserved_dispatch_strategies ?? [],
    reservedFutureEventTypes: runtimeHooks.reserved_future_event_types ?? [],
    reservedFutureDispatchStrategies: runtimeHooks.reserved_future_dispatch_strategies ?? [],
  };
}

function mapMessage(message: BackendMessage): Message {
  return {
    id: message.id,
    conversationId: message.conversationId,
    senderType: message.senderType,
    senderId: message.senderId,
    content: message.content,
    attachments: message.attachments.map(mapAttachment),
    createdAt: message.createdAt,
  };
}

function mapModelStatus(status: string): ModelConfig["status"] {
  return MODEL_STATUS_SET.has(status) ? (status as ModelConfig["status"]) : "failed";
}

function mapModelApiFormat(apiFormat: string): ModelApiFormat {
  return MODEL_API_FORMAT_SET.has(apiFormat as ModelApiFormat)
    ? (apiFormat as ModelApiFormat)
    : "openai_chat";
}

function mapModelConfig(modelConfig: BackendModelConfig): ModelConfig {
  const capabilities = modelConfig.capabilities ?? {};
  const contextWindow = capabilities.contextWindow ?? null;

  return {
    id: modelConfig.id,
    provider: modelConfig.provider,
    model: modelConfig.model,
    displayName: modelConfig.displayName,
    apiFormat: mapModelApiFormat(modelConfig.apiFormat),
    baseUrl: modelConfig.baseUrl ?? "",
    useFullUrl: modelConfig.useFullUrl,
    status: mapModelStatus(modelConfig.status),
    statusMessage: modelConfig.statusMessage ?? null,
    apiKeyConfigured: modelConfig.apiKeyConfigured,
    supportsImageInput: capabilities.supportsImageInput ?? false,
    supportsFileInput: capabilities.supportsFileInput ?? false,
    supportsSystemPrompt: true,
    supportsStreaming: capabilities.supportsStreaming ?? false,
    contextWindowInput: contextWindow,
    contextWindowOutput: null,
    maxImageCount: null,
    maxImageSizeMb: null,
    defaultTemperature: null,
    lastValidatedAt: modelConfig.lastValidatedAt ?? null,
    createdAt: modelConfig.createdAt,
    updatedAt: modelConfig.updatedAt,
  };
}

function mapAttachmentToRequest(attachment: Attachment): BackendAttachment {
  const attachmentId = attachment.attachmentId ?? attachment.id;
  if (!attachmentId) {
    throw new ApiError("附件缺少 attachmentId", 422, "validation_error");
  }

  return {
    attachmentId,
    kind: "image",
    mimeType: attachment.mimeType,
    name: attachment.name,
    size: attachment.size,
    previewUrl: attachment.previewUrl,
    expiresAt: attachment.expiresAt ?? null,
    metadata: attachment.metadata ?? {},
  };
}

function buildModelConfigRequest(payload: ModelConfigPayload) {
  return {
    provider: payload.provider,
    model: payload.model,
    displayName: payload.displayName?.trim() || `${payload.provider} - ${payload.model}`,
    apiFormat: payload.apiFormat,
    baseUrl: payload.baseUrl?.trim() || null,
    useFullUrl: payload.useFullUrl,
    apiKey: payload.apiKey ?? "",
    capabilities: {
      supportsImageInput: payload.supportsImageInput ?? false,
      supportsFileInput: payload.supportsFileInput ?? false,
      supportsStreaming: payload.supportsStreaming ?? false,
      contextWindow: payload.contextWindowInput ?? payload.contextWindowOutput ?? null,
    },
  };
}

function buildModelConfigPatch(payload: Partial<ModelConfigPayload>) {
  const body: Record<string, unknown> = {};

  if (payload.provider !== undefined) body.provider = payload.provider;
  if (payload.model !== undefined) body.model = payload.model;
  if (payload.displayName !== undefined) body.displayName = payload.displayName;
  if (payload.apiFormat !== undefined) body.apiFormat = payload.apiFormat;
  if (payload.baseUrl !== undefined) body.baseUrl = payload.baseUrl?.trim() || null;
  if (payload.useFullUrl !== undefined) body.useFullUrl = payload.useFullUrl;
  if (payload.apiKey !== undefined) body.apiKey = payload.apiKey;

  if (
    payload.supportsImageInput !== undefined ||
    payload.supportsFileInput !== undefined ||
    payload.supportsStreaming !== undefined ||
    payload.contextWindowInput !== undefined ||
    payload.contextWindowOutput !== undefined
  ) {
    body.capabilities = {
      supportsImageInput: payload.supportsImageInput ?? false,
      supportsFileInput: payload.supportsFileInput ?? false,
      supportsStreaming: payload.supportsStreaming ?? false,
      contextWindow: payload.contextWindowInput ?? payload.contextWindowOutput ?? null,
    };
  }

  return body;
}

export function getAgents() {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendAgent[]>("/agents");
    return response.map(mapAgent);
  }, "读取 Agent 列表失败");
}

export function createAgent(payload: CreateAgentPayload) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendAgent>("/agents", {
      method: "POST",
      body: {
        name: payload.name,
        roleSummary: payload.roleSummary,
        styleSummary: payload.styleSummary,
        systemPrompt: payload.systemPrompt ?? "",
        avatar: payload.avatar,
        avatarImage: payload.avatarImage ?? null,
        themeColor: payload.themeColor ?? null,
        themeLight: payload.themeLight ?? null,
        themeSoft: payload.themeSoft ?? null,
        modelConfigId: payload.modelConfigId ?? null,
      },
    });
    return mapAgent(response);
  }, "创建 Agent 失败");
}

export function updateAgent(agentId: string, payload: AgentDto) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendAgent>(`/agents/${encodeURIComponent(agentId)}`, {
      method: "PUT",
      body: {
        name: payload.name,
        roleSummary: payload.roleSummary,
        styleSummary: payload.styleSummary,
        systemPrompt: payload.systemPrompt,
        avatar: payload.avatar,
        avatarImage: payload.avatarImage ?? null,
        themeColor: payload.themeColor ?? null,
        themeLight: payload.themeLight ?? null,
        themeSoft: payload.themeSoft ?? null,
      },
    });
    return mapAgent(response);
  }, "更新 Agent 失败");
}

export function updateAgentModelBinding(agentId: string, modelConfigId: string | null) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendAgent>(`/agents/${encodeURIComponent(agentId)}/model`, {
      method: "PATCH",
      body: { modelConfigId },
    });
    return mapAgent(response);
  }, "更新 Agent 模型绑定失败");
}

export function updateAgentPin(agentId: string, pinned: boolean) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendAgent>(`/agents/${encodeURIComponent(agentId)}/pin`, {
      method: "PATCH",
      body: { pinned },
    });
    return mapAgent(response);
  }, "更新 Agent 置顶状态失败");
}

export function getConversations() {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendConversation[]>("/conversations");
    return response.map(mapConversation);
  }, "读取会话列表失败");
}

export function updateConversationPin(conversationId: string, pinned: boolean) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendConversation>(
      `/conversations/${encodeURIComponent(conversationId)}/pin`,
      {
        method: "PATCH",
        body: { pinned },
      }
    );
    return mapConversation(response);
  }, "更新会话置顶状态失败");
}

export function deleteConversation(conversationId: string) {
  return withErrorConversion(async () => {
    await requestJson<null>(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
    });
  }, "删除会话失败");
}

export function bulkDeleteConversations(conversationIds: string[]) {
  return withErrorConversion(async () => {
    return requestJson<BulkDeleteConversationsResponse>("/conversations/bulk-delete", {
      method: "POST",
      body: { conversationIds },
    });
  }, "批量删除会话失败");
}

export async function getMessages(conversationId: string, limit = 100, offset = 0) {
  return withErrorConversion(async () => {
    const params = new URLSearchParams({
      conversationId,
      limit: String(limit),
      offset: String(offset),
    });
    const response = await requestJson<BackendMessagesPageResponse>(`/messages?${params.toString()}`);
    return response.items.map(mapMessage);
  }, "读取消息列表失败");
}

export function createDirectConversation(
  agentId: string,
  title?: string,
  options?: { modelConfigId?: string | null }
) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendConversation>("/conversations/direct", {
      method: "POST",
      body: {
        agentId,
        title,
        modelConfigId: options?.modelConfigId ?? null,
      },
    });
    return mapConversation(response);
  }, "创建单聊失败");
}

export function createGroupConversation(payload: {
  title: string;
  memberIds: string[];
  sourceConversationId?: string | null;
  historyRounds?: number;
}) {
  return withErrorConversion(async () => {
    const historyRounds = payload.sourceConversationId ? Math.max(payload.historyRounds ?? 1, 1) : 0;
    const response = await requestJson<BackendConversation>("/conversations/group", {
      method: "POST",
      body: {
        title: payload.title,
        memberIds: payload.memberIds,
        sourceConversationId: payload.sourceConversationId ?? null,
        includeContext: historyRounds > 0,
        contextRounds: historyRounds,
      },
    });
    return mapConversation(response);
  }, "创建群聊失败");
}

export function sendMessage(payload: SendMessagePayload) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendMessageSendResponse>("/messages", {
      method: "POST",
      body: {
        conversationId: payload.conversationId,
        content: payload.content,
        attachments: (payload.attachments ?? []).map(mapAttachmentToRequest),
      },
    });
    return {
      userMessage: mapMessage(response.userMessage),
      agentMessages: response.agentMessages.map(mapMessage),
      conversationUpdatedAt: response.conversationUpdatedAt,
    } satisfies SendMessageResponse;
  }, "发送消息失败");
}

export function sendGroupMessageStream(
  payload: SendMessagePayload,
  onEvent: (event: GroupMessageStreamEvent) => void
) {
  return withErrorConversion(async () => {
    await requestEventStream<BackendMessageStreamEvent>("/messages/stream", {
      method: "POST",
      body: {
        conversationId: payload.conversationId,
        content: payload.content,
        attachments: (payload.attachments ?? []).map(mapAttachmentToRequest),
      },
      onEvent: (event) => {
        const payloadData = event.payload;
        if (event.event === "user_message" || event.event === "agent_message") {
          if (!payloadData.message) {
            return;
          }
          onEvent({
            event: event.event,
            payload: {
              conversationId: payloadData.conversationId,
              message: mapMessage(payloadData.message),
              conversationUpdatedAt: payloadData.conversationUpdatedAt ?? null,
              runtimeHooks: mapGroupRuntimeHooks(payloadData.runtimeHooks),
            },
          });
          return;
        }
        if (event.event === "error") {
          onEvent({
            event: "error",
            payload: {
              conversationId: payloadData.conversationId,
              conversationUpdatedAt: payloadData.conversationUpdatedAt ?? null,
              error: {
                code: payloadData.error?.code,
                message: payloadData.error?.message ?? "群聊运行失败",
              },
              runtimeHooks: mapGroupRuntimeHooks(payloadData.runtimeHooks),
            },
          });
          return;
        }
        if (
          event.event === "moderator_note_ready" ||
          event.event === "conversation_updated" ||
          event.event === "done"
        ) {
          onEvent({
            event: event.event,
            payload: {
              conversationId: payloadData.conversationId,
              conversationUpdatedAt: payloadData.conversationUpdatedAt ?? null,
              runtimeHooks: mapGroupRuntimeHooks(payloadData.runtimeHooks),
            },
          });
          return;
        }
        if (event.event === "tool_call") {
          onEvent({
            event: "tool_call",
            payload: {
              conversationId: payloadData.conversationId,
              conversationUpdatedAt: payloadData.conversationUpdatedAt ?? null,
              runtimeHooks: mapGroupRuntimeHooks(payloadData.runtimeHooks),
              agentId: payloadData.agentId ?? payloadData.agent_id ?? "",
              agentName: payloadData.agentName ?? payloadData.agent_name ?? "",
              toolCallId: payloadData.toolCallId ?? payloadData.tool_call_id ?? "",
              toolName: payloadData.toolName ?? payloadData.tool_name ?? "",
              toolArgs: payloadData.toolArgs ?? payloadData.tool_args ?? {},
            },
          });
          return;
        }
        if (event.event === "tool_result") {
          onEvent({
            event: "tool_result",
            payload: {
              conversationId: payloadData.conversationId,
              conversationUpdatedAt: payloadData.conversationUpdatedAt ?? null,
              runtimeHooks: mapGroupRuntimeHooks(payloadData.runtimeHooks),
              agentId: payloadData.agentId ?? payloadData.agent_id ?? "",
              toolCallId: payloadData.toolCallId ?? payloadData.tool_call_id ?? "",
              toolName: payloadData.toolName ?? payloadData.tool_name ?? "",
              resultPreview: payloadData.resultPreview ?? payloadData.result_preview ?? "",
            },
          });
          return;
        }
        if (RESERVED_FUTURE_GROUP_MESSAGE_EVENT_SET.has(event.event as ReservedFutureGroupRuntimeEventType)) {
          onEvent({
            event: event.event as ReservedFutureGroupRuntimeEventType,
            payload: {
              conversationId: payloadData.conversationId,
              message: payloadData.message ? mapMessage(payloadData.message) : undefined,
              conversationUpdatedAt: payloadData.conversationUpdatedAt ?? null,
              error: payloadData.error
                ? {
                    code: payloadData.error.code,
                    message: payloadData.error.message,
                  }
                : undefined,
              runtimeHooks: mapGroupRuntimeHooks(payloadData.runtimeHooks),
            },
          });
        }
      },
    });
  }, "发送群聊消息失败");
}

export function getModelConfigs() {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendModelConfig[]>("/model-configs");
    return response.map(mapModelConfig);
  }, "读取模型配置失败");
}

export function createModelConfig(payload: ModelConfigPayload) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendModelConfig>("/model-configs", {
      method: "POST",
      body: buildModelConfigRequest(payload),
    });
    return mapModelConfig(response);
  }, "创建模型配置失败");
}

export function updateModelConfig(modelConfigId: string, payload: Partial<ModelConfigPayload>) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendModelConfig>(
      `/model-configs/${encodeURIComponent(modelConfigId)}`,
      {
        method: "PATCH",
        body: buildModelConfigPatch(payload),
      }
    );
    return mapModelConfig(response);
  }, "更新模型配置失败");
}

export function validateModelConfig(modelConfigId: string) {
  return withErrorConversion(async () => {
    const response = await requestJson<BackendModelConfig>(
      `/model-configs/${encodeURIComponent(modelConfigId)}/validate`,
      {
        method: "POST",
      }
    );
    return mapModelConfig(response);
  }, "校验模型配置失败");
}

export function deleteModelConfig(modelConfigId: string) {
  return withErrorConversion(async () => {
    await requestJson<null>(`/model-configs/${encodeURIComponent(modelConfigId)}`, {
      method: "DELETE",
    });
  }, "删除模型配置失败");
}

export function uploadImageAttachment(file: File, _conversationId?: string) {
  void _conversationId;

  return withErrorConversion(async () => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await requestJson<{
      attachmentId: string;
      mimeType: string;
      previewUrl: string;
      expiresAt?: string | null;
    }>("/attachments/images", {
      method: "POST",
      body: formData,
    });

    return {
      id: response.attachmentId,
      attachmentId: response.attachmentId,
      type: "image",
      mimeType: response.mimeType,
      previewUrl: response.previewUrl,
      expiresAt: response.expiresAt ?? null,
    } satisfies ImageAttachmentUploadResponse;
  }, "上传图片失败");
}

export function getLlmSettings() {
  return withErrorConversion(() => requestJson<LlmSettings>("/settings/llm"), "读取兼容 LLM 设置失败");
}

export function updateLlmSettings(payload: LlmSettingsUpdate) {
  return withErrorConversion(
    () =>
      requestJson<LlmSettings>("/settings/llm", {
        method: "PUT",
        body: payload,
      }),
    "更新兼容 LLM 设置失败"
  );
}
