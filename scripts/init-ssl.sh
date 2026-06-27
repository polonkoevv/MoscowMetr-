#!/bin/bash
# Получение SSL-сертификата от Let's Encrypt.
# Запускать ОДИН РАЗ на сервере после первого деплоя.
#
# Использование:
#   bash scripts/init-ssl.sh your-domain.ru your@email.com

set -e

DOMAIN=${1:?"Укажи домен: bash init-ssl.sh your-domain.ru email@example.com"}
EMAIL=${2:?"Укажи email: bash init-ssl.sh your-domain.ru email@example.com"}

echo "→ Домен: $DOMAIN"
echo "→ Email:  $EMAIL"

# 1. Запускаем nginx только с HTTP (для прохождения challenge)
echo "→ Запускаем nginx..."
docker compose up -d nginx

# 2. Получаем сертификат
echo "→ Получаем сертификат..."
docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

# 3. Заменяем YOUR_DOMAIN в nginx конфиге
echo "→ Прописываем домен в nginx конфиге..."
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx/conf.d/reval.conf

# 4. Перезапускаем nginx с HTTPS
echo "→ Перезапускаем nginx..."
docker compose restart nginx

echo ""
echo "✅ SSL настроен! Приложение доступно на https://$DOMAIN"
echo "   Сертификат обновляется автоматически каждые 12 часов."
