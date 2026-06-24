import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  demoLogin,
  fetchMe,
  loginUser,
  logoutUser,
  registerUser,
  updateProfile,
  verifyOtp,
  type AuthResponse,
  type AuthUser,
} from "../shared/api/auth";
import { clearAuthUser, setAuthUser } from "./user";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  /** True right after a brand-new signup verifies — App shows onboarding. */
  needsOnboarding: boolean;
  login: (email: string, password: string) => Promise<AuthResponse>;
  register: (full_name: string, email: string, password: string) => Promise<AuthResponse>;
  verify: (email: string, otp: string, purpose: "signup" | "login") => Promise<AuthResponse>;
  demo: () => Promise<AuthResponse>;
  setExpertise: (level: "beginner" | "intermediate" | "advanced") => Promise<void>;
  saveProfile: (input: {
    full_name?: string;
    phone_number?: string;
    expertise_level?: "beginner" | "intermediate" | "advanced";
  }) => Promise<void>;
  finishOnboarding: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  const apply = useCallback((resp: AuthResponse) => {
    setUser(resp.user);
    setAuthUser(resp.user.id, resp.user.expertise_level);
    return resp;
  }, []);

  // Restore session on boot.
  useEffect(() => {
    let cancelled = false;
    // Watchdog: never hang on the loading spinner. If /auth/me doesn't answer
    // (e.g. the API is momentarily restarting), fall through to the login screen.
    const watchdog = setTimeout(() => {
      if (!cancelled) setLoading(false);
    }, 6000);
    fetchMe()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setAuthUser(u.id, u.expertise_level);
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null);
          clearAuthUser();
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
        clearTimeout(watchdog);
      });
    return () => {
      cancelled = true;
      clearTimeout(watchdog);
    };
  }, []);

  const login = useCallback(
    (email: string, password: string) => loginUser({ email, password }).then(apply),
    [apply]
  );

  const register = useCallback(
    (full_name: string, email: string, password: string) =>
      registerUser({ full_name, email, password }),
    []
  );

  const verify = useCallback(
    (email: string, otp: string, purpose: "signup" | "login") =>
      verifyOtp({ email, otp, purpose }).then((resp) => {
        if (resp.is_new_user) setNeedsOnboarding(true);
        return apply(resp);
      }),
    [apply]
  );

  const finishOnboarding = useCallback(() => setNeedsOnboarding(false), []);

  const demo = useCallback(() => demoLogin().then(apply), [apply]);

  const saveProfile = useCallback(
    async (input: {
      full_name?: string;
      phone_number?: string;
      expertise_level?: "beginner" | "intermediate" | "advanced";
    }) => {
      const updated = await updateProfile(input);
      setUser(updated);
      setAuthUser(updated.id, updated.expertise_level);
    },
    []
  );

  const setExpertise = useCallback(
    (level: "beginner" | "intermediate" | "advanced") =>
      saveProfile({ expertise_level: level }),
    [saveProfile]
  );

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch {
      /* clear locally regardless */
    }
    setUser(null);
    setNeedsOnboarding(false);
    clearAuthUser();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        needsOnboarding,
        login,
        register,
        verify,
        demo,
        setExpertise,
        saveProfile,
        finishOnboarding,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
