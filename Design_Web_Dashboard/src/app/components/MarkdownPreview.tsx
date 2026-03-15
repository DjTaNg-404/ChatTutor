import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";

import "katex/dist/katex.min.css";
import "highlight.js/styles/github.css";

interface MarkdownPreviewProps {
  content: string;
  className?: string;
}

export function MarkdownPreview({ content, className = "" }: MarkdownPreviewProps) {
  return (
    <div className={`prose prose-sm max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={{
          h1: ({ node, ...props }) => (
            <h1 className="text-2xl font-bold mt-6 mb-4 text-gray-900" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-xl font-semibold mt-5 mb-3 text-gray-900" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-lg font-medium mt-4 mb-2 text-gray-900" {...props} />
          ),
          p: ({ node, ...props }) => (
            <p className="my-3 leading-relaxed text-gray-700" {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ul className="my-3 ml-6 list-disc space-y-1 text-gray-700" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="my-3 ml-6 list-decimal space-y-1 text-gray-700" {...props} />
          ),
          li: ({ node, ...props }) => (
            <li className="leading-relaxed" {...props} />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="border-l-4 border-indigo-500 pl-4 my-4 italic text-gray-600 bg-gray-50 py-2 pr-4 rounded-r"
              {...props}
            />
          ),
          code: ({ node, inline, ...props }: any) => {
            if (inline) {
              return (
                <code
                  className="rounded px-1.5 py-0.5 text-sm font-mono text-indigo-600"
                  {...props}
                />
              );
            }
            return <code className="text-sm font-mono" {...props} />;
          },
          pre: ({ node, ...props }) => (
            <pre
              className="bg-gray-900 text-gray-100 rounded-lg p-4 my-4 overflow-x-auto"
              {...props}
            />
          ),
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-4">
              <table className="min-w-full border-collapse border border-gray-300" {...props} />
            </div>
          ),
          th: ({ node, ...props }) => (
            <th
              className="border border-gray-300 px-4 py-2 text-left text-sm font-semibold bg-gray-50"
              {...props}
            />
          ),
          td: ({ node, ...props }) => (
            <td
              className="border border-gray-300 px-4 py-2 text-sm"
              {...props}
            />
          ),
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-gray-900" {...props} />
          ),
          em: ({ node, ...props }) => (
            <em className="italic text-gray-700" {...props} />
          ),
          a: ({ node, ...props }) => (
            <a
              className="text-indigo-600 hover:text-indigo-800 underline"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
          hr: ({ node, ...props }) => (
            <hr className="my-6 border-gray-200" {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
