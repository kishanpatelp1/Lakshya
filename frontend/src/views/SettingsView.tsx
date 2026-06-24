import { useState } from "react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { Card, CardHeader } from "../components/ui";
import { Icon } from "../components/Icon";

const EXPERTISE: {
  key: "beginner" | "intermediate" | "advanced";
  title: string;
  desc: string;
}[] = [
  { key: "beginner", title: "Beginner", desc: "Plain-English answers, jargon defined" },
  { key: "intermediate", title: "Intermediate", desc: "Balanced depth with key ratios" },
  { key: "advanced", title: "Advanced", desc: "Dense, quant-first, minimal hand-holding" },
];

export function SettingsView() {
  const { user, setExpertise, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [savingLevel, setSavingLevel] = useState<string | null>(null);

  async function pickLevel(level: "beginner" | "intermediate" | "advanced") {
    if (level === user?.expertise_level) return;
    setSavingLevel(level);
    try {
      await setExpertise(level);
    } finally {
      setSavingLevel(null);
    }
  }

  return (
    <div className="space-y-lg max-w-3xl">
      <h1 className="text-headline-lg font-semibold text-on-surface">Settings</h1>

      {/* Appearance */}
      <Card>
        <CardHeader title="Appearance" icon="palette" />
        <div className="px-lg pb-lg">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-body-md text-on-surface">Theme</div>
              <div className="text-caption text-on-surface-variant">
                Choose how the console looks.
              </div>
            </div>
            <div className="flex items-center gap-1 bg-bg-0 border border-outline-variant rounded-lg p-0.5">
              {(["light", "dark"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  className={`flex items-center gap-sm px-md h-9 rounded-md text-body-sm capitalize transition-colors ${
                    theme === t
                      ? "bg-bg-2 text-on-surface"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  <Icon name={t === "light" ? "light_mode" : "dark_mode"} className="text-[16px]" />
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Research depth */}
      <Card>
        <CardHeader title="Research Depth" icon="tune" />
        <div className="px-lg pb-lg">
          <p className="text-caption text-on-surface-variant mb-md">
            Controls how deep Lakshya goes in its analysis.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-sm">
            {EXPERTISE.map((e) => {
              const active = e.key === user?.expertise_level;
              return (
                <button
                  key={e.key}
                  onClick={() => pickLevel(e.key)}
                  disabled={savingLevel !== null}
                  className={`relative text-left rounded-lg border p-md transition-colors disabled:opacity-60 ${
                    active
                      ? "border-primary bg-primary/10"
                      : "border-outline-variant bg-bg-0 hover:border-outline"
                  }`}
                >
                  {active && (
                    <Icon
                      name="check_circle"
                      className="absolute top-sm right-sm text-primary text-[18px]"
                    />
                  )}
                  <div className="text-body-md font-medium text-on-surface">{e.title}</div>
                  <div className="text-caption text-on-surface-variant mt-1">{e.desc}</div>
                  {savingLevel === e.key && (
                    <div className="text-caption text-primary mt-sm">Saving…</div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Account */}
      <Card>
        <CardHeader title="Account" icon="account_circle" />
        <div className="px-lg pb-lg space-y-md">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-body-md text-on-surface">Signed in as</div>
              <div className="text-caption text-on-surface-variant">{user?.email}</div>
            </div>
          </div>
          <div className="pt-md border-t border-outline-variant/50">
            <button
              onClick={() => logout()}
              className="inline-flex items-center gap-sm h-10 px-md rounded-lg border border-negative/40 text-negative font-medium text-body-sm hover:bg-negative/10 transition"
            >
              <Icon name="logout" className="text-[18px]" />
              Sign out
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}
