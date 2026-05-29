import type { Message } from "../types/chat";

const THINK_TAG_PATTERN = /<think\b[^>]*>[\s\S]*?<\/think>/gi;
const CODE_FENCE_PATTERN = /```[\s\S]*?```/g;
const CODE_FENCE_DELIMITER_PATTERN = /^\s*```/;
const HEADING_LINE_PATTERN = /^\s{0,3}#{1,6}\s+\S/;
const INLINE_HEADING_PATTERN =
  /^(.*(?:[。！？!?：:；;]|-{2,}|👇|👉|➡️|→))\s*(#{1,6}\s+\S.*)$/;
const TABLE_LINE_PATTERN = /^\s*\|(?:.*\|)+\s*$/;
const TABLE_DIVIDER_PATTERN = /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$/;

export function sanitizeMessageContent(content: string): string {
  return content.replace(THINK_TAG_PATTERN, "").trim();
}

function pushBlankLine(lines: string[]): void {
  if (lines.length === 0 || lines[lines.length - 1] === "") {
    return;
  }
  lines.push("");
}

function trimBlankLines(lines: string[]): string[] {
  const trimmed = [...lines];
  while (trimmed[0] === "") {
    trimmed.shift();
  }
  while (trimmed[trimmed.length - 1] === "") {
    trimmed.pop();
  }
  return trimmed;
}

function normalizeMarkdownTextLines(lines: string[]): string[] {
  const normalized: string[] = [];

  for (let index = 0; index < lines.length; ) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      pushBlankLine(normalized);
      index += 1;
      continue;
    }

    const inlineHeadingMatch = line.match(INLINE_HEADING_PATTERN);
    if (inlineHeadingMatch) {
      const prefix = inlineHeadingMatch[1].trimEnd();
      const heading = inlineHeadingMatch[2].trim();
      normalized.push(prefix);
      pushBlankLine(normalized);
      normalized.push(heading);
      if (index + 1 < lines.length && lines[index + 1].trim()) {
        pushBlankLine(normalized);
      }
      index += 1;
      continue;
    }

    if (HEADING_LINE_PATTERN.test(trimmed)) {
      pushBlankLine(normalized);
      normalized.push(trimmed);
      if (index + 1 < lines.length && lines[index + 1].trim()) {
        pushBlankLine(normalized);
      }
      index += 1;
      continue;
    }

    if (TABLE_LINE_PATTERN.test(trimmed)) {
      const tableLines: string[] = [];
      let cursor = index;

      while (cursor < lines.length && TABLE_LINE_PATTERN.test(lines[cursor].trim())) {
        tableLines.push(lines[cursor].trim());
        cursor += 1;
      }

      const hasDivider = tableLines.some((tableLine) => TABLE_DIVIDER_PATTERN.test(tableLine));
      if (tableLines.length >= 2 && hasDivider) {
        pushBlankLine(normalized);
        normalized.push(...tableLines);
        if (cursor < lines.length && lines[cursor].trim()) {
          pushBlankLine(normalized);
        }
        index = cursor;
        continue;
      }
    }

    normalized.push(line);
    index += 1;
  }

  return trimBlankLines(normalized);
}

export function normalizeMarkdownBlocks(content: string): string {
  const normalizedContent = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const lines = normalizedContent.split("\n");
  const output: string[] = [];
  const textBuffer: string[] = [];
  let insideCodeFence = false;

  const flushTextBuffer = () => {
    if (textBuffer.length === 0) {
      return;
    }
    output.push(...normalizeMarkdownTextLines(textBuffer));
    textBuffer.length = 0;
  };

  for (const line of lines) {
    if (CODE_FENCE_DELIMITER_PATTERN.test(line)) {
      flushTextBuffer();
      output.push(line);
      insideCodeFence = !insideCodeFence;
      continue;
    }

    if (insideCodeFence) {
      output.push(line);
      continue;
    }

    textBuffer.push(line);
  }

  flushTextBuffer();
  return trimBlankLines(output).join("\n");
}

export function toPreviewText(content: string): string {
  return sanitizeMessageContent(content)
    .replace(CODE_FENCE_PATTERN, " [代码片段] ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^\s{0,3}(#{1,6}|>|\-|\*|\+)\s+/gm, "")
    .replace(/^\s{0,3}\d+\.\s+/gm, "")
    .replace(/\r?\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function getMessagePreviewText(message: Message, maxLength = 24): string | null {
  const previewText = toPreviewText(message.content);
  if (previewText) {
    return previewText.length > maxLength ? `${previewText.slice(0, maxLength)}…` : previewText;
  }

  const attachmentCount = message.attachments?.length ?? 0;
  if (attachmentCount > 0) {
    return attachmentCount === 1 ? "[图片附件]" : `[${attachmentCount} 个图片附件]`;
  }

  return null;
}
