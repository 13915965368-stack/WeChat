import type { ComponentPropsWithoutRef } from "react";
import rehypeSanitize from "rehype-sanitize";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { normalizeMarkdownBlocks, sanitizeMessageContent } from "../../utils/messageContent";

type Props = {
  content: string;
};

function InlineCode({ className, children, ...props }: ComponentPropsWithoutRef<"code">) {
  const languageMatch = className?.match(/language-([\w-]+)/);
  if (languageMatch) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  return (
    <code
      className="rounded bg-[#F5F0E8] px-1 py-0.5 text-[0.92em] text-[#5D554F]"
      {...props}
    >
      {children}
    </code>
  );
}

export function MessageMarkdown({ content }: Props) {
  const sanitized = sanitizeMessageContent(content);
  const normalized = normalizeMarkdownBlocks(sanitized);

  if (!normalized) {
    return null;
  }

  return (
    <div className="markdown-body space-y-3 text-[15px] leading-7 text-[#2D2926]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h1: ({ children }) => <h1 className="text-base font-semibold text-[#2D2926]">{children}</h1>,
          h2: ({ children }) => <h2 className="text-[15px] font-semibold text-[#2D2926]">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold text-[#2D2926]">{children}</h3>,
          p: ({ children }) => <p className="break-words [overflow-wrap:anywhere]">{children}</p>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          blockquote: ({ children }) => (
            <blockquote
              className="border-l-2 pl-4 text-sm italic"
              style={{ borderColor: "#D9D2C8", color: "var(--text-secondary)" }}
            >
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-[#5B7BA3] underline underline-offset-2"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto rounded-2xl border border-[var(--border-light)]">
              <table className="min-w-full border-collapse text-left text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-[#F8F6F2]">{children}</thead>,
          th: ({ children }) => (
            <th className="border-b border-[var(--border-light)] px-3 py-2 font-medium">{children}</th>
          ),
          td: ({ children }) => <td className="border-b border-[var(--border-light)] px-3 py-2">{children}</td>,
          code: InlineCode,
          pre: ({ children }) => (
            <pre className="overflow-x-auto rounded-2xl bg-[#F5F0E8] px-4 py-3 text-xs leading-relaxed text-[#5D554F]">
              {children}
            </pre>
          ),
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
