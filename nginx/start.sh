#!/bin/sh
# Если реальных сертификатов нет — создаём самоподписанный placeholder,
# чтобы nginx мог стартовать до получения сертификата от Let's Encrypt.

CERT_DIR="/etc/letsencrypt/live/bersnakx.ru"

if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    echo "→ SSL certs not found. Installing openssl..."
    apk add --no-cache openssl > /dev/null 2>&1

    echo "→ Generating self-signed placeholder..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out    "$CERT_DIR/fullchain.pem" \
        -subj   "/CN=localhost"

    if [ -f "$CERT_DIR/fullchain.pem" ]; then
        echo "→ Placeholder cert created successfully."
    else
        echo "ERROR: Failed to create placeholder cert!"
        exit 1
    fi
fi

exec nginx -g "daemon off;"
