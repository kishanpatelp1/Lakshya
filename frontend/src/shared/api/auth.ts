import { BACKEND_URL } from "./core";

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string | null;
  phone_number?: string | null;
  expertise_level: "beginner" | "intermediate" | "advanced";
  profile_pic_url?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  message: string;
  user: AuthUser;
  is_new_user: boolean;
}

export interface OtpSentResponse {
  message: string;
  expires_in_seconds: number;
}

export type AuthPurpose = "signup" | "login";

/** HTTP error that carries the backend's `detail` message. */
export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function csrfToken(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : null;
}

async function req<T>(
  path: string,
  method: "GET" | "POST" | "PUT",
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const csrf = csrfToken();
  if (csrf) headers["X-CSRF-Token"] = csrf;

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method,
      credentials: "include",
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new AuthError("Could not reach the server. Check your connection.", 0);
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = String(data.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new AuthError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function registerUser(input: {
  full_name: string;
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return req<AuthResponse>("/auth/register", "POST", input);
}

export function loginUser(input: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return req<AuthResponse>("/auth/login", "POST", input);
}

export function demoLogin(): Promise<AuthResponse> {
  return req<AuthResponse>("/auth/demo", "POST", {});
}

export function sendOtp(input: {
  email: string;
  purpose: AuthPurpose;
}): Promise<OtpSentResponse> {
  return req<OtpSentResponse>("/auth/send-otp", "POST", input);
}

export function verifyOtp(input: {
  email: string;
  otp: string;
  purpose: AuthPurpose;
  full_name?: string;
}): Promise<AuthResponse> {
  return req<AuthResponse>("/auth/verify-otp", "POST", input);
}

export function fetchMe(): Promise<AuthUser> {
  return req<AuthUser>("/auth/me", "GET");
}

export function logoutUser(): Promise<void> {
  return req<void>("/auth/logout", "POST", {});
}

export function updateProfile(input: {
  full_name?: string;
  phone_number?: string;
  expertise_level?: "beginner" | "intermediate" | "advanced";
}): Promise<AuthUser> {
  return req<AuthUser>("/auth/profile", "PUT", input);
}
