import { apiRequest, ApiResult } from "@/lib/api";
import { UserCreateRequest, UserListData, UserOut, UserUpdateRequest } from "@/lib/types";

export const userService = {
  listUsers(): Promise<ApiResult<UserListData>> {
    return apiRequest<UserListData>("/users");
  },

  createUser(payload: UserCreateRequest): Promise<ApiResult<UserOut>> {
    return apiRequest<UserOut>("/users", {
      method: "POST",
      body: payload,
    });
  },

  updateUser(userId: number, payload: UserUpdateRequest): Promise<ApiResult<UserOut>> {
    return apiRequest<UserOut>(`/users/${userId}`, {
      method: "PATCH",
      body: payload,
    });
  },
};

