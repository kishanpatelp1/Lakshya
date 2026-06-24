// The authenticated user's id and expertise are written here by AuthProvider
// after login / session restore, and cleared on logout. Views read them
// synchronously so every request is scoped to the signed-in user.
const USER_KEY = "lakshya-user-id";
const EXPERTISE_KEY = "lakshya-expertise";

export function setAuthUser(id: string, expertise?: string): void {
  localStorage.setItem(USER_KEY, id);
  if (expertise) localStorage.setItem(EXPERTISE_KEY, expertise);
}

export function clearAuthUser(): void {
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(EXPERTISE_KEY);
}

export function getUserId(): string {
  return localStorage.getItem(USER_KEY) ?? "";
}

export function getExpertise(): "beginner" | "intermediate" | "advanced" {
  const v = localStorage.getItem(EXPERTISE_KEY);
  if (v === "beginner" || v === "intermediate" || v === "advanced") return v;
  return "intermediate";
}
