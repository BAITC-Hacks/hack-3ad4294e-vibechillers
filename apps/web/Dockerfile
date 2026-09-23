# syntax=docker/dockerfile:1
# alem web UI (Next.js 16, output: "standalone").
#
# Build context MUST be the repo root so the root .dockerignore applies:
#   docker build -f apps/web/Dockerfile .
# docker-compose.yml sets context: . + dockerfile: apps/web/Dockerfile.
# Source files are copied individually (not `COPY apps/web .`) so a stray
# apps/web/node_modules in the context can never reach a layer.

# --- Stage 1: install deps from the lockfile, then build. ---
FROM node:22-slim AS build

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY apps/web/next.config.ts apps/web/tsconfig.json apps/web/next-env.d.ts apps/web/postcss.config.mjs ./
COPY apps/web/src ./src

# NEXT_PUBLIC_* is inlined into the client bundle at BUILD time — changing it
# at runtime alone does nothing, so it is a build arg AND re-declared at
# runtime. The default http://localhost:8000 is what the browser needs on the
# compose dev machine: the API is published on host port 8000, so opening
# http://localhost:3000 reaches the API at http://localhost:8000.
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}

RUN npm run build

# --- Stage 2: standalone server only (traced node_modules, no devDeps). ---
FROM node:22-slim

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY --from=build /app/.next/standalone/ ./
COPY --from=build /app/.next/static/ ./.next/static/
# apps/web has no public/ directory in the repo; if one is ever created, add:
#   COPY --from=build /app/public/ ./public/

# node:22-slim ships the unprivileged "node" user (uid 1000).
USER node

EXPOSE 3000

CMD ["node", "server.js"]
