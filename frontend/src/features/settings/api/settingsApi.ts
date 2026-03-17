import { apiClient } from "@/shared/api/client";
import { UserProfile, ProfileUpdateRequest, ChangePasswordRequest } from "@/shared/types/settings";

/**
 * Fetch current user profile
 * @returns UserProfile with all user details
 */
export const fetchUserProfile = async (): Promise<UserProfile> => {
  const response = await apiClient.get("auth/me");
  return response.data;
};

/**
 * Update user profile
 * @param data - Profile update data (full_name, preferred_language)
 * @returns Updated UserProfile
 */
export const updateProfile = async (data: ProfileUpdateRequest): Promise<UserProfile> => {
  const response = await apiClient.post("auth/update-profile", data);
  return response.data;
};

/**
 * Change user password
 * @param data - Current and new password
 * @returns Success status
 */
export const changePassword = async (data: ChangePasswordRequest): Promise<{ success: boolean }> => {
  const response = await apiClient.post("auth/change-password", {
    current_password: data.current_password,
    new_password: data.new_password,
  });
  return response.data;
};

/**
 * Update user preferences (notifications, consents, etc.)
 * @param preferences - Preference settings
 * @returns Updated preferences
 */
export const updatePreferences = async (preferences: any): Promise<any> => {
  const response = await apiClient.post("auth/preferences", preferences);
  return response.data;
};
