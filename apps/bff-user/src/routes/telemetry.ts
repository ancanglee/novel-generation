import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAuth } from "../session/middleware.js";
import type { TelemetryEvent } from "../telemetry/emf.js";

const telemetrySchema = z.object({
  name: z
    .string()
    .min(1)
    .max(64)
    .regex(/^[A-Za-z][A-Za-z0-9_]*$/),
  unit: z.enum(["Milliseconds", "Count", "None"]),
  value: z.number().finite(),
  route: z.string().max(200).optional(),
  attrs: z.record(z.union([z.string().max(100), z.number(), z.boolean()])).optional(),
});

export async function telemetryRoutes(
  app: FastifyInstance,
  opts: { write(e: TelemetryEvent): void },
): Promise<void> {
  app.post("/telemetry", async (req, reply) => {
    requireAuth(req, reply);
    if (reply.sent) return;
    const parsed = telemetrySchema.safeParse(req.body);
    if (!parsed.success) {
      return reply.code(400).send({
        error: {
          code: "INVALID_TELEMETRY",
          message: "遥测事件格式错误",
          request_id: req.id,
        },
      });
    }
    opts.write(parsed.data);
    return reply.code(204).send();
  });
}
