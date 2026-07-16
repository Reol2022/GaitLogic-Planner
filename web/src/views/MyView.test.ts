import { flushPromises, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import MyView from "./MyView.vue";

vi.mock("@/api/dataSync", () => ({ listDataSyncProviders: vi.fn().mockRejectedValue(new Error("disabled")) }));

describe("MyView runner-state entry", () => {
  it("exposes the training-state page without changing bottom navigation", async () => {
    const wrapper = shallowMount(MyView, {
      global: {
        stubs: {
          PageHeader: { template: "<header />" },
          RouterLink: { props: ["to"], template: "<a :data-path='to.path'><slot /></a>" },
          ElIcon: { template: "<i><slot /></i>" },
          ElCollapse: { template: "<div><slot /></div>" },
          ElCollapseItem: { template: "<div><slot /></div>" },
        },
      },
    });
    await flushPromises();
    const runnerLink = wrapper.findAll("a").find((link) => link.text().includes("训练状态"));
    expect(runnerLink).toBeDefined();
    expect(runnerLink?.attributes("data-path")).toBe("/runner-state");
  });
});
