import {
  type ProfileConfigResponse,
  type UserProfile,
  type UserProfileUpdate,
} from "../types/api";
import { AI_BACKEND_URL, aiGet, aiPost, ApiError } from "./core";

const NGROK_SKIP_HEADER = { "ngrok-skip-browser-warning": "true" };

export async function fetchProfileConfig(): Promise<ProfileConfigResponse> {
  return aiGet<ProfileConfigResponse>("/users/profile/config");
}

export async function fetchUserProfile(userId: string): Promise<UserProfile> {
  return aiGet<UserProfile>(`/users/${userId}`);
}

export async function updateUserProfile(
  userId: string,
  data: UserProfileUpdate
): Promise<UserProfile> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${AI_BACKEND_URL}/users/${userId}`, {
      method: "PUT",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", Accept: "application/json", ...NGROK_SKIP_HEADER },
      body: JSON.stringify(data),
    });
    if (!response.ok)
      throw new ApiError(`Profile update failed with status ${response.status}`, response.status);
    return (await response.json()) as UserProfile;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Could not update profile");
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function uploadProfilePic(
  userId: string,
  file: File
): Promise<{ profile_pic_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${AI_BACKEND_URL}/users/${userId}/profile-pic`, {
    method: "POST",
    headers: NGROK_SKIP_HEADER,
    body: formData,
  });
  if (!response.ok)
    throw new ApiError(`Profile pic upload failed with status ${response.status}`, response.status);
  return response.json();
}

export async function submitKyc(
  userId: string,
  panCardNumber: string,
  aadhaarNumber?: string
): Promise<{ kyc_status: string; kyc_submitted_at: string; message: string }> {
  return aiPost(`/users/${userId}/kyc/submit`, {
    pan_card_number: panCardNumber,
    aadhaar_number: aadhaarNumber,
  });
}


export async function verifyKyc(
  userId: string
): Promise<{ kyc_status: string; message: string }> {
  return aiPost(`/users/${userId}/kyc/verify`, {});
}
