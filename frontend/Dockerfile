# Multi-stage build - same shape as the other portfolio projects
# (deps -> builder -> runner), keeping the final image to just the
# standalone server output instead of the full node_modules tree.

# ---- deps: install once, cached separately from source changes ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- builder: compile with a placeholder API URL baked in ----
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Next.js inlines every NEXT_PUBLIC_* variable into the client bundle at
# BUILD time - but the real API URL isn't known here, it's an EasyPanel
# runtime env var. Bake in a unique placeholder token instead; the
# entrypoint script swaps it for the real value right before the server
# starts. Same workaround already proven in the Nexus project for this
# exact category of platform constraint.
ENV NEXT_PUBLIC_API_URL=__RUNTIME_NEXT_PUBLIC_API_URL__
RUN npm run build

# ---- runner: minimal image, only what's needed to serve the app ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh

USER nextjs
EXPOSE 3000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["node", "server.js"]
