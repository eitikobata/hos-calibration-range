#!/bin/sh
set -e

# Swap the placeholder baked in at build time for the real
# NEXT_PUBLIC_API_URL that EasyPanel injects at container runtime.
# Without this, the deployed site would keep pointing at the placeholder
# token (or a stale value from whenever the image was built) - a bug
# that's invisible until you actually open the site and try to use it,
# since the build itself succeeds either way.
if [ -n "$NEXT_PUBLIC_API_URL" ]; then
  find /app/.next /app/public -type f \( -name "*.js" -o -name "*.html" \) 2>/dev/null | \
    xargs -r sed -i "s|__RUNTIME_NEXT_PUBLIC_API_URL__|$NEXT_PUBLIC_API_URL|g"
fi

exec "$@"
