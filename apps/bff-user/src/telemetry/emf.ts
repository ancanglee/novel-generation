import type { FastifyBaseLogger } from "fastify";

export interface TelemetryEvent {
  name: string; // metric name (e.g. SseTtftMs)
  unit: "Milliseconds" | "Count" | "None";
  value: number;
  route?: string;
  attrs?: Record<string, string | number | boolean>;
}

export interface EmfWriterDeps {
  logger: FastifyBaseLogger;
  env: string;
  namespace?: string;
}

export function createEmfWriter({ logger, env, namespace = "novelgen/frontend" }: EmfWriterDeps) {
  return function write(metric: TelemetryEvent): void {
    const dims = ["Env", ...(metric.route ? ["Route"] : []), ...Object.keys(metric.attrs ?? {})];
    const payload: Record<string, unknown> = {
      _aws: {
        Timestamp: Date.now(),
        CloudWatchMetrics: [
          {
            Namespace: namespace,
            Dimensions: [dims],
            Metrics: [{ Name: metric.name, Unit: metric.unit }],
          },
        ],
      },
      Env: env,
      [metric.name]: metric.value,
      ...(metric.route ? { Route: metric.route } : {}),
      ...(metric.attrs ?? {}),
    };
    logger.info(payload);
  };
}
