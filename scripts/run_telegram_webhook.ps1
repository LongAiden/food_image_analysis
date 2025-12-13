$ErrorActionPreference = "Stop"

# Requirements:
# - uvicorn available in your Python environment
# - ngrok installed and on PATH
# - TELEGRAM_BOT_TOKEN set in your environment or .env
# - Backend runs on port 8000 (change $Port if needed)

$Port = 8000

# Resolve TELEGRAM_BOT_TOKEN from environment
function Get-TelegramToken {
    if ($env:TELEGRAM_BOT_TOKEN) { return $env:TELEGRAM_BOT_TOKEN }
    # Try to read from .env (simple parse)
    $envPath = Join-Path -Path (Get-Location) -ChildPath ".env"
    if (Test-Path $envPath) {
        $line = Get-Content $envPath | Where-Object { $_ -match "^\s*TELEGRAM_BOT_TOKEN\s*=" } | Select-Object -First 1
        if ($line) {
            return ($line -split "=",2)[1].Trim().Trim("'`"")
        }
    }
    throw "TELEGRAM_BOT_TOKEN not found in environment or .env"
}

$token = Get-TelegramToken

Write-Host "Starting uvicorn on port $Port..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn main:app --host 0.0.0.0 --port $Port"
Start-Sleep -Seconds 2

Write-Host "Starting ngrok tunnel on port $Port..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http $Port"
Start-Sleep -Seconds 4

# Fetch the public HTTPS URL from ngrok API (runs on 4040)
try {
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels"
    $publicUrl = ($tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1).public_url
    if (-not $publicUrl) { throw "No https tunnel found from ngrok" }
    Write-Host "ngrok public URL: $publicUrl"

    $webhookUrl = "$publicUrl/telegram/webhook"
    Write-Host "Setting Telegram webhook to $webhookUrl"

    $setWebhookUri = "https://api.telegram.org/bot$token/setWebhook"
    $resp = Invoke-RestMethod -Uri $setWebhookUri -Method Post -Body @{ url = $webhookUrl }
    Write-Host "setWebhook response: $($resp | ConvertTo-Json -Depth 3)"

    $info = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getWebhookInfo"
    Write-Host "Webhook info: $($info | ConvertTo-Json -Depth 3)"
} catch {
    Write-Warning "Failed to set webhook: $_"
    Write-Warning "Ensure ngrok is running and TELEGRAM_BOT_TOKEN is correct."
}

Write-Host "Ready. Send a photo to the bot and watch the uvicorn console for logs."
