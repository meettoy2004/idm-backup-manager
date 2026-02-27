# Stage 1: build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --silent
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:1.27-alpine
RUN rm /etc/nginx/conf.d/default.conf

# Bake both HTTP and SSL configs into the image.
# The entrypoint copies the appropriate one to conf.d/app.conf at runtime.
COPY nginx.conf     /etc/nginx/http.conf
COPY nginx-ssl.conf /etc/nginx/ssl.conf
COPY nginx.conf     /etc/nginx/conf.d/app.conf

# Entrypoint: selects config and polls for SSL reload trigger
COPY entrypoint.sh /entrypoint.sh
RUN  chmod +x /entrypoint.sh

COPY --from=builder /app/dist /usr/share/nginx/html

# Create the SSL volume mount point so it exists before Docker attaches the volume
RUN mkdir -p /etc/ssl/idm-toolkit

RUN chown -R nginx:nginx /usr/share/nginx/html \
 && chown -R nginx:nginx /var/cache/nginx \
 && chown -R nginx:nginx /var/log/nginx \
 && chown -R nginx:nginx /etc/nginx/conf.d \
 && touch /var/run/nginx.pid \
 && chown nginx:nginx /var/run/nginx.pid

USER nginx
EXPOSE 80 443
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/health || exit 1
ENTRYPOINT ["/entrypoint.sh"]
