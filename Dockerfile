FROM python:3.14-slim

WORKDIR /app

# curl/wget: python:3.14-slim ships neither, but Coolify's container
# healthcheck runs one of them *inside* the container to hit /healthz/ - so
# without these the healthcheck can never pass, regardless of whether the app
# itself is healthy.
RUN apt-get update && apt-get install -y --no-install-recommends curl wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic only needs settings.py to import cleanly, not real secrets or
# a live DB connection - these placeholders are baked into the image but get
# overridden by Coolify's actual runtime env vars when the container starts.
RUN SECRET_KEY=build-time-placeholder \
    DB_NAME=build DB_USER=build DB_PASSWORD=build DB_HOST=build DB_PORT=5432 \
    python manage.py collectstatic --noinput

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
