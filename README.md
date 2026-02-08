# BeConversive Confession 💭

A production-ready anonymous confession portal that generates aesthetic images and automatically posts them to Instagram.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- **Anonymous Submissions**: No user data collected or stored
- **Aesthetic Image Generation**: Auto-generates 1080x1080 images with gradient backgrounds
- **Instagram Integration**: Automatically posts to Instagram via Graph API
- **Content Moderation**: Built-in profanity filter and spam detection
- **Rate Limiting**: Prevents abuse (10 submissions per hour per IP)
- **Modern UI**: Beautiful dark theme with glassmorphism effects
- **Docker Ready**: Easy deployment with Docker Compose

## 🏗️ Architecture

```
Backend: FastAPI (Python)
Database: SQLite (PostgreSQL ready)
Image Processing: Pillow
Instagram API: Graph API v24.0 (latest)
Frontend: HTML/CSS/JavaScript
Deployment: Docker
```

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- Instagram Professional/Business Account
- Facebook Developer App with Instagram Graph API access

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd /home/hrash-raj/test/confession
cp .env.example .env
```

### 2. Configure Instagram API

Edit `.env` file with your credentials:

```env
INSTAGRAM_USER_ID=your_instagram_user_id
INSTAGRAM_ACCESS_TOKEN=your_access_token
```

**How to get Instagram credentials (Updated for Graph API v24.0):**

The application uses **Instagram Graph API v24.0** (latest stable version as of 2026).

#### Authentication Methods

There are two ways to authenticate with Instagram Graph API:

1. **Facebook Login for Business** (Recommended - Default)
   - Uses `graph.facebook.com` host
   - Instagram account must be linked to a Facebook Page
   - Better for managing multiple accounts
   - Supports Facebook Business Manager integration

2. **Business Login for Instagram**
   - Uses `graph.instagram.com` host
   - Direct Instagram authentication
   - Suitable for single account management
   - To use this method, uncomment the alternative instance in `instagram_api.py`

#### Setup Steps (Facebook Login for Business):

1. **Create Facebook App**
   - Go to [Meta for Developers](https://developers.facebook.com/)
   - Create a new app → Choose "Business" type
   - Add "Instagram Graph API" product to your app

2. **Link Instagram Account**
   - Ensure your Instagram account is a Professional account (Business or Creator)
   - Link it to a Facebook Page
   - Go to Instagram Settings → Account → Linked Accounts → Facebook

3. **Get Instagram User ID**
   - In Graph API Explorer (https://developers.facebook.com/tools/explorer/)
   - Select your app from the dropdown
   - Make a GET request to: `me/accounts`
   - Find your Facebook Page, then request: `{page-id}?fields=instagram_business_account`
   - The `instagram_business_account.id` is your `INSTAGRAM_USER_ID`

4. **Generate Access Token**
   - In Graph API Explorer, generate a User Access Token
   - Required permissions: 
     - `instagram_basic`
     - `instagram_content_publish`
     - `pages_read_engagement`
     - `pages_show_list`
   
5. **Exchange for Long-Lived Token** (60 days validity)
   ```bash
   curl -X GET "https://graph.facebook.com/v24.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
   ```
   
   The response will contain your long-lived access token.

6. **Update .env file**
   ```env
   INSTAGRAM_USER_ID=17841... (your IG User ID)
   INSTAGRAM_ACCESS_TOKEN=EAAxxxxx... (your long-lived token)
   ```

> [!IMPORTANT]
> **Access Token Expiration**: Long-lived tokens expire after 60 days. You'll need to refresh them periodically. Consider implementing automatic token refresh for production use.

> [!NOTE]
> **Image URL Requirements**: Instagram API requires images to be hosted on publicly accessible URLs. You can test from local using **ngrok** (see below) or use S3/CDN in production.

#### Testing Instagram locally with a tunnel

Instagram must fetch your image from a **public URL**. Two options:

**Option A: Cloudflare Tunnel (recommended for free)**

Ngrok’s free tier shows an HTML “browser warning” page to non-browser requests. Instagram’s servers don’t send browser headers, so they get that HTML instead of your image and the API returns “Only photo or video can be accepted.” **Cloudflare Tunnel does not do this**, so it works for Instagram.

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) and run:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
2. Copy the `https://*.trycloudflare.com` URL and set in `.env`:
   ```env
   PUBLIC_BASE_URL=https://your-random-subdomain.trycloudflare.com
   ```
3. Restart the app and use that URL in your browser to submit confessions.
4. **If Instagram still returns "Only photo or video"** (e.g. "context canceled" in cloudflared): Instagram may timeout when fetching through the tunnel. **Easiest fix:** set **ImgBB** so images are uploaded to a CDN first. Get a free API key at [api.imgbb.com](https://api.imgbb.com/), add `IMGBB_API_KEY=your_key` to `.env`, and restart. The app will upload each image to ImgBB and send that URL to Instagram (no tunnel involved).

**Option B: Ngrok (paid, or with warning disabled)**

1. Run the app and expose it: `ngrok http 8000`
2. Copy the HTTPS URL and set `PUBLIC_BASE_URL` in `.env`.
3. On **ngrok free tier**, Instagram will still get the warning page unless you disable the browser warning in the ngrok dashboard (if available) or use a paid plan.

### 3. Run with Docker (Recommended)

```bash
docker-compose up --build
```

Visit: `http://localhost:8000`

### 4. Run Locally (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 Project Structure

```
confession/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── database.py          # Database setup
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── routes/
│   │   └── confession.py    # API endpoints
│   ├── services/
│   │   ├── image_generator.py    # Image creation
│   │   ├── caption_generator.py  # Caption creation
│   │   ├── instagram_api.py      # Instagram posting
│   │   └── moderation.py         # Content filtering
│   ├── static/              # CSS, JS, fonts
│   └── templates/           # HTML templates
├── generated_images/        # Generated confession images
├── backgrounds/             # Gradient backgrounds
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🎨 How It Works

1. **User submits confession** → Anonymous text input
2. **Content moderation** → Profanity filter + spam detection
3. **Image generation** → Creates 1080x1080 aesthetic image with text
4. **Caption creation** → Auto-generates Instagram caption with hashtags
5. **Instagram posting** → Posts via Graph API (two-step: upload → publish)
6. **Database storage** → Saves confession with post status

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///./confessions.db` |
| `INSTAGRAM_USER_ID` | Instagram Business Account ID | Required for posting |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram API access token | Required for posting |
| `PUBLIC_BASE_URL` | Public URL for image links (e.g. ngrok/Cloudflare tunnel URL) | Inferred from request |
| `IMGBB_API_KEY` | Optional: upload images to ImgBB and use CDN URL for Instagram (avoids tunnel timeouts) | None |
| `MAX_CONFESSION_LENGTH` | Maximum characters allowed | `500` |
| `RATE_LIMIT_PER_HOUR` | Submissions per IP per hour | `10` |
| `SECRET_KEY` | Application secret key | Change in production |

### Database Options

**SQLite (Default):**
```env
DATABASE_URL=sqlite:///./confessions.db
```

**PostgreSQL:**
```env
DATABASE_URL=postgresql://user:password@localhost/confession_db
```

Uncomment PostgreSQL service in `docker-compose.yml` for production use.

## 📡 API Endpoints

### POST `/api/submit`
Submit a new confession

**Request:**
```json
{
  "text": "Your confession here..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Confession submitted successfully!",
  "confession_id": 1
}
```

### GET `/api/health`
Health check endpoint

## 🎨 Image Generation

- **Size**: 1080x1080 pixels (Instagram optimized)
- **Backgrounds**: 6 aesthetic gradient variations
- **Fonts**: Elegant serif fonts with auto-scaling
- **Layout**: Centered card with semi-transparent overlay
- **Text**: Auto-wrapped with proper spacing

## 🔒 Security Features

- **Anonymous**: No user identity stored (only hashed IP for rate limiting)
- **Content Moderation**: Profanity filtering via `better-profanity`
- **Rate Limiting**: 10 submissions per hour per IP
- **Input Validation**: Max length and spam detection
- **CORS**: Configurable allowed origins

## 🧪 Testing

### Test Image Generation
```bash
python -c "from app.services.image_generator import image_generator; print(image_generator.generate_image('Test confession!'))"
```

### Test API
```bash
curl -X POST http://localhost:8000/api/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test confession!"}'
```

### Check Generated Images
```bash
ls -lh generated_images/
```

## 🚢 Deployment

### Docker Production

1. Update `.env` with production credentials
2. Build and run:
```bash
docker-compose up -d
```

### Manual Deployment

1. Install dependencies on server
2. Set environment variables
3. Use a process manager (systemd, supervisor)
4. Configure reverse proxy (nginx, caddy)

**Example systemd service:**
```ini
[Unit]
Description=BeConversive Confession
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/confession
Environment="PATH=/var/www/confession/venv/bin"
ExecStart=/var/www/confession/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🐛 Troubleshooting

### Instagram API Errors

**"Invalid access token"**
- Token expired → Generate new long-lived token
- Wrong permissions → Ensure `instagram_content_publish` is granted

**"Image URL not accessible" / "Only photo or video can be accepted"**
- Instagram's servers must be able to fetch the image URL (localhost does not work).
- **Ngrok free tier:** Ngrok returns an HTML warning page to non-browser requests. Use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) and `PUBLIC_BASE_URL`, or use ngrok paid.
- **Tunnel timeouts ("context canceled"):** Instagram may close the connection before the image is delivered. **Fix:** Use **ImgBB**: get a free key at [api.imgbb.com](https://api.imgbb.com/), set `IMGBB_API_KEY=your_key` in `.env`. The app will upload images to ImgBB and send that CDN URL to Instagram.
- **Production:** Host images on a public URL (your domain, S3, CDN) or use ImgBB.

### Image Generation Issues

**"Font not found"**
- Install fonts: `apt-get install fonts-dejavu-core fonts-liberation`
- Check font paths in `image_generator.py`

### Rate Limit

**"Rate limit exceeded"**
- Wait 1 hour or adjust `RATE_LIMIT_PER_HOUR` in `.env`
- Clear old submissions from database

## 📝 License

MIT License - feel free to use for your own projects!

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR.

## 📧 Support

For issues or questions, please open a GitHub issue.

---

**Built with ❤️ using FastAPI, Pillow, and Instagram Graph API**
