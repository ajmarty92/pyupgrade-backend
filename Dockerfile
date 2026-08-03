FROM python:3.11.6-slim

WORKDIR /app

# git is required at runtime: scanner.py shells out to GitPython, which needs
# the actual `git` binary to clone repositories being scanned.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Overridden per Fly.io process group (see fly.toml) for the Celery worker;
# this is the default/"web" entrypoint.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
