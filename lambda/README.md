# Lambda: Post to Instagram (SQS-triggered)

This Lambda is invoked when your admin approves a confession and a message is sent to SQS. It posts the approved image to Instagram using the Graph API.

## SQS message format

Each message **body** must be JSON:

```json
{
  "image_url": "https://your-public-domain.com/generated_images/confession_20260207_123456_789012.png",
  "caption": "Anonymous confession 💭\n\n#confession #anonymous #beyourself ..."
}
```

- **`image_url`** (required): Public URL of the image. Instagram’s servers will fetch it; it must be reachable from the internet (e.g. your app’s public URL or S3/CloudFront).
- **`caption`** (optional): Caption for the post (can be empty string).

## Environment variables (Lambda configuration)

| Variable | Description |
|----------|-------------|
| `INSTAGRAM_USER_ID` | Instagram Business Account ID (e.g. `17841480395488283`) |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Instagram Graph API access token |

Set these in the Lambda console: **Configuration → Environment variables**.

## Deployment (copy-paste deploy)

### 1. Zip the handler

From the project root:

```bash
cd lambda
zip -r ../instagram_post_lambda.zip instagram_post_handler.py
cd ..
```

Or from anywhere:

```bash
zip instagram_post_lambda.zip instagram_post_handler.py
```

### 2. Create the Lambda (AWS Console)

1. **Lambda** → Create function → Author from scratch.
2. **Function name:** e.g. `confession-instagram-post`.
3. **Runtime:** Python 3.11 (or 3.12).
4. **Create function.**

### 3. Upload code

1. In the function, **Code** tab → **Upload from** → **.zip file**.
2. Select `instagram_post_lambda.zip`.
3. **Handler:** leave as `lambda_function.lambda_handler` **or** set to `instagram_post_handler.lambda_handler` (must match the file name and the function name inside the file).
4. If your zip has the file at root, set **Handler** to `instagram_post_handler.lambda_handler`.

### 4. Set environment variables

**Configuration** → **Environment variables** → Edit:

- `INSTAGRAM_USER_ID` = your Instagram user ID  
- `INSTAGRAM_ACCESS_TOKEN` = your long-lived token  

### 5. Add SQS trigger

1. **Configuration** → **Triggers** → **Add trigger**.
2. **Source:** SQS.
3. **SQS queue:** select the queue where your app sends approval messages.
4. **Batch size:** 1–10 (e.g. 5).
5. Save.

### 6. Timeout and memory

- **Timeout:** 30 seconds (Instagram create + 2s wait + publish).
- **Memory:** 128 MB is enough (no heavy deps).

## Flow summary

1. User submits confession → app creates image and stores it (e.g. DB + file).
2. Admin sees pending items in admin UI and approves one.
3. Backend sends one SQS message per approval: body = `{"image_url": "<public url>", "caption": "..."}`.
4. Lambda is triggered by SQS, runs `instagram_post_handler.lambda_handler`.
5. Lambda reads `image_url` and `caption`, calls Instagram create media → wait 2s → publish.
6. Failed messages appear in `batchItemFailures`; SQS will retry according to the queue’s redrive policy.

## Handler name

- File name: `instagram_post_handler.py`
- Function name inside file: `lambda_handler`
- So in Lambda **Handler** use: **`instagram_post_handler.lambda_handler`**

No external dependencies (uses only Python stdlib).
