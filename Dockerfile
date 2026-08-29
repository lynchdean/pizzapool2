FROM python:3.14-slim

WORKDIR /app

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
