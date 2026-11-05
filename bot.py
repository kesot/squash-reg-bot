import os
import asyncio
import logging
from datetime import timedelta, datetime, timezone
from logging.handlers import RotatingFileHandler

from telethon import TelegramClient, events
from telethon.tl.functions.messages import SendVoteRequest

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            f"{LOG_DIR}/bot.log", maxBytes=5 * 1024 * 1024, backupCount=3
        ),
    ],
)
log = logging.getLogger(__name__)

logging.getLogger("telethon").setLevel(logging.WARNING)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
CHAT_ID = int(os.environ["CHAT_ID"])
TOPIC_IDS = (
    {int(t) for t in os.environ["TOPIC_ID"].split(",")}
    if os.environ.get("TOPIC_ID")
    else None
)
POLL_AUTHOR_IDS = (
    {int(a) for a in os.environ["POLL_AUTHOR_ID"].split(",")}
    if os.environ.get("POLL_AUTHOR_ID")
    else None
)

SESSION_PATH = "/app/data/bot"

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)


@client.on(events.NewMessage(chats=CHAT_ID))
async def handle_poll(event):
    log.debug("New message in chat %d, msg_id=%d", event.chat_id, event.message.id)

    if TOPIC_IDS is not None:
        reply_to = event.message.reply_to
        if not reply_to or getattr(reply_to, "forum_topic", False) is False:
            log.debug("Skipping — not in target topic")
            return
        thread_id = reply_to.reply_to_top_id or reply_to.reply_to_msg_id
        if thread_id not in TOPIC_IDS:
            log.debug("Skipping — topic %s not in %s", thread_id, TOPIC_IDS)
            return

    poll = event.message.poll
    if poll is None:
        log.debug("Skipping — not a poll")
        return

    author_id = getattr(event.message.from_id, "user_id", None)
    if POLL_AUTHOR_IDS is not None and author_id not in POLL_AUTHOR_IDS:
        log.info("Skipping poll — author %s not in %s", author_id, POLL_AUTHOR_IDS)
        return

    target = next(
        (a for a in poll.poll.answers if "иду" in a.text.text.lower()),
        None,
    )
    if target is None:
        log.debug("Skipping — no 'иду' option in poll: %s", poll.poll.question)
        return

    log.info("Poll detected: %s — voting for %r", poll.poll.question, target.text.text)

    # Measure server-side delivery lag: how long between Telegram stamping the
    # poll message and us actually processing it. message.date is UTC, 1s res.
    lag = (datetime.now(timezone.utc) - event.message.date).total_seconds()
    log.info("Delivery lag (poll date -> handler): %.2fs", lag)

    t0 = datetime.now(timezone.utc)
    try:
        await client(SendVoteRequest(
            peer=event.chat_id,
            msg_id=event.message.id,
            options=[target.option],
        ))
        vote_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log.info("Voted successfully (SendVote round-trip %.0fms)", vote_ms)
    except Exception:
        log.exception("Failed to vote")
        return

    # Fire-and-forget the reminder so it never sits in the vote critical path.
    # Awaiting it here would delay the next poll's handler when updates are
    # dispatched sequentially (e.g. two polls posted back-to-back).
    asyncio.create_task(schedule_reminder(poll.poll.question))


async def schedule_reminder(question):
    try:
        await client.send_message(
            "me",
            f"Voted on poll: {question}",
            schedule=timedelta(minutes=1),
        )
        log.info("Scheduled reminder to Saved Messages in 1 min")
    except Exception:
        log.exception("Failed to schedule reminder")


async def main():
    log.debug("Starting client...")
    await client.start()
    me = await client.get_me()
    log.info("Logged in as %s (id=%d)", me.first_name, me.id)
    topic_info = f", topics {TOPIC_IDS}" if TOPIC_IDS else ""
    log.info("Listening for polls in chat %d%s", CHAT_ID, topic_info)
    log.debug("Config: API_ID=%s, CHAT_ID=%s, TOPIC_IDS=%s, POLL_AUTHOR_IDS=%s", API_ID, CHAT_ID, TOPIC_IDS, POLL_AUTHOR_IDS)
    await client.run_until_disconnected()


client.loop.run_until_complete(main())
