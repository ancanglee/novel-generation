# syntax=docker/dockerfile:1.7
# frontend-admin: SPA (Vite build) served by nginx on port 3001.
# Route base is "/admin/" (see apps/frontend-admin/vite.config.ts).
# ALB forwards /admin/* to this service (target port 3001, see infra/cdk/stacks/compute_stack.py).

FROM node:20-bookworm-slim AS builder

ENV PNPM_HOME=/root/.local/share/pnpm \
    PATH=/root/.local/share/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app
# Root + workspace manifests needed for correct pnpm resolution
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/frontend-admin/package.json apps/frontend-admin/
COPY packages/shared-types-ts/package.json packages/shared-types-ts/
COPY packages/api-client-ts/package.json packages/api-client-ts/
COPY packages/ui/package.json packages/ui/
RUN pnpm install --frozen-lockfile --filter @novelgen/frontend-admin...

COPY apps/frontend-admin apps/frontend-admin
COPY packages/shared-types-ts packages/shared-types-ts
COPY packages/api-client-ts packages/api-client-ts
COPY packages/ui packages/ui
RUN pnpm --filter @novelgen/frontend-admin build

# ---- runtime: nginx serving the built SPA -----------------------------------
FROM nginx:1.27-alpine AS runtime

# Minimal nginx config:
#  - listen on 3001 (matches compute_stack.py target port)
#  - serve /admin/ prefix from /usr/share/nginx/html/admin
#  - SPA fallback: unknown paths under /admin/ -> /admin/index.html
#  - /healthz -> 200 OK for ALB health checks
RUN rm /etc/nginx/conf.d/default.conf
COPY <<'EOF' /etc/nginx/conf.d/frontend-admin.conf
server {
    listen 3001;
    server_name _;

    # ALB health check
    location = /healthz {
        access_log off;
        add_header Content-Type text/plain;
        return 200 'ok';
    }

    # Admin SPA, base path /admin/ (see vite.config.ts `base: "/admin/"`)
    location /admin/ {
        alias /usr/share/nginx/html/admin/;
        try_files $uri $uri/ /admin/index.html;
    }

    # Redirect root to /admin/ (convenience when hitting container directly)
    location = / {
        return 302 /admin/;
    }
}
EOF

# Copy built SPA into /usr/share/nginx/html/admin so URLs like /admin/assets/*
# resolve correctly.
COPY --from=builder /app/apps/frontend-admin/dist /usr/share/nginx/html/admin

STOPSIGNAL SIGQUIT
EXPOSE 3001

CMD ["nginx", "-g", "daemon off;"]
