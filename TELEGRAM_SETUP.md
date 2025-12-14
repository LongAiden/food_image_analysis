# 🤖 Telegram Bot Integration Guide

## Overview

This application integrates with Telegram to allow users to analyze food images directly through a Telegram bot. Users send photos to the bot, and it responds with nutritional analysis.

---

## 📋 Table of Contents

1. [How It Works](#how-it-works)
2. [Webhook vs Long Polling](#webhook-vs-long-polling)
3. [Configuration Options](#configuration-options)
4. [Local Development Setup](#local-development-setup)
5. [Production Deployment](#production-deployment)
6. [Troubleshooting](#troubleshooting)

---

## 🔄 How It Works

### User Flow

```
User sends photo to Telegram bot
           ↓
Telegram sends update to your app (via webhook OR polling)
           ↓
App receives update → process_telegram_update()
           ↓
Extract photo file_id from update
           ↓
Download photo from Telegram servers → fetch_telegram_file()
           ↓
Send "Analyzing image..." message to user
           ↓
Prepare and resize image → prepare_image()
           ↓
Analyze with Gemini AI → analyzer.analyze_image()
           ↓
Upload to Supabase Storage → storage.upload_image()
           ↓
Save to Database → database.save_analysis()
           ↓
Send nutrition results back to user
```

### Code Flow

**Location:** `main.py`

1. **Entry Points:**
   - **Webhook:** `/telegram/webhook` endpoint (line 482)
   - **Long Polling:** `telegram_long_poll()` function (line 282)

2. **Update Processing:** `process_telegram_update()` (line 195)
   - Validates message has photo
   - Extracts chat_id and file_id
   - Downloads file from Telegram
   - Processes and analyzes image
   - Stores results
   - Sends response

3. **File Download:** `fetch_telegram_file()` (line 147)
   - Gets file metadata from Telegram API
   - Downloads actual file content
   - Returns bytes and filename

4. **Message Sending:** `send_telegram_message()` (line 191)
   - Sends text responses back to user
   - Includes error handling

---

## 🔀 Webhook vs Long Polling

Your app supports **two modes** for receiving Telegram updates:

### **Webhook Mode** (Production)

**How it works:**
- Telegram sends updates directly to your server via HTTPS POST requests
- Real-time, instant delivery
- More efficient (no constant polling)

**Requirements:**
- ✅ Publicly accessible server with HTTPS
- ✅ Valid domain or public IP
- ✅ `TELEGRAM_WEBHOOK_URL` configured

**When to use:**
- Production deployments
- When your server is publicly accessible

**Code:** Lines 83-92 in `main.py` (automatically sets webhook on startup)

---

### **Long Polling Mode** (Development)

**How it works:**
- Your app continuously asks Telegram: "Any new updates?"
- Telegram responds with new messages (if any)
- Loop repeats every ~25 seconds

**Requirements:**
- ✅ Just a Telegram bot token
- ✅ No public URL needed
- ✅ `TELEGRAM_WEBHOOK_URL` must be empty/unset

**When to use:**
- Local development
- Testing on your laptop
- No public server available

**Code:** Lines 282-316 in `main.py` (`telegram_long_poll` function)

---

## ⚙️ Configuration Options

### Option 1: Long Polling (Recommended for Local Dev)

**`.env` configuration:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
# TELEGRAM_WEBHOOK_URL=  # Leave commented out or empty

ENABLE_NGROK=false
```

**Pros:**
- ✅ Works locally without any tunnels
- ✅ No HTTPS certificate needed
- ✅ Simple setup

**Cons:**
- ❌ Slight delay (up to 25 seconds)
- ❌ Keeps connection open to Telegram

---

### Option 2: ngrok Tunnel (Quick Public Access)

**`.env` configuration:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
# TELEGRAM_WEBHOOK_URL=  # Leave empty, will auto-fill
ENABLE_NGROK=true
NGROK_PORT=8000
```

**Steps:**
1. Install ngrok: `brew install ngrok` (macOS) or download from https://ngrok.com
2. Set `ENABLE_NGROK=true` in `.env`
3. Run your app - it will:
   - Start ngrok automatically
   - Get public HTTPS URL
   - Set Telegram webhook
   - Log the public URL

**Pros:**
- ✅ Instant delivery (real webhook)
- ✅ No manual ngrok setup
- ✅ Works for local testing

**Cons:**
- ❌ Requires ngrok installed
- ❌ URL changes each restart (unless you have ngrok pro)

**Code:** Lines 51-81 in `main.py`

---

### Option 3: Production Webhook

**`.env` configuration:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
ENABLE_NGROK=false
```

**Steps:**
1. Deploy your app to a public server (Railway, Render, Fly.io, etc.)
2. Get your public HTTPS URL
3. Set `TELEGRAM_WEBHOOK_URL` to `https://your-domain.com/telegram/webhook`
4. Run app - webhook will be set automatically

**Pros:**
- ✅ Instant, reliable delivery
- ✅ Scalable for production
- ✅ Professional setup

**Cons:**
- ❌ Requires deployment
- ❌ Must have HTTPS (not HTTP)

---

## 🛠️ Local Development Setup

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow prompts to choose name and username
4. **Copy the bot token** (looks like `123456:ABC-DEF1234...`)
5. Paste it in `.env` as `TELEGRAM_BOT_TOKEN`

### Step 2: Configure Environment

Edit `.env`:
```bash
# Supabase Configuration
SUPABASE_PROJECT_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here  # NOT anon key!
SUPABASE_BUCKETS=food-images
SUPABASE_TABLE=food_analyses

# Gemini AI Configuration
GOOGLE_API_KEY=your_gemini_api_key_here

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
# TELEGRAM_WEBHOOK_URL=  # Commented for long polling

ENABLE_NGROK=false
```

### Step 3: Clear Any Existing Webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
```

### Step 4: Run the App

```bash
cd food_image_analysis
python main.py
```

You should see:
```
Starting Telegram long polling (no webhook URL configured)
```

### Step 5: Test It

1. Open Telegram
2. Find your bot (search by username)
3. Send `/start`
4. Send a photo of food
5. Wait for analysis response

---

## 🚀 Production Deployment

### Deploy to Railway (Example)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Deploy to Railway**
   - Go to https://railway.app
   - Connect GitHub repo
   - Set environment variables in Railway dashboard
   - Railway will give you a public URL like `https://your-app.railway.app`

3. **Configure Webhook**

   In Railway environment variables:
   ```
   TELEGRAM_WEBHOOK_URL=https://your-app.railway.app/telegram/webhook
   ```

4. **Verify**
   ```bash
   curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo" | jq
   ```

   Should show:
   ```json
   {
     "ok": true,
     "result": {
       "url": "https://your-app.railway.app/telegram/webhook",
       "has_custom_certificate": false,
       "pending_update_count": 0
     }
   }
   ```

---

## 🐛 Troubleshooting

### Bot doesn't respond to messages

**Check 1: Is the app running?**
```bash
curl http://localhost:8000/health
```

**Check 2: What mode is it in?**
Look at startup logs:
- `Starting Telegram long polling` → Long polling mode ✅
- `Telegram webhook set` → Webhook mode ✅

**Check 3: Verify webhook status**
```bash
curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo" | python3 -m json.tool
```

If `"url": "https://your-public-host/telegram/webhook"` → **PROBLEM!** This is a fake URL.

**Fix:**
```bash
# Clear the fake webhook
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"

# Remove TELEGRAM_WEBHOOK_URL from .env (or comment it out)
# Restart app → will use long polling
```

**Check 4: Are there pending updates?**
```bash
curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo" | python3 -m json.tool
```

If `"pending_update_count": 5` → Messages are queued! Fix the webhook and restart.

---

### App crashes when receiving photo

**Check logs for:**
```
Failed to download Telegram file
```

**Common causes:**
- ❌ Invalid `TELEGRAM_BOT_TOKEN`
- ❌ Network timeout
- ❌ File too large

**Solution:** Check Logfire logs for detailed error messages.

---

### "Error creating bucket: [Scrubbed due to 'auth']"

**Problem:** You're using the `anon` key instead of `service_role` key.

**Solution:**
1. Go to Supabase Dashboard → Settings → API
2. Copy the `service_role` key (NOT the `anon` key)
3. Update `.env`:
   ```bash
   SUPABASE_SERVICE_KEY=eyJhbG... (service_role key)
   ```

---

### Database not updating

**Check 1: Verify table exists**
```sql
-- In Supabase SQL Editor
SELECT * FROM food_analyses LIMIT 1;
```

**Check 2: Check table name in .env**
```bash
SUPABASE_TABLE=food_analyses  # Must match your table name
```

**Check 3: Look for errors in Logfire**
Search for: `"Analysis error"` or `"Telegram processing error"`

---

## 📊 Monitoring

### View Logs in Logfire

1. Go to https://logfire.pydantic.dev
2. Search for:
   - `"Received Telegram update"` - Shows incoming messages
   - `"Processing Telegram photo"` - Shows photo processing
   - `"Analysis successful"` - Shows completed analyses
   - `"Telegram processing error"` - Shows errors

### Check Telegram Webhook Status

```bash
curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo" | python3 -m json.tool
```

Key fields:
- `"url"` - Where updates are sent (empty = polling mode)
- `"pending_update_count"` - Queued messages
- `"last_error_date"` - Last time webhook failed
- `"last_error_message"` - Why it failed

---

## 🔑 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | None | Bot token from @BotFather |
| `TELEGRAM_WEBHOOK_URL` | ❌ No | None | Public HTTPS URL for webhook (omit for polling) |
| `TELEGRAM_WEBHOOK_SECRET` | ❌ No | None | Optional secret to verify webhook requests |
| `ENABLE_NGROK` | ❌ No | `false` | Auto-start ngrok tunnel |
| `NGROK_PORT` | ❌ No | `8000` | Port for ngrok tunnel |
| `SUPABASE_PROJECT_URL` | ✅ Yes | None | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ Yes | None | Supabase **service_role** key |
| `SUPABASE_BUCKETS` | ✅ Yes | None | Storage bucket name |
| `SUPABASE_TABLE` | ✅ Yes | None | Database table name |
| `GOOGLE_API_KEY` | ✅ Yes | None | Gemini API key |
| `LOGFIRE_WRITE_TOKEN` | ❌ No | None | Logfire token for monitoring |

---

## 📚 API Endpoints

### Telegram Webhook
- **URL:** `POST /telegram/webhook`
- **Purpose:** Receives updates from Telegram
- **Called by:** Telegram servers (when webhook mode is enabled)

### Health Check
- **URL:** `GET /health`
- **Purpose:** Verify app is running
- **Response:** `{"status": "healthy", "service": "food-analysis-api"}`

### Manual Analysis (Direct Upload)
- **URL:** `POST /analyze`
- **Purpose:** Analyze food image via HTTP (not Telegram)
- **Body:** Multipart form with image file

---

## 🎯 Quick Reference Commands

```bash
# Check webhook status
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | python3 -m json.tool

# Delete webhook (switch to polling)
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Set webhook manually
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram/webhook"

# Get bot info
curl -s "https://api.telegram.org/bot<TOKEN>/getMe" | python3 -m json.tool

# Check if app is running
curl http://localhost:8000/health

# View app logs (if using uvicorn)
tail -f logs/app.log
```

---

## ✅ Best Practices

1. **Development:** Use long polling (no webhook)
2. **Production:** Use webhook with HTTPS
3. **Never** commit `.env` to git (add to `.gitignore`)
4. **Use service_role key** for Supabase (not anon key)
5. **Monitor logs** in Logfire for debugging
6. **Test locally first** before deploying

---

## 📞 Support

If you encounter issues:

1. Check the logs in Logfire
2. Verify environment variables are set correctly
3. Test the health endpoint: `curl http://localhost:8000/health`
4. Check Telegram webhook status
5. Look for error messages in the console

---

**Happy coding! 🎉**
