# BeConversive Confession – Deployment Plan

This document outlines how to deploy the app so that:

1. **Web app** runs on a public URL (HTTPS).
2. **Admin** can log in and approve confessions.
3. **Approved confessions** are sent to SQS → **Lambda** posts to Instagram.
4. **Generated images** are served at a public URL so Lambda/Instagram can fetch them.

---

## Architecture overview

```
[User] → [Web App (HTTPS)] → submit → [DB + generated_images]
                ↑
[Admin] → /admin → approve → [SQS] → [Lambda] → [Instagram Graph API]
                ↑
         image_url = PUBLIC_BASE_URL + /generated_images/...
```

- **Web app**: FastAPI (Docker). Must be reachable at `PUBLIC_BASE_URL` (e.g. `https://confession.yourdomain.com`).
- **Database**: SQLite (single instance) or PostgreSQL (for multi-instance / backups).
- **Storage**: `generated_images/` and `backgrounds/` must persist and be served by the app (or a CDN).
- **AWS**: SQS queue + Lambda (see `lambda/README.md`). App needs AWS credentials to send messages; Lambda needs Instagram credentials and SQS trigger.

---

## Pre-deployment checklist

### 1. Environment variables (app)

| Variable | Required | Notes |
|----------|----------|--------|
| `ADMIN_PASSWORD` | Yes | Admin login for `/admin`. |
| `SECRET_KEY` | Yes | Strong random value; used for admin cookie signing. |
| `PUBLIC_BASE_URL` | Yes | Full public URL of the app (e.g. `https://confession.example.com`). Used when approving so `image_url` is reachable by Lambda/Instagram. |
| `SQS_QUEUE_URL` | Yes | SQS queue URL where the app sends approval messages. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Or IAM role | For boto3 to send messages to SQS. |
| `AWS_REGION` | Optional | Default `us-east-1`. Must match the SQS queue region. |
| `DATABASE_URL` | Optional | Default SQLite. Use PostgreSQL for production if you need backups or multiple app instances. |
| `MAX_CONFESSION_LENGTH` | Optional | Default 500. |
| `RATE_LIMIT_PER_HOUR` | Optional | Default 10. |
| `INSTAGRAM_*` | No (for app) | Not used by the app; only Lambda needs these for posting. |

### 2. AWS (SQS + Lambda)

- **SQS**: Create a standard queue. Note the queue URL; set `SQS_QUEUE_URL` in the app.
- **Lambda**: Deploy as in `lambda/README.md`. Set `INSTAGRAM_USER_ID` and `INSTAGRAM_ACCESS_TOKEN` on the function. Add SQS as trigger (same queue).
- **IAM**: App only needs `sqs:SendMessage` on that queue. Lambda needs SQS read + Instagram (no extra AWS resources).

### 3. Domain and SSL

- Reserve a domain (e.g. `confession.yourdomain.com`).
- Plan to terminate HTTPS on the server (reverse proxy) or on the platform (e.g. Railway/Render). `PUBLIC_BASE_URL` must use this HTTPS URL.

---

## Deployment options

### Option A: Single VPS (Docker + reverse proxy)

**Best for:** Full control, low cost, one server.

1. **VPS**: e.g. DigitalOcean Droplet, Linode, or AWS EC2 (Ubuntu 22.04). 1 GB RAM is enough to start.
2. **Docker**: Install Docker and Docker Compose on the VPS.
3. **Data**: Use bind mounts or named volumes for `generated_images`, `backgrounds`, and `confessions.db` (or point `DATABASE_URL` to a managed DB).
4. **Reverse proxy + SSL**: Run Caddy or Nginx in front (or in the same compose) with Let’s Encrypt so the app is served over HTTPS. Caddy auto-obtains certs if you set the domain.
5. **Env**: Create `.env` on the server (or use secrets). Set `PUBLIC_BASE_URL=https://confession.yourdomain.com`.
6. **Run**:
   ```bash
   docker compose up -d --build
   ```
7. **DNS**: Point `confession.yourdomain.com` to the VPS IP.

**Example Caddy (optional):** Run Caddy in front of the app; Caddy listens 443 and proxies to `http://web:8000`. Then `PUBLIC_BASE_URL` = `https://confession.yourdomain.com`.

---

### Option B: PaaS (Railway, Render, Fly.io)

**Best for:** Minimal ops, automatic HTTPS, optional DB.

1. **Connect repo**: Link GitHub/GitLab to the platform.
2. **Build**: Use existing `Dockerfile` or let the platform build from the repo.
3. **Config**: Set all env vars in the platform dashboard (no `.env` in repo). Set `PUBLIC_BASE_URL` to the platform-assigned URL (e.g. `https://yourapp.railway.app`).
4. **Storage**: PaaS often has ephemeral disks. For persistence:
   - Use a **volume** if the platform supports it for `generated_images` and (if needed) SQLite DB, or
   - Use **external storage** (e.g. S3) and change the app to serve images from there (requires code changes).
5. **Database**: For SQLite, ensure the DB file is on a persistent volume. Or set `DATABASE_URL` to a managed PostgreSQL (Render/Railway offer add-ons).
6. **AWS**: Keep `SQS_QUEUE_URL` and AWS credentials in env; Lambda stays on AWS.

---

### Option C: AWS ECS → SQS → Lambda

**Best for:** Everything in one cloud, IAM roles for SQS, no long-lived AWS keys in the app.

**Full step-by-step:** See **[docs/DEPLOYMENT-ECS-SQS-LAMBDA.md](docs/DEPLOYMENT-ECS-SQS-LAMBDA.md)** for:

- ECR, EFS (generated_images + SQLite), SQS queue
- IAM roles (ECS task execution, ECS task role for SQS, Lambda)
- Secrets Manager, ECS task definition (Fargate, env, EFS mounts)
- ALB (HTTPS/ACM), target group, security groups, ECS service
- Lambda deploy and SQS trigger
- Post-deploy checks and cost notes

Summary: Run the Docker image on ECS Fargate behind an ALB; set `PUBLIC_BASE_URL` to the ALB (or custom domain) URL; store secrets in Secrets Manager; give the ECS task role `sqs:SendMessage` on the approval queue; Lambda consumes SQS and posts to Instagram.

---

## Recommended path (simple production)

1. **VPS (e.g. $5–6/mo)** with Docker Compose.
2. **Caddy** in front for HTTPS and `PUBLIC_BASE_URL=https://confession.yourdomain.com`.
3. **SQLite** with a bind-mounted `confessions.db` and backups (cron + copy to S3 or another server).
4. **Bind mounts** for `generated_images` and `backgrounds` so they survive restarts.
5. **SQS + Lambda** on AWS as in `lambda/README.md`; app env: `SQS_QUEUE_URL`, `PUBLIC_BASE_URL`, `ADMIN_PASSWORD`, `SECRET_KEY`, AWS credentials (or IAM if on EC2).

---

## Post-deploy checks

- [ ] `https://<PUBLIC_BASE_URL>/` loads the confession form.
- [ ] Submit a test confession; it appears as PENDING (no Instagram post from app).
- [ ] Open `https://<PUBLIC_BASE_URL>/admin`, log in with `ADMIN_PASSWORD`.
- [ ] Approve the test confession; it should disappear from pending (or show “Queued”). Check SQS for the message and Lambda logs for a successful Instagram post.
- [ ] Open `https://<PUBLIC_BASE_URL>/generated_images/<filename>.png` (from DB or admin UI) – should return the image (required for Lambda/Instagram).

---

## Summary

| Item | Action |
|------|--------|
| App runtime | Docker (existing Dockerfile + docker-compose). |
| Public URL | Set `PUBLIC_BASE_URL` to the exact HTTPS URL users and Lambda use. |
| Admin | Set `ADMIN_PASSWORD` and `SECRET_KEY`. |
| SQS + Lambda | Deploy Lambda per `lambda/README.md`; set `SQS_QUEUE_URL` and AWS creds (or IAM) for the app. |
| DB & files | Persist `confessions.db`, `generated_images/`, `backgrounds/` (volumes or external DB/storage). |
| SSL | Use reverse proxy (Caddy/Nginx) or platform-managed HTTPS. |

If you tell me your preferred option (VPS, PaaS, or AWS), I can turn this into step-by-step commands (e.g. exact Caddy config or a `docker-compose.prod.yml`).
