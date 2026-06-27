#!/bin/sh
# Если реальных сертификатов нет — создаём самоподписанный placeholder,
# чтобы nginx мог стартовать до получения сертификата от Let's Encrypt.

CERT_DIR="/etc/letsencrypt/live/bersnakx.ru"

if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    echo "→ SSL certs not found. Generating self-signed placeholder..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out  "$CERT_DIR/fullchain.pem" \
        -subj "/CN=localhost" 2>/dev/null
    echo "→ Placeholder cert created. Run scripts/init-ssl.sh to get real certs."
fi

exec nginx -g "daemon off;"
