import asyncio
import json
import sqlite3
from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton

API_ID = 27502961
API_HASH = "b8d9acdc18d1352241239aab9e348fa5"
BOT_TOKEN = "7813573214:AAFtwCpJZMXGcHYFZ3LzmFgpEgJC6y16JJE"

ADMIN_IDS = {7737575998}
STORAGE_CHANNEL_ID = -4996646671

DELETE_DELAY = 1200

app = Client("media_store_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

db = sqlite3.connect("media.db", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS contents (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, files TEXT, caption TEXT)")
db.commit()

album_buffer = {}

def is_admin(uid):
    return uid in ADMIN_IDS

def buttons():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Link", url="https://example.com")]])

async def auto_delete(client, chat_id, ids):
    await asyncio.sleep(DELETE_DELAY)
    for mid in ids:
        try:
            await client.delete_messages(chat_id, mid)
        except:
            pass

@app.on_message(filters.private & filters.media)
async def upload_handler(client, message):
    if not is_admin(message.from_user.id):
        return

    gid = message.media_group_id

    if gid:
        album_buffer.setdefault(gid, []).append(message)
        await asyncio.sleep(1.5)
        if gid not in album_buffer:
            return

        album = album_buffer.pop(gid)
        album.sort(key=lambda x: x.id)

        forwarded = []
        for m in album:
            f = await m.copy(STORAGE_CHANNEL_ID)
            forwarded.append(f)

        files = []
        for f in forwarded:
            if f.photo:
                files.append(("photo", f.photo.file_id))
            elif f.video:
                files.append(("video", f.video.file_id))

        caption = album[0].caption or ""

        cur.execute("INSERT INTO contents (type, files, caption) VALUES (?, ?, ?)", ("album", json.dumps(files), caption))
        db.commit()
        cid = cur.lastrowid

        await message.reply(f"✅ Album saved\n🆔 ID: `{cid}`", reply_markup=buttons())
        return

    fwd = await message.copy(STORAGE_CHANNEL_ID)

    if fwd.photo:
        files = [("photo", fwd.photo.file_id)]
    elif fwd.video:
        files = [("video", fwd.video.file_id)]
    else:
        return

    caption = message.caption or ""

    cur.execute("INSERT INTO contents (type, files, caption) VALUES (?, ?, ?)", ("single", json.dumps(files), caption))
    db.commit()
    cid = cur.lastrowid

    await message.reply(f"✅ Media saved\n🆔 ID: `{cid}`", reply_markup=buttons())

@app.on_message(filters.private & filters.command("get"))
async def get_handler(client, message):
    if len(message.command) < 2:
        return

    try:
        cid = int(message.command[1])
    except:
        return

    cur.execute("SELECT type, files, caption FROM contents WHERE id=?", (cid,))
    row = cur.fetchone()

    if not row:
        await message.reply("❌ Content not found")
        return

    ctype, files, caption = row
    files = json.loads(files)

    if ctype == "single":
        mtype, fid = files[0]
        if mtype == "photo":
            msg = await client.send_photo(message.chat.id, fid, caption=caption, reply_markup=buttons())
        else:
            msg = await client.send_video(message.chat.id, fid, caption=caption, reply_markup=buttons())
        asyncio.create_task(auto_delete(client, message.chat.id, [msg.id]))
        return

    media = []
    for i, (mtype, fid) in enumerate(files):
        cap = caption if i == 0 else None
        if mtype == "photo":
            media.append(InputMediaPhoto(fid, caption=cap))
        else:
            media.append(InputMediaVideo(fid, caption=cap))

    msgs = await client.send_media_group(message.chat.id, media)
    btn = await client.send_message(message.chat.id, "⬇️ Link below", reply_markup=buttons())

    ids = [m.id for m in msgs]
    ids.append(btn.id)

    asyncio.create_task(auto_delete(client, message.chat.id, ids))

app.run()
