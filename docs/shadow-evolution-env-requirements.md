# Shadow Evolution Pipeline — Environment Requirements

This document describes the environment variables required to operate the Shadow Evolution Pipeline V2.

## Required Variables

### CONTEXT7_API_KEY

- **Purpose:** Authenticate requests to Context7 API for fact-checking signals against official documentation.
- **Required for:** `skills/memoria-consolidation/fact_checker.py`
- **Obtain from:** https://context7.com/api
- **Example:**
  ```bash
  export CONTEXT7_API_KEY=ctx7_live_xxxxxxxxxxxxxxxxxxxxxxxx
  ```

### MATTERMOST_WEBHOOK_URL

- **Purpose:** Route triage decisions to the Mattermost team channel for human review.
- **Required for:** `skills/memoria-consolidation/triage_bridge.py`
- **Obtain from:** Mattermost integration settings → Incoming Webhooks
- **Example:**
  ```bash
  export MATTERMOST_WEBHOOK_URL=https://mattermost.example.com/hooks/abc123xyz
  ```
- **Note:** If not set, triage bridge will log to console only (no routing occurs).

### TELEGRAM_BOT_TOKEN

- **Purpose:** Telegram bot token for receiving human override callbacks (hold/promote commands).
- **Required for:** `skills/memoria-consolidation/telegram_override_handler.py`
- **Obtain from:** Telegram @BotFather → /newbot → copy token
- **Example:**
  ```bash
  export TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
  ```

### TELEGRAM_CHAT_ID

- **Purpose:** Target Telegram chat (user or channel) for pipeline summary notifications.
- **Required for:** Telegram notification dispatch
- **Example:**
  ```bash
  export TELEGRAM_CHAT_ID=-1001234567890
  ```

## Operational Variables

### RECONCILIATION_WRITE_MODE

- **Default:** `0` (shadow mode, safe)
- **Values:**
  - `0` — Shadow mode: evaluate only, no writes
  - `1` — Write mode: promote decisions that pass all gates
- **Example:**
  ```bash
  export RECONCILIATION_WRITE_MODE=0  # Shadow (default, safe)
  export RECONCILIATION_WRITE_MODE=1  # Write (production promotion)
  ```

### RECONCILIATION_SHADOW_EVOLUTION_ENABLED

- **Default:** `1` (enabled)
- **Values:** `0` to disable the full shadow evolution pipeline.
- **Example:**
  ```bash
  export RECONCILIATION_SHADOW_EVOLUTION_ENABLED=1
  ```

## Wrapper Script

All variables are sourced automatically by the wrapper script:

```bash
bash skills/memoria-consolidation/curation_cron_wrapper.sh
```

Ensure these are set in your shell profile, `.env` file, or CI/CD secret manager before running the pipeline.

## Validation

To verify the environment is correctly configured:

```bash
# Check Context7 connectivity
curl -s -H "Authorization: Bearer $CONTEXT7_API_KEY" https://api.context7.com/v1/health

# Verify Mattermost webhook (expect HTTP 200)
curl -s -o /dev/null -w "%{http_code}" -X POST "$MATTERMOST_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"text":"Shadow Evolution Pipeline — webhook test"}'

# Check Telegram bot info
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"
```

## Troubleshooting Missing Variables

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Fact-check skipped for all signals | `CONTEXT7_API_KEY` not set | Set API key |
| No triage messages in Mattermost | `MATTERMOST_WEBHOOK_URL` not set | Configure webhook URL |
| Override commands not processed | `TELEGRAM_BOT_TOKEN` not set | Create bot via @BotFather |
| Summary notifications not delivered | `TELEGRAM_CHAT_ID` not set | Identify target chat ID |
