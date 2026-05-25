# QW-2 Callback Handler Skill

Handles Telegram inline button callbacks and text replies for QW-2 pending decisions workflow.

## Trigger

When a Telegram message from Lincoln (7426291192) contains:
- callback_data starting with `qw2_` (qw2_confirm, qw2_cancel, qw2_approve, qw2_reject)
- Text matching: `approve`, `reject`, `/qw2approve`, `/qw2reject`

## Flow

### Via button callback (qw2_approve / qw2_reject)
Buttons are sent with the pending decisions DM. When Lincoln taps a button, the callback data is sent to the bot.

### Via text reply
1. DM sent to Lincoln listing pending decisions
2. Lincoln replies with "approve" or "reject"
3. This agent session receives the message and processes the command

## Processing

```
if "approve" in text.lower():
    → confirm_pending() → write decisions → consolidate → update MEMORY.md
    → Send confirmation DM to Lincoln
    
if "reject" in text.lower():
    → cancel_pending() → archive pending files
    → Send cancellation DM to Lincoln
```

## Implementation

```python
# In agent's message handler:
from vault.qw2.callback_handler import process_callback, confirm_pending, cancel_pending

def handle_message(text):
    text = text.strip().lower()
    if text in ("approve", "aprovar", "sim", "yes", "/qw2approve"):
        result = confirm_pending()
        send_confirmation_dm(result)
    elif text in ("reject", "rejeitar", "nao", "no", "/qw2reject"):
        result = cancel_pending()
        send_cancellation_dm(result)
```

## DM Poller (backup)

When direct message handling isn't available, a polling mechanism checks for commands:

```bash
# Cron: qw2-dm-poller (every 15 min during work hours)
cd /home/lincoln/.openclaw/workspace-livy-memory
PYTHONPATH=. TELEGRAM_MEMORY_BOT_TOKEN=<token> python3 vault/qw2/dm_poller.py --poll
```

The poller uses getUpdates API to find messages from Lincoln containing approve/reject commands.
