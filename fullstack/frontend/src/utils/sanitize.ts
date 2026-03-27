function sanitizeString(value: string, keyPath: string): string {
  const normalized = value.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "");
  if (keyPath.toLowerCase().includes("password")) {
    return normalized;
  }
  return normalized.trim();
}

export function sanitizePayload(value: unknown, keyPath = ""): unknown {
  if (typeof value === "string") {
    return sanitizeString(value, keyPath);
  }

  if (Array.isArray(value)) {
    return value.map((item, index) => sanitizePayload(item, `${keyPath}[${index}]`));
  }

  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
      const nextPath = keyPath ? `${keyPath}.${key}` : key;
      output[key] = sanitizePayload(nested, nextPath);
    }
    return output;
  }

  return value;
}
