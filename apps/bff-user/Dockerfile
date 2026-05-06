FROM node:20-bookworm-slim AS builder

ENV PNPM_HOME=/root/.local/share/pnpm \
    PATH=/root/.local/share/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/bff-user/package.json apps/bff-user/
COPY packages/shared-types-ts/package.json packages/shared-types-ts/
RUN pnpm install --frozen-lockfile --filter @novelgen/bff-user...

COPY apps/bff-user apps/bff-user
COPY packages/shared-types-ts packages/shared-types-ts
RUN pnpm --filter @novelgen/bff-user build

FROM node:20-bookworm-slim AS runtime
ENV NODE_ENV=production \
    PNPM_HOME=/root/.local/share/pnpm \
    PATH=/root/.local/share/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app
COPY --from=builder /app/pnpm-lock.yaml /app/pnpm-workspace.yaml /app/package.json ./
COPY --from=builder /app/apps/bff-user/package.json apps/bff-user/
COPY --from=builder /app/packages/shared-types-ts packages/shared-types-ts
RUN pnpm install --frozen-lockfile --filter @novelgen/bff-user --prod
COPY --from=builder /app/apps/bff-user/dist apps/bff-user/dist

USER node
STOPSIGNAL SIGTERM
EXPOSE 3000

CMD ["node", "apps/bff-user/dist/server.js"]
