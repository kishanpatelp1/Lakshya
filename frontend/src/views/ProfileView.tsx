import { useState } from "react";
import { useAuth } from "../lib/auth";
import { Card, CardHeader } from "../components/ui";
import { Icon } from "../components/Icon";

const EXPERTISE_LABEL: Record<string, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export function ProfileView() {
  const { user, saveProfile } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [phone, setPhone] = useState(user?.phone_number ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  const initials = (user.full_name || user.email).slice(0, 2).toUpperCase();
  const dirty = name.trim() !== (user.full_name ?? "") || phone.trim() !== (user.phone_number ?? "");

  async function onSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await saveProfile({ full_name: name.trim() || undefined, phone_number: phone.trim() || undefined });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("Could not save changes. Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-lg max-w-3xl">
      <h1 className="text-headline-lg font-semibold text-on-surface">Profile</h1>

      {/* Identity header */}
      <Card className="p-lg">
        <div className="flex items-center gap-lg">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary to-primary-fixed-dim flex items-center justify-center text-on-primary text-headline-lg font-semibold shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <div className="text-card-title font-semibold text-on-surface truncate">
              {user.full_name || "Unnamed analyst"}
            </div>
            <div className="text-body-sm text-on-surface-variant truncate">{user.email}</div>
            <div className="text-caption text-on-surface-variant mt-1">
              Member since{" "}
              {new Date(user.created_at).toLocaleDateString("en-IN", {
                month: "long",
                year: "numeric",
              })}{" "}
              · {EXPERTISE_LABEL[user.expertise_level] ?? user.expertise_level} tier
            </div>
          </div>
        </div>
      </Card>

      {/* Editable details */}
      <Card>
        <CardHeader title="Account Details" icon="badge" />
        <div className="px-lg pb-lg space-y-lg">
          <Field label="Full name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="w-full bg-bg-0 border border-outline-variant rounded-lg px-md h-11 text-body-md text-on-surface focus:outline-none focus:border-primary/60 placeholder:text-on-surface-variant"
            />
          </Field>

          <Field label="Email">
            <div className="flex items-center bg-bg-0/60 border border-outline-variant rounded-lg px-md h-11 text-body-md text-on-surface-variant">
              {user.email}
              <span className="ml-auto text-caption">Read-only</span>
            </div>
          </Field>

          <Field label="Phone number">
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 …"
              className="w-full bg-bg-0 border border-outline-variant rounded-lg px-md h-11 text-body-md text-on-surface focus:outline-none focus:border-primary/60 placeholder:text-on-surface-variant"
            />
          </Field>

          {error && (
            <p className="text-body-sm text-negative flex items-center gap-xs">
              <Icon name="error" className="text-[16px]" /> {error}
            </p>
          )}

          <div className="flex items-center gap-md">
            <button
              onClick={onSave}
              disabled={!dirty || saving}
              className="h-11 px-lg rounded-lg bg-primary text-on-primary font-medium text-body-sm hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
            {saved && (
              <span className="text-body-sm text-positive flex items-center gap-xs">
                <Icon name="check_circle" className="text-[18px]" /> Saved
              </span>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-label-caps font-label-caps text-on-surface-variant block mb-xs">
        {label}
      </label>
      {children}
    </div>
  );
}
