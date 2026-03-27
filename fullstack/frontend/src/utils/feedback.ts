import axios from "axios";

import { useUiStore } from "@/stores/ui";

function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object" && "msg" in item) {
          const record = item as { msg?: unknown; loc?: unknown };
          const msg = String(record.msg ?? "").trim();
          const loc = Array.isArray(record.loc)
            ? record.loc
                .map((part) => String(part))
                .filter((part) => part !== "body")
                .join(".")
            : "";
          if (loc && msg) {
            return `${loc}: ${msg}`;
          }
          return msg;
        }
        return "";
      })
      .filter((value) => value.trim().length > 0);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (detail && typeof detail === "object") {
    if ("msg" in detail) {
      return String((detail as { msg?: unknown }).msg ?? "");
    }
    if ("message" in detail) {
      return String((detail as { message?: unknown }).message ?? "");
    }
  }

  return null;
}

export function getErrorMessage(error: unknown, fallback = "Request failed."): string {
  if (axios.isAxiosError(error)) {
    const parsed = formatDetail(error.response?.data?.detail);
    return parsed ?? error.message ?? fallback;
  }
  return fallback;
}

export function notifyError(error: unknown, fallback = "Request failed."): string {
  const message = getErrorMessage(error, fallback);
  const ui = useUiStore();
  ui.error("Action Failed", message);
  return message;
}
