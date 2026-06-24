import { useEffect, useState } from "react";
import {
  fetchCompanyFilings,
  type CompanyFiling,
  type AICompany,
} from "../lib/api";
import { Card, Chip, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { CompanySearch } from "../components/CompanySearch";

function filingIcon(type: string): string {
  const t = type.toLowerCase();
  if (t.includes("annual")) return "menu_book";
  if (t.includes("quarter") || t.includes("result")) return "assessment";
  if (t.includes("board") || t.includes("meeting")) return "groups";
  if (t.includes("announce")) return "campaign";
  return "description";
}

export function FilingsView() {
  const [company, setCompany] = useState<AICompany | null>(null);
  const [filings, setFilings] = useState<CompanyFiling[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<string>("all");

  useEffect(() => {
    if (!company) {
      setFilings([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCompanyFilings(company.id, 40)
      .then((f) => !cancelled && setFilings(f))
      .catch(() => !cancelled && setError("Could not load filings for this company."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [company?.id]);

  const types = ["all", ...Array.from(new Set(filings.map((f) => f.filing_type)))];
  const shown = type === "all" ? filings : filings.filter((f) => f.filing_type === type);

  return (
    <div className="space-y-lg">
      <div>
        <h1 className="text-headline-lg font-semibold text-on-surface">Filings</h1>
        <p className="text-body-sm text-on-surface-variant mt-1">
          Regulatory disclosures, annual reports, and corporate announcements.
        </p>
      </div>

      <div className="max-w-xl">
        <CompanySearch
          placeholder="Search a company to view its filings…"
          onSelect={setCompany}
        />
      </div>

      {!company ? (
        <Card className="text-center py-2xl px-lg">
          <Icon name="folder_open" className="text-on-surface-variant text-[32px] mb-sm" />
          <p className="text-body-sm text-on-surface-variant">
            Search for a company above to browse its filings.
          </p>
        </Card>
      ) : (
        <>
          {/* Selected company + type filter */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-md">
            <div className="flex items-center gap-sm">
              <Chip tone="neutral">
                {company.ticker_nse ?? company.ticker_bse ?? "—"}
              </Chip>
              <span className="text-card-title font-semibold text-on-surface">
                {company.name}
              </span>
            </div>
            {types.length > 2 && (
              <div className="flex items-center gap-xs flex-wrap">
                {types.map((t) => (
                  <button
                    key={t}
                    onClick={() => setType(t)}
                    className={`h-8 px-sm rounded-md text-caption capitalize border transition-colors ${
                      type === t
                        ? "bg-primary/15 border-primary/40 text-primary"
                        : "bg-bg-1 border-outline-variant text-on-surface-variant hover:text-on-surface"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>

          <Card>
            {loading ? (
              <div className="p-lg space-y-sm">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : error ? (
              <div className="p-lg text-body-sm text-negative">{error}</div>
            ) : shown.length === 0 ? (
              <div className="text-center py-2xl px-lg text-body-sm text-on-surface-variant">
                No filings on record for {company.name} yet.
              </div>
            ) : (
              <ul className="divide-y divide-outline-variant/50">
                {shown.map((f) => (
                  <li key={f.id}>
                    <a
                      href={f.source_url ?? "#"}
                      target={f.source_url ? "_blank" : undefined}
                      rel="noreferrer"
                      className={`flex items-center gap-md px-lg py-md transition-colors ${
                        f.source_url ? "hover:bg-bg-2/50" : "cursor-default"
                      }`}
                    >
                      <div className="w-10 h-10 rounded-md bg-bg-2 flex items-center justify-center shrink-0">
                        <Icon name={filingIcon(f.filing_type)} className="text-[20px] text-primary" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-body-md text-on-surface font-medium truncate">
                          {f.title}
                        </div>
                        <div className="flex items-center gap-sm text-caption text-on-surface-variant mt-0.5">
                          <span>{f.filing_type}</span>
                          {f.filing_date && (
                            <span>
                              • {new Date(f.filing_date).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })}
                            </span>
                          )}
                          {f.period_end && <span>• FY ending {f.period_end}</span>}
                        </div>
                      </div>
                      {f.source_url && (
                        <Icon
                          name="open_in_new"
                          className="text-on-surface-variant text-[18px] shrink-0"
                        />
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
