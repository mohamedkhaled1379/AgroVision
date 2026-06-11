# Production Deployment Guide

## 1) Prepare environment

- Copy `.env.example` to `.env` and set real secrets.
- Use a strong `SECRET_KEY`.
- Set `FLASK_ENV=production`.

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

## 3) Run in production

```bash
gunicorn -c gunicorn.conf.py app:app
```

## 4) Recommended stack

- Reverse proxy: Nginx
- App server: Gunicorn
- Database: PostgreSQL (recommended upgrade from SQLite)
- TLS: Let's Encrypt certificates

## 5) Security checklist

- HTTPS enabled
- Debug disabled
- Secrets stored in environment variables
- Strong passwords only
- Rate limits active
- Logs rotated and monitored

## 6) CI

- GitHub Actions workflow at `.github/workflows/ci.yml`
- Runs syntax checks and tests on push/PR
