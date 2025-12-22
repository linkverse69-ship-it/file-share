import asyncio
import logging
import secrets
from datetime import datetime, timezone

from pymongo import MongoClient
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)

logging.disable(logging.CRITICAL)

BOT_TOKEN = "6863982081:AAF-Xa7S_OgJ5TRYT_Qth_wyQ7AdjuX_eGM"
BOT_USERNAME = "KenzoXrobot"
STORAGE_CHANNEL_ID = -1003439660511
FORCE_JOIN_CHANNEL_ID = -1003341125100
FORCE_JOIN_URL = "https://t.me/linkverse6969"
ADMIN_ID = 7737575998
MONGO_URI = "mongodb+srv://yatoo:yatoo@cluster.4rnyscd.mongodb.net/?appName=Cluster"

DELIVERY_DELETE_SECONDS = 1200
ALBUM_WAIT_SECONDS = 1.2
CAPTION_TEXT = "this will be deleted in 20 mins"

WELCOME_TEXT = (
    "Hello {name}\n\n"
    "I can store private files in Specified Channel and other users can access it from special link."
)

client = None
db = None


class ProtectedBot(Bot):
    @staticmethod
    def _protect(kwargs: dict) -> dict:
        kwargs.setdefault("protect_content", True)
        return kwargs

    async def send_message(self, *args, **kwargs):
        return await super().send_message(*args, **self._protect(kwargs))

    async def send_photo(self, *args, **kwargs):
        return await super().send_photo(*args, **self._protect(kwargs))

    async def send_video(self, *args, **kwargs):
        return await super().send_video(*args, **self._protect(kwargs))

    async def send_document(self, *args, **kwargs):
        return await super().send_document(*args, **self._protect(kwargs))

    async def send_audio(self, *args, **kwargs):
        return await super().send_audio(*args, **self._protect(kwargs))

    async def send_animation(self, *args, **kwargs):
        return await super().send_animation(*args, **self._protect(kwargs))

    async def send_voice(self, *args, **kwargs):
        return await super().send_voice(*args, **self._protect(kwargs))

    async def send_video_note(self, *args, **kwargs):
        return await super().send_video_note(*args, **self._protect(kwargs))

    async def copy_message(self, *args, **kwargs):
        return await super().copy_message(*args, **self._protect(kwargs))

    async def forward_message(self, *args, **kwargs):
        return await super().forward_message(*args, **self._protect(kwargs))


def init_db():
    global client, db
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
    )
    db = client.botdb
    db.links.create_index("code", unique=True)
    try:
        idx = db.links.index_information()
        if "created_at_1" in idx:
            db.links.drop_index("created_at_1")
    except Exception:
        pass
    db.users.create_index("user_id", unique=True)


def make_code(length: int = 16) -> str:
    while True:
        code = secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:length]
        if db.links.find_one({"code": code}) is None:
            return code


def save_link(code: str, payload: dict):
    db.links.insert_one(
        {
            "code": code,
            "payload": payload,
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_link(code: str):
    return db.links.find_one({"code": code})


def add_or_update_user(user):
    if not user:
        return
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"user_id": user.id},
        {
            "$set": {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "last_active": now,
                "is_blocked": False,
            },
            "$setOnInsert": {"joined_at": now},
        },
        upsert=True,
    )


def mark_user_blocked(user_id: int):
    db.users.update_one({"user_id": user_id}, {"$set": {"is_blocked": True}})


def get_all_active_users():
    return [
        user["user_id"]
        for user in db.users.find({"is_blocked": False}, {"user_id": 1})
    ]


def get_user_stats():
    active = db.users.count_documents({"is_blocked": False})
    blocked = db.users.count_documents({"is_blocked": True})
    return {"active": active, "blocked": blocked, "total": active + blocked}


async def delayed_delete(bot, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


def extract_item(message):
    if message.photo:
        return {"type": "photo", "file_id": message.photo[-1].file_id}
    if message.video:
        return {"type": "video", "file_id": message.video.file_id}
    if message.document:
        return {"type": "document", "file_id": message.document.file_id}
    if message.audio:
        return {"type": "audio", "file_id": message.audio.file_id}
    if message.animation:
        return {"type": "animation", "file_id": message.animation.file_id}
    if message.voice:
        return {"type": "voice", "file_id": message.voice.file_id}
    if message.video_note:
        return {"type": "video_note", "file_id": message.video_note.file_id}
    return None


def is_supported_message(msg) -> bool:
    if not msg:
        return False
    return any(
        [
            msg.photo,
            msg.video,
            msg.document,
            msg.audio,
            msg.animation,
            msg.voice,
            msg.video_note,
        ]
    )


async def send_item(bot, chat_id: int, item: dict):
    t = item["type"]
    fid = item["file_id"]
    try:
        if t == "photo":
            return await bot.send_photo(chat_id=chat_id, photo=fid, caption=CAPTION_TEXT)
        if t == "video":
            return await bot.send_video(chat_id=chat_id, video=fid, caption=CAPTION_TEXT)
        if t == "document":
            return await bot.send_document(chat_id=chat_id, document=fid, caption=CAPTION_TEXT)
        if t == "audio":
            return await bot.send_audio(chat_id=chat_id, audio=fid, caption=CAPTION_TEXT)
        if t == "animation":
            return await bot.send_animation(chat_id=chat_id, animation=fid, caption=CAPTION_TEXT)
        if t == "voice":
            return await bot.send_voice(chat_id=chat_id, voice=fid, caption=CAPTION_TEXT)
        if t == "video_note":
            return await bot.send_video_note(chat_id=chat_id, video_note=fid)
    except Exception:
        return None
    return None


async def deliver_from_storage(bot, target_chat_id: int, payload: dict):
    items = payload.get("items", [])
    storage_message_ids = payload.get("storage_message_ids", [])

    for i, item in enumerate(items):
        sent = await send_item(bot, target_chat_id, item)
        if sent is not None:
            asyncio.create_task(
                delayed_delete(bot, sent.chat_id, sent.message_id, DELIVERY_DELETE_SECONDS)
            )
        else:
            if i < len(storage_message_ids):
                try:
                    m = await bot.copy_message(
                        chat_id=target_chat_id,
                        from_chat_id=STORAGE_CHANNEL_ID,
                        message_id=int(storage_message_ids[i]),
                    )
                    asyncio.create_task(
                        delayed_delete(bot, m.chat_id, m.message_id, DELIVERY_DELETE_SECONDS)
                    )
                except Exception:
                    pass


async def test_channel_access(bot):
    try:
        await bot.get_chat(STORAGE_CHANNEL_ID)
        return True
    except Exception:
        return False


async def check_user_membership(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=FORCE_JOIN_CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_or_update_user(update.effective_user)

    if context.args:
        code = context.args[0].strip()
        user_id = update.effective_user.id

        is_member = await check_user_membership(context.bot, user_id)
        if not is_member:
            keyboard = [
                [InlineKeyboardButton("Join Channel", url=FORCE_JOIN_URL)],
                [InlineKeyboardButton("Verify Membership", callback_data=f"verify_{code}")],
            ]
            await update.message.reply_text(
                "You must join our channel to access files.\n\nJoin the channel and click Verify Membership.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        link_doc = get_link(code)
        if not link_doc:
            await update.message.reply_text("Invalid link.")
            return

        payload = link_doc.get("payload", {})
        items = payload.get("items", [])
        storage_ids = payload.get("storage_message_ids", [])

        if not items and not storage_ids:
            await update.message.reply_text("Invalid link.")
            return

        await deliver_from_storage(context.bot, update.effective_chat.id, payload)
        return

    name = update.effective_user.full_name if update.effective_user else "there"
    await update.message.reply_text(WELCOME_TEXT.format(name=name))


async def verify_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    code = query.data.replace("verify_", "")
    user_id = update.effective_user.id

    is_member = await check_user_membership(context.bot, user_id)
    if not is_member:
        await query.answer("You have not joined the channel yet. Please join first.", show_alert=True)
        return

    await query.answer()

    link_doc = get_link(code)
    if not link_doc:
        await query.edit_message_text("Invalid link.")
        return

    payload = link_doc.get("payload", {})
    items = payload.get("items", [])
    storage_ids = payload.get("storage_message_ids", [])

    if not items and not storage_ids:
        await query.edit_message_text("Invalid link.")
        return

    await query.edit_message_text("Verified! Sending files...")
    await deliver_from_storage(context.bot, query.message.chat_id, payload)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    if uid != ADMIN_ID:
        await update.message.reply_text("Only admin can view stats.")
        return

    s = get_user_stats()
    await update.message.reply_text(
        f"Bot Statistics\n\nTotal Users: {s['total']}\nActive Users: {s['active']}\nBlocked Users: {s['blocked']}"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    if uid != ADMIN_ID:
        await update.message.reply_text("Only admin can broadcast.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message with /broadcast to send it to all users.")
        return

    users = get_all_active_users()
    if not users:
        await update.message.reply_text("No active users to broadcast to.")
        return

    status_msg = await update.message.reply_text(f"Broadcasting to {len(users)} users...\n0/{len(users)}")

    success = failed = blocked = 0
    msg_to_send = update.message.reply_to_message

    for i, user_id in enumerate(users):
        try:
            await msg_to_send.copy(chat_id=user_id)
            success += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "user is deactivated" in err or "bot was blocked" in err:
                mark_user_blocked(user_id)
                blocked += 1
            else:
                failed += 1

        if (i + 1) % 10 == 0 or (i + 1) == len(users):
            try:
                await status_msg.edit_text(
                    f"Broadcasting...\n{i + 1}/{len(users)}\n\nDelivered: {success}\nFailed: {failed}\nBlocked: {blocked}"
                )
            except Exception:
                pass

        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"Broadcast Complete\n\nDelivered: {success}\nFailed: {failed}\nBlocked: {blocked}\nTotal: {len(users)}"
    )


async def store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_or_update_user(update.effective_user)

    uid = update.effective_user.id if update.effective_user else 0
    if uid != ADMIN_ID:
        await update.message.reply_text("Only admin can upload.")
        return

    if not is_supported_message(update.message):
        await update.message.reply_text("Unsupported message.")
        return

    item = extract_item(update.message)
    if not item:
        await update.message.reply_text("Unsupported message.")
        return

    mgid = update.message.media_group_id

    if mgid:
        base = f"mg:{update.effective_chat.id}:{mgid}"
        key_mids = f"{base}:mids"
        key_items = f"{base}:items"

        mids_bucket = context.application.bot_data.get(key_mids, [])
        mids_bucket.append(update.message.message_id)
        context.application.bot_data[key_mids] = mids_bucket

        items_bucket = context.application.bot_data.get(key_items, [])
        items_bucket.append(item)
        context.application.bot_data[key_items] = items_bucket

        task_key = f"task:{base}"
        old = context.application.bot_data.get(task_key)
        if old:
            try:
                old.cancel()
            except Exception:
                pass

        context.application.bot_data[task_key] = asyncio.create_task(
            finalize_album(context.application, update.effective_chat.id, base)
        )
        return

    try:
        stored_msg = await context.bot.forward_message(
            chat_id=STORAGE_CHANNEL_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )
    except Exception:
        try:
            stored_msg = await context.bot.copy_message(
                chat_id=STORAGE_CHANNEL_ID,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
        except Exception:
            await update.message.reply_text("Upload failed.")
            return

    code = make_code()
    save_link(code, {"storage_message_ids": [stored_msg.message_id], "items": [item]})
    await update.message.reply_text(
        f"https://t.me/{BOT_USERNAME}?start={code}", disable_web_page_preview=True
    )


async def finalize_album(app: Application, chat_id: int, base: str):
    await asyncio.sleep(ALBUM_WAIT_SECONDS)

    key_mids = f"{base}:mids"
    key_items = f"{base}:items"
    task_key = f"task:{base}"

    msg_ids = app.bot_data.get(key_mids, [])
    items = app.bot_data.get(key_items, [])

    app.bot_data.pop(key_mids, None)
    app.bot_data.pop(key_items, None)
    app.bot_data.pop(task_key, None)

    if not msg_ids:
        return

    stored_ids = []

    for mid in msg_ids:
        try:
            stored_msg = await app.bot.forward_message(
                chat_id=STORAGE_CHANNEL_ID,
                from_chat_id=chat_id,
                message_id=int(mid),
            )
        except Exception:
            try:
                stored_msg = await app.bot.copy_message(
                    chat_id=STORAGE_CHANNEL_ID,
                    from_chat_id=chat_id,
                    message_id=int(mid),
                )
            except Exception:
                return
        stored_ids.append(stored_msg.message_id)

    code = make_code()
    save_link(code, {"storage_message_ids": stored_ids, "items": items})
    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=f"https://t.me/{BOT_USERNAME}?start={code}",
            disable_web_page_preview=True,
        )
    except Exception:
        pass


async def post_init(application: Application):
    init_db()
    await test_channel_access(application.bot)


def main():
    bot = ProtectedBot(token=BOT_TOKEN)
    app = Application.builder().bot(bot).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(verify_membership_callback, pattern="^verify_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, store))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
