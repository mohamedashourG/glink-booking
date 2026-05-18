# fallback — outage page. Static export served by nginx.
#
# The Next.js build needs ../../.data/clients.json, which is gitignored AND
# excluded from the docker build context by the monorepo .dockerignore. So
# the build runs LOCALLY (npm run build → ./out) and this Dockerfile only
# packages the prebuilt ./out into an nginx image.
#
# Re-run the deploy script after any provisioning change to refresh the page.

FROM nginx:1.27-alpine

# nginx default conf serves /usr/share/nginx/html on :80. trailingSlash:true
# in next.config.js means each page is `slug/index.html`, so nginx's default
# index handling Just Works for /<slug>/.
COPY out/ /usr/share/nginx/html/

# A simple healthcheck endpoint — nginx returns 200 for any existing file.
# We rely on the index page existing; if there are zero clients, the build
# still emits app/page.tsx as /index.html.

EXPOSE 80
