import type { Message } from "../types/chat";

export function mergeMessageList(messages: Message[], ...nextMessages: Message[]): Message[] {
  return nextMessages.reduce<Message[]>((currentMessages, nextMessage) => {
    const existingIndex = currentMessages.findIndex((message) => message.id === nextMessage.id);
    if (existingIndex === -1) {
      return [...currentMessages, nextMessage];
    }

    return currentMessages.map((message) =>
      message.id === nextMessage.id ? nextMessage : message
    );
  }, messages);
}

export function replaceOptimisticMessage(
  messages: Message[],
  temporaryId: string,
  confirmedMessage: Message
): Message[] {
  return messages.map((message) =>
    message.id === temporaryId ? confirmedMessage : message
  );
}
