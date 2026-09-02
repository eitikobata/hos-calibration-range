# Multi-stage build - same shape as the other portfolio projects
# (deps -> builder -> runner), keeping the final image to just the
# standalone server output instead of the full node_modules tree.

# ---- deps: install once, cached separately from source changes ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- builder: compile with the real API URL baked in ----
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# EasyPanel passes configured env vars as a build ARG - confirmed from
# the actual deploy invocation (--build-arg 'NEXT_PUBLIC_API_URL=...').
# This lines up with how Next.js needs it anyway: NEXT_PUBLIC_* vars get
# inlined into the client bundle during `next build`, not read at
# runtime, so consuming it as a build ARG here is the standard pattern -
# no placeholder/sed swap needed on this platform, unlike whatever forced
# that workaround in the Nexus project.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# ---- runner: minimal image, only what's needed to serve the app ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
# Without this, the standalone server binds to localhost only - reachable
# from inside the container, invisible to anything outside it (like
# EasyPanel's reverse proxy). This is Next.js's own documented
# requirement for standalone Docker deployments, not an EasyPanel quirk.
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
