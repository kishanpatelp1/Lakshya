import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Themed markdown renderer used for all streamed AI output. */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: (p) => <h3 className="text-section-header text-on-surface mt-lg mb-sm first:mt-0" {...p} />,
        h2: (p) => <h3 className="text-card-title uppercase tracking-caps text-on-surface mt-lg mb-sm first:mt-0" {...p} />,
        h3: (p) => <h4 className="text-body-md font-semibold text-on-surface mt-md mb-xs" {...p} />,
        p: (p) => <p className="text-body-md text-on-surface-variant leading-relaxed mb-md" {...p} />,
        strong: (p) => <strong className="text-on-surface font-semibold" {...p} />,
        em: (p) => <em className="text-on-surface-variant italic" {...p} />,
        ul: (p) => <ul className="list-disc pl-lg space-y-xs mb-md text-on-surface-variant" {...p} />,
        ol: (p) => <ol className="list-decimal pl-lg space-y-xs mb-md text-on-surface-variant" {...p} />,
        li: (p) => <li className="text-body-md leading-relaxed marker:text-primary" {...p} />,
        a: (p) => <a className="text-primary hover:underline" target="_blank" rel="noreferrer" {...p} />,
        code: (p) => <code className="text-primary bg-bg-2 rounded px-1 py-[1px] text-body-sm" {...p} />,
        hr: () => <hr className="border-outline-variant/50 my-md" />,
        table: (p) => (
          <div className="overflow-x-auto mb-md rounded-md border border-outline-variant">
            <table className="w-full text-body-sm border-collapse" {...p} />
          </div>
        ),
        thead: (p) => <thead className="bg-bg-2" {...p} />,
        th: (p) => <th className="text-left text-label-caps font-label-caps text-on-surface-variant px-md py-sm border-b border-outline-variant" {...p} />,
        td: (p) => <td className="px-md py-sm text-body-sm text-on-surface border-b border-outline-variant/40 align-top" {...p} />,
        tr: (p) => <tr className="hover:bg-bg-2/40 transition-colors" {...p} />,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
