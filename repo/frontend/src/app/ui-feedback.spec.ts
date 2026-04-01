import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";

import { useUiStore } from "@/stores/ui";

describe("ui feedback store", () => {
  it("tracks global loading state", () => {
    setActivePinia(createPinia());
    const ui = useUiStore();

    expect(ui.isLoading).toBe(false);
    ui.beginRequest();
    expect(ui.isLoading).toBe(true);
    ui.endRequest();
    expect(ui.isLoading).toBe(false);
  });

  it("pushes and removes toast messages", () => {
    setActivePinia(createPinia());
    const ui = useUiStore();

    ui.success("Created", "Campaign created successfully.");
    expect(ui.toasts.length).toBe(1);
    const toastId = ui.toasts[0].id;

    ui.removeToast(toastId);
    expect(ui.toasts.length).toBe(0);
  });
});
