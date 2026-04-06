"""
AWS Lambda: Post approved confession image to Instagram (triggered by SQS).

Expects SQS message body (JSON):
  {
    "image_url": "https://your-public-url/path/to/image.png",
    "caption": "Caption text with hashtags..."
  }

Environment variables (set in Lambda config):
  INSTAGRAM_USER_ID   - Instagram Business Account ID
  INSTAGRAM_ACCESS_TOKEN - Long-lived access token

SQS trigger: Lambda is invoked when messages arrive in the queue.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INSTAGRAM_API_VERSION = "v24.0"
BASE_URL = f"https://graph.instagram.com/{INSTAGRAM_API_VERSION}"


def _get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise ValueError(f"Missing environment variable: {name}")
    return val.strip()


def _http_post_json(url: str, data: dict, headers: dict) -> dict:
    """POST JSON body and return parsed JSON response."""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _http_post_params(url: str, params: dict) -> dict:
    """POST with query params (no body) and return parsed JSON response."""
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    full_url = f"{url}?{qs}" if qs else url
    req = urllib.request.Request(full_url, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def post_to_instagram(image_url: str, caption: str) -> dict:
    """
    Step 1: Create media container.
    Step 2: Wait 2s then publish container.
    Returns dict with container_id and media_id on success.
    """
    user_id = _get_env("INSTAGRAM_USER_ID")
    access_token = _get_env("INSTAGRAM_ACCESS_TOKEN")

    # Step 1: Create media container
    create_url = f"{BASE_URL}/{user_id}/media"
    create_body = {
        "image_url": image_url,
        "media_type": "IMAGE",
        "caption": caption,
    }
    create_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        create_resp = _http_post_json(create_url, create_body, create_headers)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"Instagram create media failed: {e.code} {err_body}")
    except Exception as e:
        raise RuntimeError(f"Instagram create media request failed: {e}") from e

    container_id = create_resp.get("id")
    if not container_id:
        raise RuntimeError(f"No container ID in response: {create_resp}")

    time.sleep(2)

    # Step 2: Publish media
    publish_url = f"{BASE_URL}/{user_id}/media_publish"
    publish_params = {
        "creation_id": container_id,
        "access_token": access_token,
    }

    try:
        publish_resp = _http_post_params(publish_url, publish_params)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"Instagram publish failed: {e.code} {err_body}")
    except Exception as e:
        raise RuntimeError(f"Instagram publish request failed: {e}") from e

    media_id = publish_resp.get("id")
    if not media_id:
        raise RuntimeError(f"No media ID in response: {publish_resp}")

    return {"container_id": container_id, "media_id": media_id}


def lambda_handler(event, context):
    """
    SQS trigger: event["Records"] is a list of SQS messages.
    Each record["body"] should be JSON: { "image_url": "...", "caption": "..." }.
    Returns batchItemFailures so failed messages can be retried by SQS.
    """
    failed_message_ids = []

    for record in event.get("Records", []):
        message_id = record.get("messageId", "")
        body_str = record.get("body", "{}")

        try:
            body = json.loads(body_str)
            image_url = body.get("image_url")
            caption = body.get("caption") or ""

            if not image_url:
                raise ValueError("Missing image_url in message body")

            result = post_to_instagram(image_url, caption)
            logger.info("Posted to Instagram: %s", result)
        except Exception as e:
            logger.exception("Failed to process message %s: %s", message_id, e)
            failed_message_ids.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failed_message_ids}
