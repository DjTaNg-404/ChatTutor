import { useMemo } from "react";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkMath from "remark-math";
import remarkRehype from "remark-rehype";
import rehypeKatex from "rehype-katex";
import rehypeStringify from "rehype-stringify";

import "katex/dist/katex.min.css";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

let processor: ReturnType<typeof createProcessor> | null = null;

function createProcessor() {
  return (
    unified()
      .use(remarkParse)
      .use(remarkMath)
      .use(remarkRehype, { allowDangerousHtml: false })
      .use(rehypeKatex, { throwOnError: false, strict: "ignore" as const })
      .use(rehypeStringify)
  );
}

function getProcessor() {
  if (!processor) {
    processor = createProcessor();
  }
  return processor;
}

/** Markdown + KaTeX → HTML，写入单一 DOM 容器，避免 React 子 Fiber 与 KaTeX 改写 DOM 冲突（insertBefore NotFoundError） */
export function assistantMarkdownToHtml(source: string): string {
  const raw = source ?? "";
  if (!raw.trim()) return "";
  try {
    return String(getProcessor().processSync(raw));
  } catch {
    return `<p>${escapeHtml(raw)}</p>`;
  }
}

export function AssistantMarkdownHtml({ content }: { content: string }) {
  const html = useMemo(() => assistantMarkdownToHtml(content), [content]);
  if (!html) {
    return null;
  }
  return (
    <div
      className="assistant-md-html text-gray-800 leading-relaxed [overflow-wrap:anywhere]"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
