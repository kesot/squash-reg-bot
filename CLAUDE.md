commit and push changes as you are doing them

# Project

Telegram poll auto-voter userbot (Telethon). Monitors a specific chat/topic for polls from a specific author and votes for the first option. Sends a scheduled reminder to Saved Messages after voting.

## Stack

- Python 3.12, Telethon
- Docker + docker-compose
- uv for dependency management

## Key files

- `bot.py` — main bot logic
- `env.example` — env var template (copy to `.env`)
- `Dockerfile`, `docker-compose.yml` — container setup

## Config (env vars)

- `API_ID`, `API_HASH` — from my.telegram.org
- `CHAT_ID` — target chat (e.g. `-1001880589294`)
- `TOPIC_ID` — forum topic id (optional)
- `POLL_AUTHOR_ID` — hardcoded in bot.py (`108966186`)

## Deployment

First time (interactive login required):
```
cp env.example .env   # fill in API_ID, API_HASH
docker compose run --rm bot   # enter phone + code
# after "Listening for polls..." appears, Ctrl+C
docker compose up -d
```

Subsequent deploys (session persists in docker volume):
```
docker compose up -d --build
```

Logs are mounted at `./logs/bot.log` on the host.