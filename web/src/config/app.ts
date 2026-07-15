export const APP_NAME = "GaitLogic";

export const APP_VERSION =
  import.meta.env.VITE_APP_VERSION || (typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0");

export const APP_STAGE = import.meta.env.VITE_APP_STAGE?.trim() || "";

export const APP_VERSION_LABEL = `v${APP_VERSION}${APP_STAGE ? ` · ${APP_STAGE}` : ""}`;
