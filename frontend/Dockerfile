# ── Stage 1 : build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --frozen-lockfile

COPY . .

# VITE_API_URL vient de .env.production (copié ci-dessus) : pas d'ARG/ENV ici,
# une variable d'environnement (même vide) passerait avant .env.production.
RUN npm run build

# ── Stage 2 : serve avec nginx ────────────────────────────────────────────────
FROM nginx:1.25-alpine

# Mode SPA : le site déployable (index.html + assets) est dans dist/client/
COPY --from=builder /app/dist/client /usr/share/nginx/html

# Config nginx pour SPA (toutes routes → index.html)
RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    location ~* \\.(js|css|png|jpg|svg|woff2)$ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/index.html || exit 1
