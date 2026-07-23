import { describe, expect, it } from "vitest";
import router from "./index";

describe("coach route", () => {
  it("registers one protected route without identity or provider parameters", () => {
    const route = router.getRoutes().find((item) => item.path === "/coach");
    expect(route).toBeDefined();
    expect(route?.name).toBe("CoachAgent");
    expect(route?.meta.public).not.toBe(true);
    expect(route?.path).not.toContain(":user_id");
    expect(route?.path).not.toContain("provider");
  });
});
