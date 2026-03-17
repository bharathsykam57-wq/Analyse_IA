export interface User {
  id: string;
  email: string;
  full_name: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export interface LoginResponse extends AuthTokens {}

export interface RequestError {
  detail: string;
}
