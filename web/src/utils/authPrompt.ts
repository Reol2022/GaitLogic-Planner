export const AUTH_REQUIRED_EVENT = "gaitlogic:auth-required";

export interface AuthRequiredDetail {
  redirect?: string;
}

export function requestAuth(redirect = window.location.pathname + window.location.search) {
  window.dispatchEvent(new CustomEvent<AuthRequiredDetail>(AUTH_REQUIRED_EVENT, { detail: { redirect } }));
}
