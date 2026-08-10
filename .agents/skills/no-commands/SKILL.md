---
name: no-commands
description: Enforces conversational-only Telegram UX. Load for any change touching app/bot.py or user-facing response text.
---
Atlas AI never uses slash commands, inline keyboards, buttons, or quick-reply
menus. All intent is inferred from natural language (text, voice, or image).
If a feature seems to need a command or button, redesign it as something the
user can ask for in plain conversation instead.
