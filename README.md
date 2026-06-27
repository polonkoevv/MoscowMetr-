# ReVal — Интеллектуальная оценка стоимости недвижимости

> Авторы: **Полонкоев Берс** и **Мирзаханов Саид**

ReVal — веб-сервис для автоматической оценки рыночной стоимости недвижимости Москвы. Пользователь задаёт параметры объекта, указывает местоположение на интерактивной карте и получает прогноз цены на основе модели машинного обучения (CatBoost), обученной на реальных объявлениях.

---

## Содержание

1. [Архитектура](#архитектура)
2. [Технологический стек](#технологический-стек)
3. [Структура репозитория](#структура-репозитория)
4. [Модель машинного обучения](#модель-машинного-обучения)
5. [API-сервис](#api-сервис)
6. [Фронтенд](#фронтенд)
7. [Быстрый старт](#быстрый-старт)
8. [Переменные окружения](#переменные-окружения)
9. [Миграции базы данных](#миграции-базы-данных)
10. [Тесты](#тесты)
11. [CI/CD](#cicd)
12. [Деплой на сервер](#деплой-на-сервер)

---

## Архитектура

Система состоит из четырёх основных сервисов, запускаемых через Docker Compose:

```
                          ┌──────────────┐
                          │    Nginx     │  :80 / :443
                          │  (SSL/TLS)   │  bersnakx.ru
                          └──────┬───────┘
                 ┌───────────────┼──────────────────┐
                 ▼               ▼                   ▼
         ┌──────────────┐ ┌──────────────┐  ┌──────────────┐
         │   Frontend   │ │  API Service │  │   pgAdmin    │
         │  Streamlit   │ │   FastAPI    │  │              │
         │   :8501      │ │   :8000      │  │   :5050      │
         └──────────────┘ └──────┬───────┘  └──────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  ▼              ▼               ▼
          ┌──────────────┐ ┌──────────┐ ┌────────────────┐
          │  ML Service  │ │PostgreSQL│ │     Redis      │
          │   FastAPI    │ │  :5433   │ │   (кэш, JWT)   │
          │   :8001      │ └──────────┘ └────────────────┘
          └──────────────┘
```

- **Nginx** — реверс-прокси, SSL-терминация (Let's Encrypt), редирект HTTP → HTTPS, rate limiting на `/api/auth`.
- **Frontend (Streamlit)** — пользовательский интерфейс. Общается с API Service напрямую через HTTP.
- **API Service (FastAPI)** — основной бэкенд: авторизация, ролевая модель, проксирование запросов к ML Service, логирование в БД, кэширование в Redis.
- **ML Service (FastAPI)** — внутренний микросервис предсказания цен. Доступен только внутри Docker-сети, авторизации не требует.
- **PostgreSQL** — хранение пользователей и истории предсказаний.
- **Redis** — хранение refresh-токенов, токенов верификации email, кэш ответов предсказаний (TTL 1 час) и статистики (TTL 30 мин).

---

## Технологический стек

| Слой | Технологии |
|---|---|
| **ML** | Python 3.12, CatBoost, pandas, numpy, scikit-learn, shapely |
| **API** | FastAPI, SQLAlchemy (async), asyncpg, Alembic, Pydantic v2 |
| **Auth** | JWT (python-jose), bcrypt (passlib), Redis (refresh-токены) |
| **Email** | aiosmtplib (фоновая отправка через BackgroundTasks) |
| **Frontend** | Streamlit, Folium (карта), Plotly, streamlit-folium |
| **БД** | PostgreSQL 15, Redis 7 |
| **Инфраструктура** | Docker, Docker Compose, Nginx 1.27, Certbot (Let's Encrypt) |
| **CI/CD** | GitHub Actions (тесты + SSH-деплой) |
| **Логирование** | Loguru |
| **Тесты** | pytest, pytest-asyncio, pytest-cov, httpx, fakeredis |

---

## Структура репозитория

```
.
├── api-service/              # Основной API (FastAPI)
│   ├── app/
│   │   ├── auth/             # JWT, хэширование паролей, зависимости
│   │   ├── db/               # Сессия SQLAlchemy, Redis
│   │   ├── models/           # ORM-модели (User, PredictionLog)
│   │   ├── routers/          # Эндпоинты: auth, predict, listings, stats, admin
│   │   ├── services/         # Отправка email
│   │   └── config.py         # Pydantic Settings (валидация .env)
│   ├── alembic/              # Миграции БД
│   ├── data/                 # listings.parquet, metrics.json
│   ├── tests/                # Тесты (pytest)
│   ├── main.py
│   └── pyproject.toml
│
├── ml-service/               # Сервис предсказания (FastAPI)
│   ├── artifacts/
│   │   ├── model.cbm         # Обученная модель CatBoost
│   │   ├── metrics.json      # Метрики модели
│   │   └── moscow_okrugs.geojson  # Полигоны округов Москвы
│   ├── main.py
│   ├── predictor.py          # Инференс: загрузка модели, feature engineering
│   └── schemas.py            # Pydantic-схемы запроса/ответа
│
├── frontend/                 # Веб-интерфейс (Streamlit)
│   ├── pages/
│   │   ├── 1_Predict.py      # Оценка квартиры
│   │   ├── 2_History.py      # История предсказаний
│   │   ├── 3_Listings.py     # База объявлений
│   │   ├── 4_Stats.py        # Статистика (analyst/admin)
│   │   └── 5_Admin.py        # Управление пользователями (admin)
│   ├── app.py                # Главная страница, авторизация
│   ├── api_client.py         # HTTP-клиент к API Service
│   └── components.py / styles.py
│
├── ml/                       # Обучение модели
│   ├── train.py              # Скрипт обучения CatBoost
│   ├── predict.py            # Локальное предсказание
│   └── artifacts/            # model.cbm (локальная копия)
│
├── nginx/                    # Конфигурация Nginx
│   ├── nginx.conf
│   └── conf.d/reval.conf
│
├── notebooks/
│   └── eda.ipynb             # Разведочный анализ данных
│
├── data/
│   ├── listings.parquet      # Датасет объявлений
│   └── moscow_okrugs.geojson # GeoJSON округов Москвы
│
├── scripts/                  # Вспомогательные скрипты
├── .github/workflows/
│   └── deploy.yml            # CI/CD pipeline
├── docker-compose.yml
├── .env.example
└── Dockerfile.postgres
```

---

## Модель машинного обучения

### Задача

Предсказание рыночной стоимости объекта недвижимости в Московском регионе.

**Таргет:** `log1p(price_per_m2)` → результат обратно преобразуется через `expm1`, затем умножается на `total_area`, чтобы получить итоговую цену.

### Алгоритм

**CatBoostRegressor** (2000 итераций, встроенная обработка категориальных признаков).

### Признаки (21 штука)

| Группа | Признаки |
|---|---|
| **Числовые** | `total_area`, `floor`, `floors`, `distance`, `lat`, `lon`, `floor_ratio`, `month`, `quarter` |
| **Категориальные** | `rooms_code`, `remont_code`, `hometype_code`, `deal_type_code`, `category`, `property_kind`, `region_id`, `bucket`, `okrug` |
| **Бинарные** | `new_building`, `is_first_floor`, `is_top_floor` |

`floor_ratio`, `is_first_floor`, `is_top_floor` — производные признаки, строятся из `floor` и `floors` на этапе feature engineering.

`okrug` (округ Москвы) определяется автоматически по координатам `lat`/`lon` через полигоны из `moscow_okrugs.geojson` (библиотека `shapely`).

### Метрики

| Метрика | Модель | Baseline (медиана по region_id) |
|---|---|---|
| **MAPE** | **29.6%** | 565.8% |
| **MAE (цена/м²)** | 60 037 ₽ | 134 476 ₽ |
| **MAE (цена)** | 5 272 078 ₽ | — |
| **RMSE (цена)** | 17 914 193 ₽ | 608 490 ₽ |

### Обучение модели

```bash
# Из корня репозитория
python ml/train.py
```

Модель сохраняется в `ml/artifacts/model.cbm`, метрики — в `ml/artifacts/metrics.json`. Для использования в сервисе скопируйте артефакты в `ml-service/artifacts/`.

---

## API-сервис

Документация доступна по адресу `http://localhost:8000/docs` (Swagger UI).

### Ролевая модель

| Роль | Возможности |
|---|---|
| `user` | Регистрация, вход, оценка объектов, просмотр своей истории, база объявлений |
| `analyst` | Всё от `user` + доступ к статистике (`/stats`) |
| `admin` | Всё от `analyst` + управление пользователями (`/admin/users`) |

### Основные эндпоинты

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `POST` | `/auth/register` | Регистрация | Все |
| `POST` | `/auth/login` | Вход, выдача токенов | Все |
| `POST` | `/auth/refresh` | Обновление access-токена | Все |
| `POST` | `/auth/logout` | Отзыв refresh-токена | Все |
| `GET` | `/auth/verify` | Подтверждение email | Все |
| `GET` | `/auth/me` | Данные текущего пользователя | Авторизованные |
| `POST` | `/predict` | Оценка объекта | Авторизованные |
| `GET` | `/predict/history` | История предсказаний | Авторизованные |
| `GET` | `/listings` | База объявлений | Авторизованные |
| `GET` | `/stats` | Статистика и метрики | analyst, admin |
| `GET` | `/admin/users` | Список пользователей | admin |
| `PATCH` | `/admin/users/{id}` | Изменение роли / блокировка | admin |
| `GET` | `/health` | Health check | Все |

### Авторизация

- **Access-токен** (JWT): срок действия 30 минут, передаётся в заголовке `Authorization: Bearer <token>`.
- **Refresh-токен**: срок действия 30 дней, хранится в Redis. Позволяет получить новый access-токен без повторного входа.
- **Email-верификация**: при регистрации на почту отправляется ссылка с одноразовым токеном (TTL 24 ч, хранится в Redis).

### Кэширование (Redis)

| Что | TTL |
|---|---|
| Результат предсказания (по SHA256 входных данных) | 1 час |
| Статистика по объявлениям | 30 минут |

---

## Фронтенд

Streamlit-приложение с пятью страницами:

| Страница | Описание |
|---|---|
| **Главная** | Авторизация (вход / регистрация) |
| **Оценить квартиру** | Форма с параметрами + интерактивная карта (Folium) для выбора координат; вывод цены, цены за м², округа и погрешности модели |
| **История** | Таблица прошлых оценок текущего пользователя |
| **Объявления** | Браузер базы объявлений с фильтрацией |
| **Статистика** | Медианная цена за м² по округам (бар-чарт Plotly), распределение типов объектов (analyst/admin) |
| **Пользователи** | Управление ролями и статусом аккаунтов (admin) |

---

## Быстрый старт

### Требования

- Docker ≥ 24
- Docker Compose ≥ 2.20

### 1. Клонирование и настройка

```bash
git clone <repo-url>
cd pyProject
cp .env.example .env
# Заполните .env (см. раздел «Переменные окружения»)
```

### 2. Запуск

```bash
docker compose up --build -d
```

### 3. Сервисы

| Сервис | URL |
|---|---|
| Фронтенд | http://localhost:8501 |
| API Swagger | http://localhost:8000/docs |
| ML Service | http://localhost:8001/docs |
| pgAdmin | http://localhost:5050 |

При первом запуске автоматически создаётся администратор с `ADMIN_EMAIL` / `ADMIN_PASSWORD` из `.env`.

---

## Переменные окружения

Скопируйте `.env.example` → `.env` и заполните:

```dotenv
# PostgreSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=<сильный пароль>

# pgAdmin
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=<пароль>

# JWT (минимум 32 символа, генерация: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=<случайная строка>

# Первый администратор (создаётся при старте)
ADMIN_EMAIL=admin@reval.ru
ADMIN_PASSWORD=<сильный пароль>

# SMTP (для писем верификации email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=<app-password>
SMTP_FROM=your@gmail.com

# URL сервиса (подставляется в ссылку в письме)
FRONTEND_URL=https://bersnakx.ru
```

> **Важно:** `SECRET_KEY` и `ADMIN_PASSWORD` **не могут** быть значениями по умолчанию (`change-me` / `changeme`) — приложение откажется запускаться.

---

## Миграции базы данных

Миграции управляются через **Alembic** и применяются автоматически при старте `api-service`.

Ручной запуск внутри контейнера:

```bash
docker compose exec api-service alembic upgrade head
```

История миграций:

| Версия | Описание |
|---|---|
| `0001_initial` | Создание таблиц `users`, `prediction_logs` |
| `0002_refresh_tokens` | Добавление таблицы `refresh_tokens` |
| `0003_drop_refresh_tokens_table` | Удаление таблицы (refresh-токены перенесены в Redis) |
| `0004_add_is_verified` | Поле `is_verified` в таблице `users` |

---

## Тесты

```bash
cd api-service
pip install -e ".[dev]"
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite "fakeredis[aioredis]"
pytest -v
```

Покрытие выводится в терминал (`--cov=app --cov-report=term-missing`).

Тесты используют `aiosqlite` (in-memory SQLite) и `fakeredis` вместо реальных PostgreSQL и Redis — внешние зависимости не нужны.

Модули тестов:

- `test_auth.py` — регистрация, вход, refresh, logout
- `test_health.py` — health check эндпоинт
- `test_jwt.py` — создание и валидация JWT
- `test_passwords.py` — хэширование паролей
- `test_schemas.py` — валидация Pydantic-схем запроса предсказания

---

## CI/CD

Пайплайн `.github/workflows/deploy.yml` запускается при пуше в ветку `main`:

1. **Тесты** — поднимает окружение, устанавливает зависимости, запускает `pytest`.
2. **Деплой** (только если тесты прошли) — подключается по SSH к серверу, обновляет код (`git pull`), записывает `.env` из GitHub Secrets, пересобирает контейнеры (`docker compose up --build -d`).

Требуемые GitHub Secrets:

```
SSH_HOST, SSH_USER, SSH_PRIVATE_KEY, SSH_PORT
REPO_URL, DEPLOY_PATH
POSTGRES_USER, POSTGRES_PASSWORD, PGADMIN_EMAIL, PGADMIN_PASSWORD
SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
FRONTEND_URL
```

---

## Деплой на сервер

Проект задеплоен на домен **bersnakx.ru** с SSL-сертификатом от Let's Encrypt.

### Первичная настройка SSL

```bash
# Запустить Nginx без SSL (только HTTP для прохождения challenge)
docker compose up nginx certbot -d

# Получить сертификат
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d bersnakx.ru \
  --email your@email.com --agree-tos --no-eff-email

# Перезапустить Nginx с HTTPS
docker compose restart nginx
```

Certbot автоматически обновляет сертификат каждые 12 часов.

### Восстановление БД из дампа

```bash
./init-restore.sh
```

Скрипт восстанавливает базу из дампа `postgres/du_portal_diploma.dump`.
