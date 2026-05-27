import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createDirectConversation,
  createGroupConversation,
  createModelConfig,
  getAgents,
  getModelConfigs,
  sendGroupMessageStream,
  sendMessage,
  uploadImageAttachment,
} from "../api/chat";

const fetchMock = vi.fn<typeof fetch>();

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(chunks: string[], status = 200) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("chat api HTTP 适配层", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("将后端 ModelConfig capabilities 映射为前端扁平字段", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        {
          id: "model-openai",
          provider: "openai",
          model: "gpt-4o-mini",
          displayName: "OpenAI - GPT-4o Mini",
          apiFormat: "openai",
          baseUrl: "https://api.openai.com/v1",
          useFullUrl: false,
          status: "available",
          statusMessage: "validated",
          apiKeyConfigured: true,
          lastValidatedAt: "2026-05-26T10:00:00.000Z",
          createdAt: "2026-05-26T09:00:00.000Z",
          updatedAt: "2026-05-26T10:00:00.000Z",
          capabilities: {
            supportsImageInput: true,
            supportsFileInput: false,
            supportsStreaming: true,
            contextWindow: 128000,
          },
        },
      ])
    );

    const modelConfigs = await getModelConfigs();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/model-configs", expect.any(Object));
    expect(modelConfigs).toEqual([
      expect.objectContaining({
        id: "model-openai",
        supportsImageInput: true,
        supportsFileInput: false,
        supportsStreaming: true,
        supportsSystemPrompt: true,
        contextWindowInput: 128000,
        contextWindowOutput: null,
        apiKeyConfigured: true,
      }),
    ]);
  });

  it("保留页面 createDirectConversation 调用语义并映射会话字段", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "conv-1",
        type: "direct",
        title: "空白对话",
        memberIds: ["user", "blank-agent"],
        agentId: "blank-agent",
        modelConfigId: "model-openai",
        isDisabled: false,
        createdAt: "2026-05-26T10:00:00.000Z",
        updatedAt: "2026-05-26T10:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      }, 201)
    );

    const conversation = await createDirectConversation("blank-agent", "空白对话", {
      modelConfigId: "model-openai",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/conversations/direct",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          agentId: "blank-agent",
          title: "空白对话",
          modelConfigId: "model-openai",
        }),
      })
    );
    expect(conversation).toEqual(
      expect.objectContaining({
        id: "conv-1",
        agentId: "blank-agent",
        modelConfigId: "model-openai",
        isDisabled: false,
      })
    );
  });

  it("创建群聊时会传递 sourceConversationId 并映射返回的来源字段", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "group-1",
        type: "group",
        title: "评审群",
        memberIds: ["user", "architect", "critic"],
        sourceConversationId: "direct-architect",
        modelConfigId: null,
        runtimeMetadata: {
          group_runtime: {
            protocol: {
              version: "group_runtime_v1",
              mode: "fixed_group_chat",
              thread_id: "default",
              scope: "conversation_default_thread",
            },
            default_thread: {
              thread_id: "default",
              kind: "conversation_default_thread",
              moderator_note: {
                status: "pending",
                content: null,
                generated_by_agent_id: null,
                generated_at: null,
                input: null,
              },
              event_window: {
                version: "group_event_window_v1",
                events: [],
                last_event_id: null,
                last_event_type: null,
              },
              dispatch_state: {
                status: "idle",
                strategy: "broadcast_chain",
                trigger_event_id: null,
                cursor: 0,
                pending_member_ids: [],
                completed_member_ids: [],
                last_completed_event_id: null,
              },
            },
          },
        },
        isDisabled: false,
        createdAt: "2026-05-26T10:00:00.000Z",
        updatedAt: "2026-05-26T10:00:00.000Z",
        pinned: false,
        pinnedAt: null,
      }, 201)
    );

    const conversation = await createGroupConversation({
      title: "评审群",
      memberIds: ["architect", "critic"],
      sourceConversationId: "direct-architect",
      historyRounds: 1,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/conversations/group",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "评审群",
          memberIds: ["architect", "critic"],
          sourceConversationId: "direct-architect",
          includeContext: true,
          contextRounds: 1,
        }),
      })
    );
    expect(conversation).toEqual(
      expect.objectContaining({
        id: "group-1",
        type: "group",
        sourceConversationId: "direct-architect",
        runtimeMetadata: expect.objectContaining({
          groupRuntime: expect.objectContaining({
            protocol: expect.objectContaining({
              version: "group_runtime_v1",
              threadId: "default",
            }),
            defaultThread: expect.objectContaining({
              threadId: "default",
              moderatorNote: expect.objectContaining({
                generatedByAgentId: null,
                generatedAt: null,
              }),
              dispatchState: expect.objectContaining({
                triggerEventId: null,
                pendingMemberIds: [],
                completedMemberIds: [],
                lastCompletedEventId: null,
              }),
            }),
          }),
        }),
      })
    );
  });

  it("发送消息时将前端 Attachment 转成后端 attachmentId 并映射返回消息", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          userMessage: {
            id: "msg-user",
            conversationId: "conv-1",
            senderType: "user",
            senderId: "user",
            content: "请结合图片给建议",
            createdAt: "2026-05-26T10:01:00.000Z",
            attachments: [
              {
                attachmentId: "att-1",
                kind: "image",
                mimeType: "image/png",
                name: "wireframe.png",
                size: 2048,
                previewUrl: "https://example.com/wireframe.png",
                expiresAt: "2026-06-01T00:00:00.000Z",
                metadata: { width: 1280, height: 720 },
              },
            ],
          },
          agentMessages: [
            {
              id: "msg-agent",
              conversationId: "conv-1",
              senderType: "agent",
              senderId: "architect",
              content: "我先给一个结构化建议。",
              createdAt: "2026-05-26T10:01:01.000Z",
              attachments: [],
            },
          ],
          conversationUpdatedAt: "2026-05-26T10:01:01.000Z",
        },
        201
      )
    );

    const response = await sendMessage({
      conversationId: "conv-1",
      content: "请结合图片给建议",
      attachments: [
        {
          id: "att-1",
          type: "image",
          source: "upload",
          mimeType: "image/png",
          previewUrl: "https://example.com/wireframe.png",
        },
      ],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/messages",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          conversationId: "conv-1",
          content: "请结合图片给建议",
          attachments: [
            {
              attachmentId: "att-1",
              kind: "image",
              mimeType: "image/png",
              name: undefined,
              size: undefined,
              previewUrl: "https://example.com/wireframe.png",
              expiresAt: null,
              metadata: {},
            },
          ],
        }),
      })
    );
    expect(response.userMessage.attachments?.[0]).toEqual(
      expect.objectContaining({
        id: "att-1",
        attachmentId: "att-1",
        type: "image",
        kind: "image",
        name: "wireframe.png",
        size: 2048,
      })
    );
    expect(response.agentMessages[0]?.attachments).toEqual([]);
  });

  it("群聊 SSE 会消费分片事件流并映射成逐条事件", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: user_message\ndata: {"event":"user_message","payload":{"conversationId":"group-1","message":{"id":"msg-user","conversationId":"group-1","senderType":"user","senderId":"user","content":"请开始","createdAt":"2026-05-26T10:01:00.000Z","attachments":[]},"runtimeHooks":{"dispatch_strategy":"broadcast_chain","trigger_event_type":"user_message","reserved_event_types":["user_message","moderator_note_ready","agent_message","conversation_updated","done","error"],"reserved_dispatch_strategies":["broadcast_chain"]}}}\n\n'
          .slice(0, 80),
        'event: user_message\ndata: {"event":"user_message","payload":{"conversationId":"group-1","message":{"id":"msg-user","conversationId":"group-1","senderType":"user","senderId":"user","content":"请开始","createdAt":"2026-05-26T10:01:00.000Z","attachments":[]},"runtimeHooks":{"dispatch_strategy":"broadcast_chain","trigger_event_type":"user_message","reserved_event_types":["user_message","moderator_note_ready","agent_message","conversation_updated","done","error"],"reserved_dispatch_strategies":["broadcast_chain"]}}}\n\n'
          .slice(80),
        'event: agent_message\ndata: {"event":"agent_message","payload":{"conversationId":"group-1","message":{"id":"msg-agent","conversationId":"group-1","senderType":"agent","senderId":"architect","content":"先拆结构。","createdAt":"2026-05-26T10:01:01.000Z","attachments":[]},"conversationUpdatedAt":"2026-05-26T10:01:01.000Z","runtimeHooks":{"dispatch_strategy":"broadcast_chain","trigger_event_type":"user_message","reserved_event_types":["user_message","moderator_note_ready","agent_message","conversation_updated","done","error"],"reserved_dispatch_strategies":["broadcast_chain"]}}}\n\nevent: done\ndata: {"event":"done","payload":{"conversationId":"group-1","conversationUpdatedAt":"2026-05-26T10:01:01.000Z","runtimeHooks":{"dispatch_strategy":"broadcast_chain","trigger_event_type":"user_message","reserved_event_types":["user_message","moderator_note_ready","agent_message","conversation_updated","done","error"],"reserved_dispatch_strategies":["broadcast_chain"]}}}\n\n',
      ])
    );

    const events: Array<{ event: string; payload: Record<string, unknown> }> = [];

    await sendGroupMessageStream(
      {
        conversationId: "group-1",
        content: "请开始",
      },
      (event) => events.push(event as { event: string; payload: Record<string, unknown> })
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/messages/stream",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        }),
        body: JSON.stringify({
          conversationId: "group-1",
          content: "请开始",
          attachments: [],
        }),
      })
    );
    expect(events).toEqual([
      {
        event: "user_message",
        payload: {
          conversationId: "group-1",
          message: expect.objectContaining({
            id: "msg-user",
            senderType: "user",
            senderId: "user",
            content: "请开始",
          }),
          conversationUpdatedAt: null,
          runtimeHooks: {
            dispatchStrategy: "broadcast_chain",
            triggerEventType: "user_message",
            reservedEventTypes: [
              "user_message",
              "moderator_note_ready",
              "agent_message",
              "conversation_updated",
              "done",
              "error",
            ],
            reservedDispatchStrategies: ["broadcast_chain"],
            reservedFutureEventTypes: [],
            reservedFutureDispatchStrategies: [],
          },
        },
      },
      {
        event: "agent_message",
        payload: {
          conversationId: "group-1",
          message: expect.objectContaining({
            id: "msg-agent",
            senderType: "agent",
            senderId: "architect",
            content: "先拆结构。",
          }),
          conversationUpdatedAt: "2026-05-26T10:01:01.000Z",
          runtimeHooks: expect.objectContaining({
            dispatchStrategy: "broadcast_chain",
            triggerEventType: "user_message",
            reservedFutureEventTypes: [],
          }),
        },
      },
      {
        event: "done",
        payload: {
          conversationId: "group-1",
          conversationUpdatedAt: "2026-05-26T10:01:01.000Z",
          runtimeHooks: expect.objectContaining({
            dispatchStrategy: "broadcast_chain",
            reservedDispatchStrategies: ["broadcast_chain"],
            reservedFutureDispatchStrategies: [],
          }),
        },
      },
    ]);
  });

  it("群聊 SSE 会透传保留 future event，并映射 future hooks 字段", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        'event: dispatch_progress\ndata: {"event":"dispatch_progress","payload":{"conversationId":"group-1","conversationUpdatedAt":"2026-05-26T10:01:00.000Z","runtimeHooks":{"dispatch_strategy":"round_robin","trigger_event_type":"dispatch_progress","reserved_event_types":["user_message","moderator_note_ready","agent_message","conversation_updated","done","error"],"reserved_dispatch_strategies":["broadcast_chain"],"reserved_future_event_types":["agent_thinking","tool_call","tool_result","dispatch_progress"],"reserved_future_dispatch_strategies":["round_robin","parallel_fan_out","manual_handoff"]}}}\n\n',
      ])
    );

    const events: Array<{ event: string; payload: Record<string, unknown> }> = [];

    await sendGroupMessageStream(
      {
        conversationId: "group-1",
        content: "请开始",
      },
      (event) => events.push(event as { event: string; payload: Record<string, unknown> })
    );

    expect(events).toEqual([
      {
        event: "dispatch_progress",
        payload: {
          conversationId: "group-1",
          message: undefined,
          conversationUpdatedAt: "2026-05-26T10:01:00.000Z",
          error: undefined,
          runtimeHooks: {
            dispatchStrategy: "round_robin",
            triggerEventType: "dispatch_progress",
            reservedEventTypes: [
              "user_message",
              "moderator_note_ready",
              "agent_message",
              "conversation_updated",
              "done",
              "error",
            ],
            reservedDispatchStrategies: ["broadcast_chain"],
            reservedFutureEventTypes: [
              "agent_thinking",
              "tool_call",
              "tool_result",
              "dispatch_progress",
            ],
            reservedFutureDispatchStrategies: [
              "round_robin",
              "parallel_fan_out",
              "manual_handoff",
            ],
          },
        },
      },
    ]);
  });

  it("群聊 SSE 请求失败时保留 ApiError 语义", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          error: {
            code: "conversation_not_streamable",
            message: "Streaming is only supported for group conversations",
          },
        },
        409
      )
    );

    await expect(
      sendGroupMessageStream(
        {
          conversationId: "direct-1",
          content: "不应该流式",
        },
        () => undefined
      )
    ).rejects.toMatchObject({
      status: 409,
      code: "conversation_not_streamable",
      message: "Streaming is only supported for group conversations",
    });
  });

  it("将上传接口返回的 attachmentId 映射为前端上传结果", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          attachmentId: "att-uploaded",
          mimeType: "image/png",
          previewUrl: "/api/v1/attachments/images/att-uploaded/preview",
          expiresAt: "2026-06-01T00:00:00.000Z",
        },
        201
      )
    );

    const file = new File(["demo"], "wireframe.png", { type: "image/png" });
    const uploaded = await uploadImageAttachment(file, "conv-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/attachments/images",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      })
    );
    expect(uploaded).toEqual({
      id: "att-uploaded",
      attachmentId: "att-uploaded",
      type: "image",
      mimeType: "image/png",
      previewUrl: "/api/v1/attachments/images/att-uploaded/preview",
      expiresAt: "2026-06-01T00:00:00.000Z",
    });
  });

  it("透传后端业务错误码并保留 ApiError 状态", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          error: {
            code: "IMAGE_NOT_SUPPORTED",
            message: "image attachments are not supported by the current model",
          },
        },
        422
      )
    );

    await expect(
      sendMessage({
        conversationId: "conv-1",
        content: "请结合图片给建议",
        attachments: [{ id: "att-1", type: "image", mimeType: "image/png" }],
      })
    ).rejects.toMatchObject({
      status: 422,
      code: "IMAGE_NOT_SUPPORTED",
      message: "image attachments are not supported by the current model",
    });
  });

  it("读取 Agent 列表时保留模板与模型状态字段", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        {
          id: "blank-agent",
          name: "空白 Agent",
          roleSummary: "用于纯净对话",
          styleSummary: "不预设风格",
          systemPrompt: "",
          avatar: "B",
          avatarImage: null,
          themeColor: null,
          themeLight: null,
          themeSoft: null,
          modelConfigId: null,
          modelUnavailable: false,
          isTemplate: true,
          pinned: false,
          pinnedAt: null,
        },
      ])
    );

    const agents = await getAgents();

    expect(agents[0]).toEqual(
      expect.objectContaining({
        id: "blank-agent",
        isTemplate: true,
        modelConfigId: null,
        modelUnavailable: false,
      })
    );
  });

  it("创建模型配置时将前端扁平能力字段打包到 capabilities", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          id: "model-created",
          provider: "openai",
          model: "gpt-4o",
          displayName: "OpenAI - GPT-4o",
          apiFormat: "openai",
          baseUrl: "https://api.openai.com/v1",
          useFullUrl: false,
          status: "available",
          statusMessage: null,
          apiKeyConfigured: true,
          lastValidatedAt: "2026-05-26T10:00:00.000Z",
          createdAt: "2026-05-26T10:00:00.000Z",
          updatedAt: "2026-05-26T10:00:00.000Z",
          capabilities: {
            supportsImageInput: true,
            supportsFileInput: false,
            supportsStreaming: false,
            contextWindow: 128000,
          },
        },
        201
      )
    );

    await createModelConfig({
      provider: "openai",
      model: "gpt-4o",
      displayName: "OpenAI - GPT-4o",
      apiFormat: "openai",
      baseUrl: "https://api.openai.com/v1",
      useFullUrl: false,
      apiKey: "demo-key",
      supportsImageInput: true,
      supportsFileInput: false,
      supportsStreaming: false,
      contextWindowInput: 128000,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/model-configs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          provider: "openai",
          model: "gpt-4o",
          displayName: "OpenAI - GPT-4o",
          apiFormat: "openai",
          baseUrl: "https://api.openai.com/v1",
          useFullUrl: false,
          apiKey: "demo-key",
          capabilities: {
            supportsImageInput: true,
            supportsFileInput: false,
            supportsStreaming: false,
            contextWindow: 128000,
          },
        }),
      })
    );
  });
});
