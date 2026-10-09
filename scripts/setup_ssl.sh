#!/usr/bin/env bash
# Install Let's Encrypt certificates for applyxai.com (nginx on Ubuntu).
set -euo pipefail

DOMAINS=(applyxai.com www.applyxai.com)
WEBROOT=/var/www/certbot
APP_DIR="${APP_DIR:-/home/ubuntu/applyxai}"
NGINX_SITE=/etc/nginx/sites-available/applyxai
REPO_CONF="$APP_DIR/scripts/nginx/applyxai.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/setup_ssl.sh" >&2
  exit 1
fi

if [[ ! -f "$REPO_CONF" ]]; then
  echo "Missing $REPO_CONF — pull latest code first." >&2
  exit 1
fi

EMAIL="${CERTBOT_EMAIL:-}"
if [[ -z "$EMAIL" && -f "$APP_DIR/.env" ]]; then
  EMAIL="$(grep -E '^SMTP_FROM=' "$APP_DIR/.env" | head -1 | cut -d= -f2- | tr -d ' "' || true)"
fi
if [[ -z "$EMAIL" ]]; then
  echo "Set CERTBOT_EMAIL or SMTP_FROM in $APP_DIR/.env" >&2
  exit 1
fi
if [[ "$EMAIL" == *@example.com ]] || [[ "$EMAIL" == *@example.org ]]; then
  echo "SMTP_FROM is a placeholder ($EMAIL). Export CERTBOT_EMAIL=you@real-domain.com" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx nginx

mkdir -p "$WEBROOT"

# HTTP-only bootstrap so ACME HTTP-01 works before LE certs exist.
cat > "$NGINX_SITE" <<'BOOT'
server {
    listen 80;
    listen [::]:80;
    server_name applyxai.com www.applyxai.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name applyxai.com www.applyxai.com;

    ssl_certificate /etc/ssl/certs/applyxai-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/applyxai-selfsigned.key;

    location / {
        root /home/ubuntu/applyxai/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
BOOT

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/applyxai
nginx -t
systemctl reload nginx

DOMAIN_ARGS=()
for d in "${DOMAINS[@]}"; do
  DOMAIN_ARGS+=(-d "$d")
done

certbot certonly --webroot -w "$WEBROOT" \
  "${DOMAIN_ARGS[@]}" \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  --keep-until-expiring

if [[ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]]; then
  if [[ -f /usr/share/doc/python3-certbot-nginx/examples/options-ssl-nginx.conf ]]; then
    cp /usr/share/doc/python3-certbot-nginx/examples/options-ssl-nginx.conf /etc/letsencrypt/options-ssl-nginx.conf
  else
    cat > /etc/letsencrypt/options-ssl-nginx.conf <<'OPTS'
ssl_session_cache shared:le_nginx_SSL:10m;
ssl_session_timeout 1440m;
ssl_session_tickets off;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_ciphers "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384";
OPTS
  fi
fi
if [[ ! -f /etc/letsencrypt/ssl-dhparams.pem ]]; then
  openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
fi

install -m 644 "$REPO_CONF" "$NGINX_SITE"
nginx -t
systemctl reload nginx

if ! systemctl is-enabled certbot.timer >/dev/null 2>&1; then
  systemctl enable certbot.timer
fi
systemctl start certbot.timer

echo "SSL active for ${DOMAINS[*]}"
certbot certificates
