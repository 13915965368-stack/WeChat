export type Agent = {
  id: string;
  name: string;
  roleSummary: string;
  styleSummary: string;
  systemPrompt: string;
  avatar: string;
  avatarImage?: string;
  themeColor: string;
  themeLight: string;
  themeSoft: string;
  pinned?: boolean;
  pinnedAt?: string | null;
  modelConfigId?: string | null;
  modelUnavailable?: boolean;
  isTemplate?: boolean;
};

export type AgentDto = {
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
  pinned?: boolean;
  pinnedAt?: string | null;
  modelConfigId?: string | null;
  modelUnavailable?: boolean;
  isTemplate?: boolean;
};

export type ModelConfigStatus =
  | "draft"
  | "validating"
  | "available"
  | "failed"
  | "disabled";

export type ModelApiFormat =
  | "openai_chat"
  | "anthropic_messages"
  | "gemini_generate_content";

export type ModelCapability = {
  supportsImageInput: boolean;
  supportsFileInput: boolean;
  supportsSystemPrompt: boolean;
  supportsStreaming: boolean;
  contextWindowInput?: number | null;
  contextWindowOutput?: number | null;
  maxImageCount?: number | null;
  maxImageSizeMb?: number | null;
};

export type ModelConfig = {
  id: string;
  provider: string;
  model: string;
  displayName: string;
  apiFormat: ModelApiFormat;
  baseUrl: string;
  useFullUrl: boolean;
  status: ModelConfigStatus;
  statusMessage?: string | null;
  apiKeyConfigured: boolean;
  defaultTemperature?: number | null;
  lastValidatedAt?: string | null;
  createdAt: string;
  updatedAt: string;
} & ModelCapability;

export type ModelConfigPayload = {
  provider: string;
  model: string;
  displayName?: string;
  apiFormat: ModelApiFormat;
  baseUrl: string;
  useFullUrl: boolean;
  apiKey?: string;
  supportsImageInput?: boolean;
  supportsFileInput?: boolean;
  supportsSystemPrompt?: boolean;
  supportsStreaming?: boolean;
  contextWindowInput?: number | null;
  contextWindowOutput?: number | null;
  maxImageCount?: number | null;
  maxImageSizeMb?: number | null;
  defaultTemperature?: number | null;
};

export type ConversationType = 'direct' | 'group';

export type GroupRuntimeEvent = {
  eventId: string;
  eventType: string;
  visibility: string;
  senderType: string;
  senderId: string;
  speakerName: string;
  speakerRole?: string | null;
  position?: number | null;
  content: string;
  createdAt?: string | null;
  [key: string]: unknown;
};

export type GroupRuntimeProtocol = {
  version: string;
  mode: string;
  threadId: string;
  scope: string;
  [key: string]: unknown;
};

export type GroupRuntimeModeratorNote = {
  status: string;
  content?: string | null;
  generatedByAgentId?: string | null;
  generatedAt?: string | null;
  input?: string | null;
  [key: string]: unknown;
};

export type GroupRuntimeEventWindow = {
  version: string;
  events: GroupRuntimeEvent[];
  lastEventId?: string | null;
  lastEventType?: string | null;
  [key: string]: unknown;
};

export type GroupRuntimeDispatchState = {
  status: string;
  strategy: string;
  triggerEventId?: string | null;
  cursor: number;
  pendingMemberIds: string[];
  completedMemberIds: string[];
  lastCompletedEventId?: string | null;
  [key: string]: unknown;
};

export type GroupRuntimeThread = {
  threadId: string;
  kind: string;
  moderatorNote: GroupRuntimeModeratorNote;
  eventWindow: GroupRuntimeEventWindow;
  dispatchState: GroupRuntimeDispatchState;
  [key: string]: unknown;
};

export type GroupRuntimeMetadata = {
  protocol: GroupRuntimeProtocol;
  defaultThread: GroupRuntimeThread;
  [key: string]: unknown;
};

export type ConversationRuntimeMetadata = {
  groupRuntime?: GroupRuntimeMetadata;
  [key: string]: unknown;
};

export type Conversation = {
  id: string;
  type: ConversationType;
  title: string;
  memberIds: string[];      // 包含 "user" + agentIds
  agentId?: string;         // 仅 direct 可用，表示主 Agent
  sourceConversationId?: string | null; // 仅 group 可用，表示来源直聊
  modelConfigId?: string | null; // 用于空白对话等会话级模型覆盖
  runtimeMetadata?: ConversationRuntimeMetadata;
  isDisabled?: boolean;
  createdAt: string;
  updatedAt: string;
  pinned?: boolean;
  pinnedAt?: string | null;
};

export type Message = {
  id: string;
  conversationId: string;
  senderType: 'user' | 'agent';
  senderId: string;
  content: string;
  attachments?: Attachment[];
  createdAt: string;
};

export type Attachment = {
  id: string;
  attachmentId?: string;
  type: "image";
  kind?: "image";
  source?: "upload" | "base64" | "url";
  mimeType: string;
  previewUrl?: string;
  url?: string;
  base64Data?: string;
  expiresAt?: string | null;
  name?: string;
  size?: number;
  metadata?: Record<string, unknown>;
};

export type SendMessageResponse = {
  userMessage: Message;
  agentMessages: Message[];
  conversationUpdatedAt: string;
};

export type StreamErrorDetail = {
  code?: string;
  message: string;
};

export type ToolCallPayload = {
  agentId: string;
  agentName: string;
  toolCallId: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
};

export type ToolResultPayload = {
  agentId: string;
  toolCallId: string;
  toolName: string;
  resultPreview: string;
};

export type CurrentGroupRuntimeEventType =
  | "user_message"
  | "moderator_note_ready"
  | "agent_message"
  | "conversation_updated"
  | "done"
  | "error"
  | "tool_call"
  | "tool_result";

export type ReservedFutureGroupRuntimeEventType =
  | "agent_thinking"
  | "dispatch_progress";

export type GroupRuntimeEventType =
  | CurrentGroupRuntimeEventType
  | ReservedFutureGroupRuntimeEventType;

export type CurrentGroupRuntimeDispatchStrategy = "broadcast_chain";

export type ReservedFutureGroupRuntimeDispatchStrategy =
  | "round_robin"
  | "parallel_fan_out"
  | "manual_handoff";

export type GroupRuntimeDispatchStrategy =
  | CurrentGroupRuntimeDispatchStrategy
  | ReservedFutureGroupRuntimeDispatchStrategy;

export type GroupRuntimeHooks = {
  dispatchStrategy: GroupRuntimeDispatchStrategy;
  triggerEventType: GroupRuntimeEventType;
  reservedEventTypes: CurrentGroupRuntimeEventType[];
  reservedDispatchStrategies: CurrentGroupRuntimeDispatchStrategy[];
  reservedFutureEventTypes: ReservedFutureGroupRuntimeEventType[];
  reservedFutureDispatchStrategies: ReservedFutureGroupRuntimeDispatchStrategy[];
  [key: string]: unknown;
};

type GroupMessageStreamPayloadBase = {
  conversationId: string;
  conversationUpdatedAt?: string | null;
  runtimeHooks?: GroupRuntimeHooks | null;
};

type GroupMessageStreamMessageEvent = {
  event: "user_message" | "agent_message";
  payload: GroupMessageStreamPayloadBase & {
    message: Message;
  };
};

type GroupMessageStreamLifecycleEvent = {
  event: "moderator_note_ready" | "conversation_updated" | "done";
  payload: GroupMessageStreamPayloadBase;
};

type GroupMessageStreamErrorEvent = {
  event: "error";
  payload: GroupMessageStreamPayloadBase & {
    error: StreamErrorDetail;
  };
};

type GroupMessageStreamToolCallEvent = {
  event: "tool_call";
  payload: GroupMessageStreamPayloadBase & ToolCallPayload;
};

type GroupMessageStreamToolResultEvent = {
  event: "tool_result";
  payload: GroupMessageStreamPayloadBase & ToolResultPayload;
};

type GroupMessageStreamReservedFutureEvent = {
  event: ReservedFutureGroupRuntimeEventType;
  payload: GroupMessageStreamPayloadBase & {
    message?: Message;
    error?: StreamErrorDetail;
    [key: string]: unknown;
  };
};

export type GroupMessageStreamEvent =
  | GroupMessageStreamMessageEvent
  | GroupMessageStreamLifecycleEvent
  | GroupMessageStreamErrorEvent
  | GroupMessageStreamToolCallEvent
  | GroupMessageStreamToolResultEvent
  | GroupMessageStreamReservedFutureEvent;

export type SendMessagePayload = {
  conversationId: string;
  content: string;
  attachments?: Attachment[];
};

export type ImageAttachmentUploadResponse = {
  id: string;
  attachmentId?: string;
  type: "image";
  mimeType: string;
  previewUrl: string;
  expiresAt: string | null;
};

export type LlmSettings = {
  provider: string;
  model: string;
  hasApiKey: boolean;
};

export type LlmSettingsUpdate = {
  provider: string;
  model: string;
  apiKey: string;
};

export type BulkDeleteConversationsResponse = {
  deletedCount: number;
  remainingConversationIds: string[];
};
