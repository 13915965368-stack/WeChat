import type { Conversation, Message } from "../types/chat";

export const mockConversations: Conversation[] = [
  {
    id: "direct-architect-default",
    type: "direct",
    title: "默认对话",
    memberIds: ["user", "architect"],
    agentId: "architect",
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
  },
  {
    id: "group-1",
    type: "group",
    title: "产品方案讨论",
    memberIds: ["user", "architect", "critic", "writer"],
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 38).toISOString(),
  },
];

export const mockMessages: Message[] = [
  // Architect 默认单聊消息
  {
    id: "msg-1",
    conversationId: "direct-architect-default",
    senderType: "agent",
    senderId: "architect",
    content: "我们可以先把产品目标压缩成最小可运行版本。",
    createdAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
  },
  {
    id: "msg-2",
    conversationId: "direct-architect-default",
    senderType: "user",
    senderId: "user",
    content: "好，你觉得第一版应该包含哪些核心功能？",
    createdAt: new Date(Date.now() - 1000 * 60 * 4).toISOString(),
  },
  {
    id: "msg-3",
    conversationId: "direct-architect-default",
    senderType: "agent",
    senderId: "architect",
    content: "我的建议是：先做出单 Agent 直聊，再支持从直聊发起群聊。群聊里让多个 Agent 依次发言，最后把消息持久化。",
    createdAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
  },
  // 群聊消息
  {
    id: "gmsg-1",
    conversationId: "group-1",
    senderType: "user",
    senderId: "user",
    content: "我们来讨论一下第一版产品的核心功能吧。",
    createdAt: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
  },
  {
    id: "gmsg-2",
    conversationId: "group-1",
    senderType: "agent",
    senderId: "architect",
    content: "我的看法是：第一版应该聚焦在「单 Agent 直聊 + 群聊协作」这两个核心体验上。先让用户能顺畅地和单个 Agent 对话，再自然地拉起群聊。",
    createdAt: new Date(Date.now() - 1000 * 60 * 44).toISOString(),
  },
  {
    id: "gmsg-3",
    conversationId: "group-1",
    senderType: "agent",
    senderId: "critic",
    content: "我同意这个方向，但有个风险点：群聊的复杂度会不会让第一版变得太重？我们需要明确群聊的最小功能集。",
    createdAt: new Date(Date.now() - 1000 * 60 * 43).toISOString(),
  },
  {
    id: "gmsg-4",
    conversationId: "group-1",
    senderType: "agent",
    senderId: "writer",
    content: "从表达角度，我建议群聊界面要让人感受到「讨论的自然流动」，而不是一堆机器人在轮流播报。每个 Agent 的发言风格应该保持差异化。",
    createdAt: new Date(Date.now() - 1000 * 60 * 42).toISOString(),
  },
  {
    id: "gmsg-5",
    conversationId: "group-1",
    senderType: "user",
    senderId: "user",
    content: "很好的观点。那群聊的最小功能集应该包含哪些？",
    createdAt: new Date(Date.now() - 1000 * 60 * 40).toISOString(),
  },
  {
    id: "gmsg-6",
    conversationId: "group-1",
    senderType: "agent",
    senderId: "architect",
    content: "我来梳理一下：1) 群成员管理（添加/移除 Agent）2) 消息流（支持多 Agent 依次发言）3) 群档案（沉淀讨论要点）4) 模式切换（brainstorming / collaboration / decision）",
    createdAt: new Date(Date.now() - 1000 * 60 * 38).toISOString(),
  },
];
