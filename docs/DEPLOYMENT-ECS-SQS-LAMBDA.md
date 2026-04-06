# BeConversive Confession – ECS → SQS → Lambda Deployment Plan

Deploy the web app on **Amazon ECS (Fargate)** behind an **Application Load Balancer**, with approvals sent to **SQS** and **Lambda** posting to Instagram.

---

## Architecture

```
[User/Admin] ──HTTPS──► [ALB] ──► [ECS Fargate task]
                                    │
                                    ├── FastAPI (port 8000)
                                    ├── EFS: /app/generated_images, /app/data (SQLite)
                                    └── IAM: sqs:SendMessage
                                    │
                                    ▼
                              [SQS Queue]
                                    │
                                    ▼
                              [Lambda]
                                    │
                                    ▼
                              [Instagram Graph API]
```

- **ALB**: HTTPS (ACM), forwards to ECS target group. This URL is `PUBLIC_BASE_URL` (Lambda/Instagram fetch images from here).
- **ECS**: One Fargate task (or two for HA). Task gets env/secrets from Secrets Manager or task definition. Writes images and DB to EFS.
- **SQS**: One standard queue. ECS sends one message per approval; Lambda consumes.
- **Lambda**: Triggered by SQS; reads `image_url` + `caption`, posts to Instagram (see `lambda/README.md`).

---

## Prerequisites

- AWS account, AWS CLI configured.
- Docker (to build and push image to ECR).
- (Optional) Domain and ACM certificate for a custom hostname; otherwise use ALB DNS and HTTP (not recommended for production).

---

## Step 1: ECR repository and image

1. Create ECR repo (e.g. in `us-east-1`):

   ```bash
   aws ecr create-repository --repository-name beconversive-confession --region us-east-1
   ```

2. Authenticate Docker to ECR:

   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   ```

3. Build and push (from project root):

   ```bash
   export ECR_URI=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/beconversive-confession:latest
   docker build -t beconversive-confession .
   docker tag beconversive-confession:latest $ECR_URI
   docker push $ECR_URI
   ```

Use the same region for ECS, SQS, and Lambda below.

---

## Step 2: EFS for persistent data

The app needs **persistent** `generated_images/` and `confessions.db`. ECS task storage is ephemeral, so use EFS.

1. **Create EFS file system** (same VPC as ECS):

   ```bash
   aws efs create-file-system --performance-mode generalPurpose --throughput-mode bursting \
     --encrypted --tags Key=Name,Value=beconversive-confession --region us-east-1
   ```

   Note the `FileSystemId`.

2. **Create mount targets** in the same subnets you will use for ECS (e.g. private subnets). You need at least one per AZ you run tasks in.

3. **Create two access points** (so the app can use fixed paths with correct permissions):

   - **Generated images**  
     Path: `/generated_images`  
     UID/GID: 1000 (or the user your container runs as; adjust if your image uses a non-root user).  
     Permissions: 0755.

   - **Data (SQLite)**  
     Path: `/data`  
     UID/GID: 1000.  
     Permissions: 0755.

   Create via Console (EFS → Access points) or CLI. Note each `AccessPointId`.

4. **Backgrounds**: The Docker image already contains `backgrounds/`. No EFS mount for backgrounds; keep them in the image.

---

## Step 3: SQS queue

1. Create standard queue (same region as ECS/Lambda):

   ```bash
   aws sqs create-queue --queue-name confession-approval-queue --region us-east-1
   ```

2. Get queue URL:

   ```bash
   aws sqs get-queue-url --queue-name confession-approval-queue --region us-east-1
   ```

   Set this as `SQS_QUEUE_URL` for the ECS task (see Step 6). Optionally add a dead-letter queue for failed Lambda invocations.

---

## Step 4: IAM roles

### 4a. ECS task execution role

Used by ECS to pull the image and write logs. If you don’t have one, create a role with:

- `AmazonECSTaskExecutionRolePolicy` (managed policy).

### 4b. ECS task role (application role)

Used by the FastAPI app (boto3) to send messages to SQS. Create a role (e.g. `ecsTaskRole-beconversive`) and attach an inline or custom policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "arn:aws:sqs:us-east-1:<ACCOUNT_ID>:confession-approval-queue"
    }
  ]
}
```

Attach this role to the **task definition** (not the execution role).

### 4c. Lambda execution role

Lambda needs: read from SQS, write logs. Attach:

- `AWSLambdaSQSQueueExecutionRole` (or inline: `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on the queue).

No VPC required for calling the Instagram API.

---

## Step 5: Secrets (recommended)

Store sensitive values in **Secrets Manager** (or SSM Parameter Store) and reference them in the ECS task definition.

1. Create a secret (e.g. `beconversive-confession/app`) with JSON:

   ```json
   {
     "ADMIN_PASSWORD": "your-secure-admin-password",
     "SECRET_KEY": "your-long-random-secret-key"
   }
   ```

2. Ensure the **ECS task execution role** has `secretsmanager:GetSecretValue` (or `ssm:GetParameters`) on this secret.

3. In the task definition (Step 6), inject these as environment variables using the “valueFrom” form pointing at the secret.

4. **SQS_QUEUE_URL** and **PUBLIC_BASE_URL** are non-secret; set them as plain env vars in the task definition (or from Parameter Store).

---

## Step 6: ECS cluster, task definition, service

### 6a. Cluster

```bash
aws ecs create-cluster --cluster-name beconversive --region us-east-1
```

### 6b. Task definition (Fargate)

Create a task definition JSON (or use Console) with:

- **Family**: `beconversive-confession`
- **Network mode**: `awsvpc`
- **CPU**: 512 (0.5 vCPU)
- **Memory**: 1024 MB
- **Task execution role**: (from Step 4a)
- **Task role**: (from Step 4b – for SQS)
- **Volumes**:
  - `generated-images`: EFS, `FileSystemId` = your EFS id, `TransitEncryption` = ENABLED, `AuthorizationConfig` with `AccessPointId` for `/generated_images`, `Iam` = ENABLED.
  - `data`: EFS, same file system, access point for `/data`, IAM = ENABLED.
- **Container**:
  - **Image**: `$ECR_URI`
  - **Port**: 8000
  - **Mount points**:
    - Source volume `generated-images` → container path `/app/generated_images`
    - Source volume `data` → container path `/app/data`
  - **Environment** (plain):
    - `PUBLIC_BASE_URL` = `https://<your-alb-dns-or-domain>`
    - `SQS_QUEUE_URL` = queue URL from Step 3
    - `AWS_REGION` = `us-east-1`
    - `DATABASE_URL` = `sqlite:////app/data/confessions.db`
  - **Secrets** (valueFrom Secrets Manager):
    - `ADMIN_PASSWORD` from secret
    - `SECRET_KEY` from secret
  - **Logging**: awslogs driver, group `/ecs/beconversive-confession`
  - **Health check** (optional): `CMD-SHELL, curl -f http://localhost:8000/api/health || exit 1` with interval 30s, timeout 5s, retries 2, startPeriod 60s.

An **example task definition** with placeholders is in `docs/ecs-task-definition.example.json`. Replace:

- `<ACCOUNT_ID>` everywhere
- `<EFS_FILE_SYSTEM_ID>`, `<EFS_ACCESS_POINT_ID_GENERATED_IMAGES>`, `<EFS_ACCESS_POINT_ID_DATA>`
- `PUBLIC_BASE_URL` and `SQS_QUEUE_URL` values
- Secret ARNs in `secrets`: use the real Secrets Manager ARN (it includes a 6-character suffix). Format: `arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:beconversive-confession/app-XXXXXX:ADMIN_PASSWORD::`

Then register:

```bash
aws ecs register-task-definition --cli-input-json file://docs/ecs-task-definition.example.json --region us-east-1
```

### 6c. ALB, target group, security groups

1. **Application Load Balancer**:
   - Scheme: internet-facing.
   - Listeners: HTTPS 443 (attach ACM certificate); optional HTTP 80 → redirect to 443.
   - Create a **target group**: type IP (for Fargate), protocol HTTP, port 8000, VPC and subnets same as ECS. Health check path `/api/health`.

2. **Security groups**:
   - **ALB**: Inbound 443 (and 80 if redirect) from 0.0.0.0/0; outbound to ECS task SG on 8000.
   - **ECS tasks**: Inbound 8000 from ALB SG only; outbound 0.0.0.0/0 (for SQS, Secrets Manager, EFS).

3. **ECS service**:
   - Cluster: `beconversive`
   - Task definition: `beconversive-confession` (latest)
   - Desired count: 1 (or 2 for HA; then use RDS instead of SQLite if you need a shared DB)
   - Launch type: Fargate
   - VPC and subnets: private subnets (with NAT so tasks can reach ECR, SQS, EFS)
   - Security group: ECS task SG above
   - Load balancer: add to the ALB listener, target group created above, container name :8000
   - **Public IP**: DISABLED (tasks in private subnets)

4. Set **PUBLIC_BASE_URL** in the task definition to the ALB URL:  
   `https://<alb-dns-name>` or `https://confession.yourdomain.com` if you add a CNAME and attach the cert to the ALB listener.

### 6d. (Optional) Custom domain and ACM

1. Request or import an ACM certificate for `confession.yourdomain.com` (in us-east-1 if using CloudFront/ALB).
2. Add a CNAME (or alias) in Route 53 (or your DNS) pointing `confession.yourdomain.com` to the ALB.
3. Attach the certificate to the ALB HTTPS listener and set `PUBLIC_BASE_URL=https://confession.yourdomain.com`.

---

## Step 7: Lambda (SQS → Instagram)

1. **Package and create the function** as in `lambda/README.md` (zip `instagram_post_handler.py`, upload to Lambda).
2. **Handler**: `instagram_post_handler.lambda_handler`.
3. **Runtime**: Python 3.11 (or 3.12).
4. **Environment variables**: `INSTAGRAM_USER_ID`, `INSTAGRAM_ACCESS_TOKEN` (long-lived token).
5. **Trigger**: SQS – select the queue `confession-approval-queue`, batch size 1–5.
6. **Timeout**: 30 seconds; memory 128 MB.
7. **IAM**: Use the Lambda execution role from Step 4c (SQS permissions).

Lambda does not need VPC access to call the Instagram API. The message body must be:

```json
{ "image_url": "https://...", "caption": "..." }
```

The ECS app builds `image_url` from `PUBLIC_BASE_URL` + `/generated_images/<filename>.png`, so Lambda and Instagram can fetch the image from the ALB.

---

## Step 8: One-time setup – EFS and DB

- **SQLite**: The app creates `confessions.db` on first request (init_db) at `DATABASE_URL` → `/app/data/confessions.db`. EFS `/data` is mounted there, so the file is created on EFS automatically.
- **Backgrounds**: Already in the image; no EFS copy needed.
- **generated_images**: Empty on first deploy; the app will create files here when users submit confessions.

No manual copy of backgrounds is required.

---

## Step 9: Post-deploy checks

1. **App**: Open `https://<PUBLIC_BASE_URL>/` – confession form loads.
2. **Submit**: Post a test confession; it should save and show success (status PENDING).
3. **Admin**: Open `https://<PUBLIC_BASE_URL>/admin`, log in with `ADMIN_PASSWORD`, see the pending confession.
4. **Image URL**: In admin, the thumbnail uses `/generated_images/<name>.png`. Open that full URL in a browser – image should load (confirms Lambda/Instagram can fetch it).
5. **Approve**: Click Approve; confession moves to “Queued”. In SQS, message count should decrease; in Lambda logs (CloudWatch), you should see a successful Instagram post.

---

## Summary checklist

| # | Item | Action |
|---|------|--------|
| 1 | ECR | Create repo, build image, push |
| 2 | EFS | Create EFS, mount targets, access points for `/generated_images` and `/data` |
| 3 | SQS | Create queue, note URL |
| 4 | IAM | ECS task execution role; ECS task role (SQS SendMessage); Lambda role (SQS) |
| 5 | Secrets | Store ADMIN_PASSWORD, SECRET_KEY; reference in task def |
| 6 | ECS | Task def with EFS mounts, env PUBLIC_BASE_URL, SQS_QUEUE_URL, DATABASE_URL, secrets |
| 7 | ALB | Create ALB, HTTPS listener (ACM), target group → ECS service |
| 8 | ECS service | Fargate, 1 task, private subnets, load balancer, security groups |
| 9 | Lambda | Deploy per lambda/README.md, SQS trigger, Instagram env vars |
| 10 | DNS (optional) | CNAME to ALB, PUBLIC_BASE_URL = custom domain |

---

## Cost (rough, us-east-1)

- **Fargate**: ~$15–20/month (1 task, 0.5 vCPU, 1 GB, 24/7).
- **ALB**: ~$16–20/month.
- **EFS**: ~$0.30/GB/month + low request cost.
- **SQS + Lambda**: Negligible at low volume.
- **Data transfer**: Depends on traffic.

Total for a single task + ALB + EFS is typically **~$35–45/month** before data transfer.

---

## Scaling and HA

- **Multiple ECS tasks**: Use **RDS (PostgreSQL)** instead of SQLite so all tasks share one DB. Set `DATABASE_URL=postgresql://...` and do not mount the `data` EFS volume for the DB; keep EFS only for `generated_images`.
- **Lambda**: Already scales with SQS message count.
- Consider **WAF** in front of the ALB and **rate limiting** (you already have app-level rate limiting).

If you want, the next step can be concrete `task-definition.json` and `task-definition.json` snippets tailored to your account ID, region, and EFS/queue ARNs.
