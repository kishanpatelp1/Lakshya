import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../lib/auth";
import { sendOtp, AuthError } from "../shared/api/auth";
import { Icon } from "../components/Icon";

type Step = "login" | "signup" | "otp";

export function AuthView() {
  const auth = useAuth();
  const [step, setStep] = useState<Step>("login");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function fail(e: unknown) {
    setError(e instanceof AuthError ? e.message : "Something went wrong. Try again.");
  }

  return (
    <div className="min-h-screen bg-bg-0 text-on-surface flex">
      {/* Brand panel */}
      <BrandPanel />

      {/* Form panel */}
      <div className="flex-1 flex flex-col items-center justify-center px-margin-mobile md:px-margin-desktop py-xl">
        <div className="w-full max-w-[400px]">
          <div className="md:hidden mb-xl flex justify-center">
            <Logo />
          </div>

          {step === "login" && (
            <LoginForm
              busy={busy}
              error={error}
              onSubmit={async (em, pw) => {
                setBusy(true);
                setError(null);
                try {
                  await auth.login(em, pw);
                } catch (e) {
                  fail(e);
                } finally {
                  setBusy(false);
                }
              }}
              onDemo={async () => {
                setBusy(true);
                setError(null);
                try {
                  await auth.demo();
                } catch (e) {
                  fail(e);
                } finally {
                  setBusy(false);
                }
              }}
              onSwitch={() => {
                setError(null);
                setStep("signup");
              }}
            />
          )}

          {step === "signup" && (
            <SignupForm
              busy={busy}
              error={error}
              onSubmit={async (name, em, pw) => {
                setBusy(true);
                setError(null);
                try {
                  await auth.register(name, em, pw);
                  setEmail(em);
                  setStep("otp");
                } catch (e) {
                  fail(e);
                } finally {
                  setBusy(false);
                }
              }}
              onSwitch={() => {
                setError(null);
                setStep("login");
              }}
            />
          )}

          {step === "otp" && (
            <OtpForm
              email={email}
              busy={busy}
              error={error}
              onVerify={async (code) => {
                setBusy(true);
                setError(null);
                try {
                  // On success `user` is set → App swaps to onboarding/shell.
                  await auth.verify(email, code, "signup");
                } catch (e) {
                  fail(e);
                } finally {
                  setBusy(false);
                }
              }}
              onResend={() => sendOtp({ email, purpose: "signup" })}
              onChangeEmail={() => {
                setError(null);
                setStep("signup");
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Brand panel ──────────────────────────────────────────────────────────────

function Logo() {
  return (
    <div className="flex items-center gap-sm">
      <div className="w-9 h-9 rounded-md bg-gradient-to-br from-primary to-primary-fixed-dim flex items-center justify-center">
        <Icon name="terminal" className="text-on-primary text-[20px]" />
      </div>
      <div className="leading-tight">
        <div className="text-card-title font-semibold tracking-tight">Lakshya</div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-on-surface-variant">
          Research Console
        </div>
      </div>
    </div>
  );
}

function BrandPanel() {
  return (
    <div className="hidden md:flex relative w-[52%] lg:w-[55%] flex-col justify-between p-margin-desktop bg-bg-1 border-r border-outline-variant overflow-hidden">
      <div className="relative z-10">
        <Logo />
      </div>

      {/* faint price-line watermark */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.06] pointer-events-none"
        viewBox="0 0 600 600"
        preserveAspectRatio="none"
      >
        <polyline
          points="0,470 120,430 210,460 300,300 380,360 470,180 600,240"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-on-surface"
        />
      </svg>

      <div className="relative z-10 max-w-md">
        <h1 className="text-[2.25rem] leading-tight font-semibold tracking-tight">
          Institutional-grade{" "}
          <span className="text-primary">equity intelligence</span>
        </h1>
        <p className="text-body-md text-on-surface-variant mt-md">
          Access real-time alternative data, domino flow-correlation graphs, and
          automated analyst workflows built for institutional desks.
        </p>
        <div className="flex items-center gap-lg mt-xl text-label-caps font-label-caps text-on-surface-variant">
          <span>SEC COMPLIANT</span>
          <span>ISO 27001</span>
          <span>256-BIT AES</span>
        </div>
      </div>
    </div>
  );
}

// ── Shared field primitives ──────────────────────────────────────────────────

function Field({
  label,
  right,
  children,
}: {
  label: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-xs">
        <label className="text-label-caps font-label-caps text-on-surface-variant">
          {label}
        </label>
        {right}
      </div>
      {children}
    </div>
  );
}

function InputShell({
  icon,
  children,
}: {
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center bg-bg-1 border border-outline-variant rounded-lg px-md h-12 focus-within:border-primary/60 transition-colors">
      <Icon name={icon} className="text-on-surface-variant text-[18px] mr-sm shrink-0" />
      {children}
    </div>
  );
}

const inputCls =
  "bg-transparent w-full text-body-md text-on-surface focus:outline-none placeholder:text-on-surface-variant";

function PrimaryBtn({
  children,
  disabled,
  onClick,
  type = "button",
}: {
  children: React.ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="w-full h-12 rounded-lg bg-primary text-on-primary font-semibold text-body-md flex items-center justify-center gap-sm hover:brightness-95 active:brightness-90 disabled:opacity-50 disabled:cursor-not-allowed transition"
    >
      {children}
    </button>
  );
}

function ErrorLine({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return (
    <div className="flex items-start gap-xs text-body-sm text-negative">
      <Icon name="error" className="text-[16px] mt-0.5 shrink-0" />
      <span>{msg}</span>
    </div>
  );
}

// ── Login ────────────────────────────────────────────────────────────────────

function LoginForm({
  busy,
  error,
  onSubmit,
  onDemo,
  onSwitch,
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (email: string, password: string) => void;
  onDemo: () => void;
  onSwitch: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const canSubmit = email.trim() && password && !busy;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit(email.trim().toLowerCase(), password);
      }}
      className="space-y-lg"
    >
      <div>
        <h2 className="text-headline-lg font-semibold">Welcome back</h2>
        <p className="text-body-sm text-on-surface-variant mt-1">
          Sign in to your research console
        </p>
      </div>

      <Field label="Institutional Email">
        <InputShell icon="mail">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@fund.com"
            autoComplete="email"
            className={inputCls}
          />
        </InputShell>
      </Field>

      <Field label="Password">
        <InputShell icon="lock">
          <input
            type={show ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            className={inputCls}
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <Icon name={show ? "visibility_off" : "visibility"} className="text-[18px]" />
          </button>
        </InputShell>
      </Field>

      <ErrorLine msg={error} />

      <PrimaryBtn type="submit" disabled={!canSubmit}>
        {busy ? "Signing in…" : "Sign in"}
      </PrimaryBtn>

      <div className="flex items-center gap-md text-label-caps font-label-caps text-on-surface-variant">
        <div className="flex-1 h-px bg-outline-variant" />
        OR
        <div className="flex-1 h-px bg-outline-variant" />
      </div>

      <button
        type="button"
        onClick={onDemo}
        disabled={busy}
        className="w-full h-12 rounded-lg border border-outline-variant text-on-surface font-medium text-body-md flex items-center justify-center gap-sm hover:bg-bg-1 disabled:opacity-50 transition"
      >
        <Icon name="database" className="text-[18px]" />
        Continue as demo
      </button>

      <p className="text-center text-body-sm text-on-surface-variant">
        New to Lakshya?{" "}
        <button type="button" onClick={onSwitch} className="text-primary font-medium hover:underline">
          Create an account
        </button>
      </p>
    </form>
  );
}

// ── Signup ───────────────────────────────────────────────────────────────────

function passwordStrength(pw: string): { score: number; label: string } {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const label = ["Too weak", "Weak", "Fair", "Good", "Strong"][score];
  return { score, label };
}

function SignupForm({
  busy,
  error,
  onSubmit,
  onSwitch,
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (name: string, email: string, password: string) => void;
  onSwitch: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [agree, setAgree] = useState(false);
  const [localErr, setLocalErr] = useState<string | null>(null);

  const strength = useMemo(() => passwordStrength(password), [password]);
  const strengthColors = ["bg-negative", "bg-negative", "bg-warning", "bg-primary", "bg-positive"];
  const canSubmit =
    name.trim() && email.trim() && password.length >= 8 && confirm && agree && !busy;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setLocalErr(null);
        if (password !== confirm) {
          setLocalErr("Passwords don't match.");
          return;
        }
        if (canSubmit) onSubmit(name.trim(), email.trim().toLowerCase(), password);
      }}
      className="space-y-md"
    >
      <div>
        <h2 className="text-headline-lg font-semibold">Create your account</h2>
        <p className="text-body-sm text-on-surface-variant mt-1">
          Start your research workspace in seconds
        </p>
      </div>

      <Field label="Full Name">
        <InputShell icon="person">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ada Lovelace"
            autoComplete="name"
            className={inputCls}
          />
        </InputShell>
      </Field>

      <Field label="Work Email">
        <InputShell icon="mail">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@fund.com"
            autoComplete="email"
            className={inputCls}
          />
        </InputShell>
      </Field>

      <Field label="Password">
        <InputShell icon="lock">
          <input
            type={show ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            className={inputCls}
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <Icon name={show ? "visibility_off" : "visibility"} className="text-[18px]" />
          </button>
        </InputShell>
        <div className="mt-xs">
          <div className="h-1 rounded-full bg-outline-variant overflow-hidden">
            <div
              className={`h-full transition-all ${strengthColors[strength.score]}`}
              style={{ width: `${(strength.score / 4) * 100}%` }}
            />
          </div>
          <div className="text-caption text-on-surface-variant mt-1">
            {password ? strength.label : "At least 8 characters"}
          </div>
        </div>
      </Field>

      <Field label="Confirm Password">
        <InputShell icon="lock">
          <input
            type={show ? "text" : "password"}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            className={inputCls}
          />
        </InputShell>
      </Field>

      <label className="flex items-start gap-sm text-body-sm text-on-surface-variant cursor-pointer">
        <input
          type="checkbox"
          checked={agree}
          onChange={(e) => setAgree(e.target.checked)}
          className="mt-0.5 accent-primary w-4 h-4"
        />
        <span>
          I agree to the <span className="text-primary">Terms</span> &{" "}
          <span className="text-primary">Privacy Policy</span>
        </span>
      </label>

      <ErrorLine msg={localErr ?? error} />

      <PrimaryBtn type="submit" disabled={!canSubmit}>
        {busy ? "Creating account…" : "Create account"}
      </PrimaryBtn>

      <p className="text-center text-body-sm text-on-surface-variant">
        Already have an account?{" "}
        <button type="button" onClick={onSwitch} className="text-primary font-medium hover:underline">
          Sign in
        </button>
      </p>
    </form>
  );
}

// ── OTP ──────────────────────────────────────────────────────────────────────

function OtpForm({
  email,
  busy,
  error,
  onVerify,
  onResend,
  onChangeEmail,
}: {
  email: string;
  busy: boolean;
  error: string | null;
  onVerify: (code: string) => void;
  onResend: () => Promise<unknown>;
  onChangeEmail: () => void;
}) {
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const [cooldown, setCooldown] = useState(58);
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const code = digits.join("");
  const complete = code.length === 6;

  function setDigit(i: number, v: string) {
    const clean = v.replace(/\D/g, "");
    if (!clean) {
      setDigits((d) => d.map((x, idx) => (idx === i ? "" : x)));
      return;
    }
    setDigits((d) => {
      const next = [...d];
      // support paste of full code
      if (clean.length > 1) {
        for (let k = 0; k < clean.length && i + k < 6; k++) next[i + k] = clean[k];
        const last = Math.min(i + clean.length, 5);
        refs.current[last]?.focus();
        return next;
      }
      next[i] = clean[0];
      if (i < 5) refs.current[i + 1]?.focus();
      return next;
    });
  }

  function onKey(i: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus();
  }

  const mm = String(Math.floor(cooldown / 60)).padStart(1, "0");
  const ss = String(cooldown % 60).padStart(2, "0");

  return (
    <div className="space-y-lg">
      <div>
        <h2 className="text-headline-lg font-semibold">Verify your email</h2>
        <p className="text-body-sm text-on-surface-variant mt-1">
          We've sent a 6-digit code to{" "}
          <span className="text-on-surface font-medium">{email}</span>.{" "}
          <button onClick={onChangeEmail} className="text-primary hover:underline">
            Change
          </button>
        </p>
      </div>

      <div className="flex gap-sm justify-between">
        {digits.map((d, i) => (
          <input
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            value={d}
            onChange={(e) => setDigit(i, e.target.value)}
            onKeyDown={(e) => onKey(i, e)}
            inputMode="numeric"
            maxLength={i === 0 ? 6 : 1}
            className="w-12 h-14 sm:w-14 text-center text-headline-lg font-semibold bg-bg-1 border border-outline-variant rounded-lg text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/50 transition"
          />
        ))}
      </div>

      <ErrorLine msg={error} />

      <PrimaryBtn disabled={!complete || busy} onClick={() => onVerify(code)}>
        {busy ? "Verifying…" : "Verify Identity"}
        {!busy && <Icon name="verified_user" className="text-[18px]" />}
      </PrimaryBtn>

      <p className="text-center text-body-sm text-on-surface-variant">
        Didn't receive the code?{" "}
        {cooldown > 0 ? (
          <span className="text-on-surface-variant">
            Resend in {mm}:{ss}
          </span>
        ) : (
          <button
            onClick={async () => {
              await onResend().catch(() => {});
              setCooldown(58);
            }}
            className="text-primary font-medium hover:underline"
          >
            Resend code
          </button>
        )}
      </p>

      <div className="pt-md border-t border-outline-variant flex items-center gap-xs justify-center text-caption text-on-surface-variant">
        <Icon name="lock" className="text-[14px]" />
        Encrypted session verified by Lakshya Compliance Engine
      </div>
    </div>
  );
}

// ── Onboarding ───────────────────────────────────────────────────────────────

const LEVELS: {
  key: "beginner" | "intermediate" | "advanced";
  icon: string;
  title: string;
  desc: string;
}[] = [
  { key: "beginner", icon: "school", title: "Beginner", desc: "Plain-English answers, jargon defined" },
  { key: "intermediate", icon: "insights", title: "Intermediate", desc: "Balanced depth with key ratios" },
  { key: "advanced", icon: "monitoring", title: "Advanced", desc: "Dense, quant-first, minimal hand-holding" },
];

export function OnboardingView() {
  const { user, setExpertise, finishOnboarding } = useAuth();
  const [level, setLevel] = useState<"beginner" | "intermediate" | "advanced">("intermediate");
  const [busy, setBusy] = useState(false);
  const firstName = user?.full_name?.split(" ")[0];

  async function done(apply: boolean) {
    setBusy(true);
    if (apply) {
      try {
        await setExpertise(level);
      } catch {
        /* non-blocking */
      }
    }
    finishOnboarding();
  }

  return (
    <div className="min-h-screen bg-bg-0 text-on-surface flex flex-col items-center justify-center px-margin-mobile py-xl">
      <div className="mb-lg">
        <Logo />
      </div>
      <div className="w-full max-w-[560px] bg-bg-1 border border-outline-variant rounded-xl p-lg md:p-xl space-y-lg">
        <div className="text-center">
          <h2 className="text-headline-lg font-semibold">
            How deep should Lakshya go{firstName ? `, ${firstName}` : ""}?
          </h2>
          <p className="text-body-sm text-on-surface-variant mt-1">
            You can change this anytime in Settings
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-sm">
          {LEVELS.map((l) => {
            const active = l.key === level;
            return (
              <button
                key={l.key}
                onClick={() => setLevel(l.key)}
                className={`relative text-left rounded-lg border p-md transition-colors ${
                  active
                    ? "border-primary bg-primary/10"
                    : "border-outline-variant bg-bg-2 hover:border-outline"
                }`}
              >
                {active && (
                  <Icon
                    name="check_circle"
                    className="absolute top-sm right-sm text-primary text-[18px]"
                  />
                )}
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center mb-sm ${
                    active ? "bg-primary/20 text-primary" : "bg-bg-0 text-on-surface-variant"
                  }`}
                >
                  <Icon name={l.icon} className="text-[20px]" />
                </div>
                <div className="text-card-title font-semibold">{l.title}</div>
                <div className="text-body-sm text-on-surface-variant mt-1">{l.desc}</div>
              </button>
            );
          })}
        </div>

        <PrimaryBtn disabled={busy} onClick={() => done(true)}>
          Enter Lakshya
          <Icon name="arrow_forward" className="text-[18px]" />
        </PrimaryBtn>

        <button
          onClick={() => done(false)}
          className="w-full text-center text-body-sm text-on-surface-variant hover:text-on-surface"
        >
          Skip for now
        </button>
      </div>
    </div>
  );
}
