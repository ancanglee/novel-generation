import { describe, expect, it, vi } from "vitest";
import { createEmfWriter } from "../src/telemetry/emf";

describe("createEmfWriter", () => {
  it("writes EMF shape via logger.info", () => {
    const spy = vi.fn();
    const logger = { info: spy } as unknown as Parameters<typeof createEmfWriter>[0]["logger"];
    const write = createEmfWriter({ logger, env: "dev" });
    write({ name: "SseTtftMs", unit: "Milliseconds", value: 4321, route: "/chapter" });
    expect(spy).toHaveBeenCalledOnce();
    const payload = spy.mock.calls[0][0];
    expect(payload.Env).toBe("dev");
    expect(payload.SseTtftMs).toBe(4321);
    expect(payload.Route).toBe("/chapter");
    expect(payload._aws.CloudWatchMetrics[0].Namespace).toBe("novelgen/frontend");
  });

  it("includes custom attrs as dimensions", () => {
    const spy = vi.fn();
    const logger = { info: spy } as unknown as Parameters<typeof createEmfWriter>[0]["logger"];
    const write = createEmfWriter({ logger, env: "prod" });
    write({
      name: "ClientError",
      unit: "Count",
      value: 1,
      attrs: { errorCode: "NET_ERR" },
    });
    const payload = spy.mock.calls[0][0];
    expect(payload.errorCode).toBe("NET_ERR");
  });
});
