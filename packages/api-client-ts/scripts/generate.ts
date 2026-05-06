// Generate TS types from ApiService /openapi.json.
// Usage: OPENAPI_URL=http://localhost:8000/openapi.json pnpm -F @novelgen/api-client generate

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const url = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json";
const outputPath = resolve(import.meta.dirname ?? ".", "../src/generated/schema.ts");

const ast = await openapiTS(new URL(url));
writeFileSync(outputPath, astToString(ast), "utf8");
console.log(`[api-client] generated ${outputPath} from ${url}`);
