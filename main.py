import os, subprocess, json, sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ----------------- CONFIG -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID =    5671408492       # <-- Öz Telegram ID
CHANNEL_ID = "@GulievSong"  # <-- Kanal username / id
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ----------------- DATABASE -----------------
db = sqlite3.connect("stats.db")
cur = db.cursor()
# Users + Downloads
cur.execute("CREATE TABLE IF NOT EXISTS stats (users INTEGER, downloads INTEGER)")
cur.execute("SELECT COUNT(*) FROM stats")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO stats VALUES (0,0)")
# İstifadəçiləri saxlamaq (broadcast üçün)
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER UNIQUE, name TEXT)")
db.commit()

def add_user(user_id, name):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (user_id, name))
    cur.execute("UPDATE stats SET users = users + 1")
    db.commit()

def add_download():
    cur.execute("UPDATE stats SET downloads = downloads + 1")
    db.commit()

def get_stats():
    cur.execute("SELECT users, downloads FROM stats")
    return cur.fetchone()

def get_all_users():
    cur.execute("SELECT id FROM users")
    return [row[0] for row in cur.fetchall()]

# ----------------- SPOTIFY -----------------
# import spotipy
# from spotipy.oauth2 import SpotifyClientCredentials

# sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
#     client_id=SPOTIFY_CLIENT_ID,
#     client_secret=SPOTIFY_CLIENT_SECRET
# ))

# ----------------- COMMANDS -----------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user = message.from_user
    add_user(user.id, user.full_name)
    # Admina bildiriş
    await bot.send_message(
        ADMIN_ID,
        f"🚀 Start verdi\n👤 {user.full_name}\n🆔 {user.id}"
    )
    await message.answer(
        "🎵 Salam! Mən 𝑮𝒖𝒍𝒊𝒆𝒗 𝑺𝒐𝒏𝒈 🪢 istifadə qaydaları:\n\n"
        "• Mahnı adı yaz\n"
        "• YouTube / Spotify link at\n"
        "• Keyfiyyət seç (128/320 kbps)\n"
        "• Owner: @quliyevv_17 Reklam və iş birliyi üçün yaza bilərsən..✅"
    )

@dp.message_handler(commands=["stats"])
async def stats(message: types.Message):
    users, downloads = get_stats()
    await message.answer(f"📊 Statistika\n👤 User: {users}\n🎶 Download: {downloads}")

# ----------------- REKLAM (broadcast) -----------------
@dp.message_handler(commands=["reklam"])
async def reklam(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace("/reklam","").strip()
    if not text:
        await message.answer("Mesaj yazmalısan: /reklam Salam!")
        return
    all_users = get_all_users()
    sent = 0
    for u in all_users:
        try:
            await bot.send_message(u, text)
            sent += 1
        except:
            continue
    await message.answer(f"✅ Reklam göndərildi: {sent} user-ə.")

# ----------------- MUSIC HANDLER -----------------
@dp.message_handler()
async def handle(message: types.Message):
    text = message.text

    # Spotify linkdirsə, YouTube axtarışı üçün ad-album əldə edirik
    if "open.spotify.com/track" in text:
        track = sp.track(text)
        query = f"{track['name']} {track['artists'][0]['name']}"
    else:
        query = text

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🎧 128 kbps", callback_data=f"dl|128|{query}|{message.from_user.full_name}"),
        InlineKeyboardButton("🔥 320 kbps", callback_data=f"dl|320|{query}|{message.from_user.full_name}")
    )
    await message.answer("Keyfiyyət seç 👇", reply_markup=kb)

# ----------------- CALLBACK (DOWNLOAD + CHANNEL) -----------------
@dp.callback_query_handler(lambda c: c.data.startswith("dl"))
async def download(call: types.CallbackQuery):
    _, quality, query, user_name = call.data.split("|", 3)
    await call.message.edit_text("Yüklənir...📥")

    # Həmişə ytsearch – YouTube bot check-dən qaçmaq üçün
    source = f"ytsearch1:{query}"

    try:
        subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0" if quality == "320" else "5",
                "--write-thumbnail",
                "--print-json",
                "--geo-bypass",
                "--no-check-certificate",
                "--user-agent", "Mozilla/5.0",
                "-o", "music.%(ext)s",
                source
            ],
            check=True,
            stdout=open("info.json", "w"),
            stderr=subprocess.DEVNULL
        )

        info = json.load(open("info.json", "r", encoding="utf-8"))

        title = info.get("title", "Unknown")
        artist = info.get("artist") or info.get("uploader", "Unknown")

        caption = f"🎧 {title}\n👤 {artist}\n💿 {quality} kbps\n\nSifariş verən: {user_name}"

        # ---------- USER ----------
        await bot.send_audio(
            call.message.chat.id,
            audio=open("music.mp3", "rb"),
            caption=caption
        )

        # ---------- CHANNEL ----------
        await bot.send_audio(
            CHANNEL_ID,
            audio=open("music.mp3", "rb"),
            caption=caption
        )

        add_download()

        # Təmizlik
        for f in ["music.mp3", "info.json", "music.jpg", "music.webp"]:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        await call.message.answer("Xəta baş verdi❌ Yenidən cəhd et🔄")
