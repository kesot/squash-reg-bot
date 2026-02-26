import os
import logging
from datetime import timedelta
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
TOPIC_ID = int(os.environ["TOPIC_ID"]) if os.environ.get("TOPIC_ID") else None
POLL_AUTHOR_ID = int(os.environ.get("POLL_AUTHOR_ID", 0)) or None

SESSION_PATH = "/app/data/bot"

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)


@client.on(events.NewMessage(chats=CHAT_ID))
async def handle_poll(event):
    log.debug("New message in chat %d, msg_id=%d", event.chat_id, event.message.id)

    if TOPIC_ID is not None:
        reply_to = event.message.reply_to
        if not reply_to or getattr(reply_to, "forum_topic", False) is False:
            log.debug("Skipping — not in target topic")
            return
        thread_id = reply_to.reply_to_top_id or reply_to.reply_to_msg_id
        if thread_id != TOPIC_ID:
            log.debug("Skipping — topic %s != %s", thread_id, TOPIC_ID)
            return

    if POLL_AUTHOR_ID and event.message.from_id and getattr(event.message.from_id, 'user_id', None) != POLL_AUTHOR_ID:
        log.debug("Skipping — author %s != %s", event.message.from_id, POLL_AUTHOR_ID)
        return

    poll = event.message.poll
    if poll is None:
        log.debug("Skipping — not a poll")
        return

    first_option = poll.poll.answers[0].option
    log.info("Poll detected: %s — voting for first option", poll.poll.question)

    try:
        await client(SendVoteRequest(
            peer=event.chat_id,
            msg_id=event.message.id,
            options=[first_option],
        ))
        log.info("Voted successfully")
        await client.send_message(
            "me",
            f"Voted on poll: {poll.poll.question}",
            schedule=timedelta(minutes=1),
        )
        log.info("Scheduled reminder to Saved Messages in 1 min")
    except Exception:
        log.exception("Failed to vote")


async def main():
    log.debug("Starting client...")
    await client.start()
    me = await client.get_me()
    log.info("Logged in as %s (id=%d)", me.first_name, me.id)
    topic_info = f", topic {TOPIC_ID}" if TOPIC_ID else ""
    log.info("Listening for polls in chat %d%s", CHAT_ID, topic_info)
    log.debug("Config: API_ID=%s, CHAT_ID=%s, TOPIC_ID=%s", API_ID, CHAT_ID, TOPIC_ID)
    await client.run_until_disconnected()


client.loop.run_until_complete(main())
