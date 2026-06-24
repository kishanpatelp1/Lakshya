import { useEffect, useRef, useState } from "react";
import { searchCompaniesDB, type AICompany } from "../lib/api";
import { Icon } from "./Icon";

interface Props {
  placeholder?: string;
  onSelect: (company: AICompany) => void;
  className?: string;
}

export function CompanySearch({ placeholder = "Search a company…", onSelect, className = "" }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<AICompany[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await searchCompaniesDB(q, 8);
        setResults(r);
        setOpen(true);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <div className="flex items-center bg-bg-0 border border-outline-variant rounded px-md py-sm focus-within:border-primary/50 transition-colors">
        <Icon name="search" className="text-on-surface-variant text-[18px] mr-sm" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          placeholder={placeholder}
          className="bg-transparent text-body-sm text-on-surface focus:outline-none w-full placeholder:text-on-surface-variant"
        />
        {loading && <Icon name="progress_activity" className="text-on-surface-variant text-[16px] animate-spin" />}
      </div>
      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-bg-1 border border-outline-variant rounded-md shadow-lg max-h-64 overflow-y-auto">
          {results.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                onSelect(c);
                setQ("");
                setResults([]);
                setOpen(false);
              }}
              className="w-full text-left px-md py-sm hover:bg-bg-2 flex items-center justify-between gap-sm"
            >
              <span className="text-body-sm text-on-surface truncate">{c.name}</span>
              <span className="text-caption text-on-surface-variant shrink-0">{c.ticker_nse ?? c.ticker_bse ?? ""}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
