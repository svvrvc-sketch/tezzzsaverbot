import os
import sys
import asyncio
import aiohttp
import re
import inspect
import subprocess
from datetime import datetime
from dotenv import load_dotenv

import yt_dlp

# FFmpeg ni avtomatik imageio_ffmpeg orqali topish (Windows va Linuxda ishlaydi)
import shutil
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        try:
            os.chmod(FFMPEG_PATH, 0o755)
        except Exception:
            pass
except Exception:
    FFMPEG_PATH = shutil.which("ffmpeg")

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
from supabase import create_client, Client

# Konsolda va Render logsida ma'lumotlar darhol ko'rinishi uchun
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# --- SOZLAMALARNI YUKLASH (.env) ---
load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN', '8747746960:AAEStDxdU6EKD0F5uqsUZIlVi0b4mYFqN7c')
ADMIN_ID = int(os.getenv('ADMIN_ID', '5111794979'))

USE_MANDATORY_SUB = os.getenv('USE_MANDATORY_SUB', 'False').lower() == 'true'
REQUIRED_CHANNEL = os.getenv('REQUIRED_CHANNEL', '@openwebacademy')
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB Telegram Bot API limiti
PROXY_URL = os.getenv('PROXY_URL', '')  # Agar proxy bo'lsa (masalan, http://127.0.0.1:1080 yoki vpn)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- BAZA VA LOKAL KESH (SUPABASE BO'LMASA HAM 100% ISHLAYDI) ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USER_DATA_CACHE = {}

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        supabase.table("users").select("count", count="exact").execute()
    except Exception as e:
        supabase = None
        print(f"DIQQAT: Supabase ulanishida xatolik: {e}")
else:
    supabase = None
    print("DIQQAT: Supabase ulanmagan. Bot lokal xotira rejimida barqaror ishlayapti.")

# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban_id = State()

# --- BAZA BILAN ISHLASH FUNKSIYALARI ---
def db_add_user(user_id):
    user_id = str(user_id)
    if user_id not in USER_DATA_CACHE:
        USER_DATA_CACHE[user_id] = {"lang": "uz", "banned": False, "last_url": ""}
    if not supabase: return
    try:
        res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not res.data:
            supabase.table("users").insert({"id": user_id, "lang": "uz", "banned": False, "last_url": ""}).execute()
        else:
            USER_DATA_CACHE[user_id] = res.data[0]
    except Exception as e:
        print(f"DB Add Error: {e}")

def db_get_all_users():
    if not supabase: return list(USER_DATA_CACHE.keys())
    try:
        res = supabase.table("users").select("id").execute()
        return [item["id"] for item in res.data]
    except Exception as e:
        print(f"DB Get Users Error: {e}")
        return list(USER_DATA_CACHE.keys())

def db_is_banned(user_id):
    user_id = str(user_id)
    if user_id in USER_DATA_CACHE and "banned" in USER_DATA_CACHE[user_id]:
        return USER_DATA_CACHE[user_id]["banned"]
    if not supabase: return False
    try:
        res = supabase.table("users").select("banned").eq("id", user_id).execute()
        if res.data: return res.data[0].get("banned", False)
    except Exception:
        pass
    return False

def db_set_ban(user_id, status: bool):
    user_id = str(user_id)
    if user_id not in USER_DATA_CACHE:
        USER_DATA_CACHE[user_id] = {}
    USER_DATA_CACHE[user_id]["banned"] = status
    if not supabase: return
    try:
        supabase.table("users").upsert({"id": user_id, "banned": status}).execute()
    except Exception as e:
        print(f"DB Ban Error: {e}")

def db_set_lang(user_id, lang):
    user_id = str(user_id)
    if user_id not in USER_DATA_CACHE:
        USER_DATA_CACHE[user_id] = {}
    USER_DATA_CACHE[user_id]["lang"] = lang
    if not supabase: return
    try:
        supabase.table("users").upsert({"id": user_id, "lang": lang}).execute()
    except Exception:
        pass

def db_get_lang(user_id):
    user_id = str(user_id)
    if user_id in USER_DATA_CACHE and "lang" in USER_DATA_CACHE[user_id]:
        return USER_DATA_CACHE[user_id]["lang"]
    if not supabase: return "uz"
    try:
        res = supabase.table("users").select("lang").eq("id", user_id).execute()
        if res.data:
            lang = res.data[0].get("lang", "uz")
            if user_id not in USER_DATA_CACHE:
                USER_DATA_CACHE[user_id] = {}
            USER_DATA_CACHE[user_id]["lang"] = lang
            return lang
    except Exception:
        pass
    return "uz"

def db_set_last_url(user_id, url):
    user_id = str(user_id)
    if user_id not in USER_DATA_CACHE:
        USER_DATA_CACHE[user_id] = {}
    USER_DATA_CACHE[user_id]["last_url"] = url
    if not supabase: return
    try:
        supabase.table("users").upsert({"id": user_id, "last_url": url}).execute()
    except Exception:
        pass

def db_get_last_url(user_id):
    user_id = str(user_id)
    if user_id in USER_DATA_CACHE and USER_DATA_CACHE[user_id].get("last_url"):
        return USER_DATA_CACHE[user_id]["last_url"]
    if not supabase: return ""
    try:
        res = supabase.table("users").select("last_url").eq("id", user_id).execute()
        if res.data:
            url = res.data[0].get("last_url", "")
            if user_id not in USER_DATA_CACHE:
                USER_DATA_CACHE[user_id] = {}
            USER_DATA_CACHE[user_id]["last_url"] = url
            return url
    except Exception:
        pass
    return ""

# --- TILLAR VA MATNLAR ---
LANGUAGES = {
    "uz": {
        "start": "⚡️ **Xush kelibsiz!**\nMenga ijtimoiy tarmoqlardan (Instagram, TikTok, YouTube, Pinterest) havola yuboring, uni bir zumda yuklab beraman! 🚀",
        "wait": "⏳ Video yuqori tezlikda yuklanmoqda, iltimos kuting...",
        "audio_wait": "⏳ Audio (MP3) tayyorlanmoqda, iltimos kuting...",
        "choose_format": "🎬 YouTube videosi aniqlandi! Qaysi formatda yuklamoqchisiz?",
        "success": "⚡️ @tezzzsaverbot orqali yuklab olindi!",
        "fail": "❌ Yuklashda xatolik yuz berdi yoki havola noto'g'ri (yopiq profil bo'lishi mumkin).",
        "too_large": "⚠️ Kechirasiz, fayl hajmi 50 MB dan katta bo'lgani sababli Telegram orqali yuborib bo'lmadi.",
        "sub_required": "⚠️ **Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz shart!**",
        "check_sub_btn": "✅ A'zo bo'ldim / Tekshirish"
    },
    "ru": {
        "start": "⚡️ **Добро пожаловать!**\nОтправьте мне ссылку (Instagram, TikTok, YouTube, Pinterest), и я скачаю её! 🚀",
        "wait": "⏳ Видео загружается на высокой скорости, подождите...",
        "audio_wait": "⏳ Аудио (MP3) обрабатывается, подождите...",
        "choose_format": "🎬 Обнаружено видео YouTube! Выберите формат:",
        "success": "⚡️ Скачано с помощью @tezzzsaverbot!",
        "fail": "❌ Ошибка при скачивании или неверная ссылка (возможно, закрытый профиль).",
        "too_large": "⚠️ К сожалению, размер файла превышает 50 МБ (лимит Telegram).",
        "sub_required": "⚠️ **Для использования бота подпишитесь на канал!**",
        "check_sub_btn": "✅ Я подписался"
    },
    "en": {
        "start": "⚡️ **Welcome!**\nSend me a link (Instagram, TikTok, YouTube, Pinterest), and I will download it! 🚀",
        "wait": "⏳ Video is downloading at high speed, please wait...",
        "audio_wait": "⏳ Audio (MP3) is being prepared, please wait...",
        "choose_format": "🎬 YouTube video detected! Choose format:",
        "success": "⚡️ Downloaded via @tezzzsaverbot!",
        "fail": "❌ Error occurred during download or invalid link (or private profile).",
        "too_large": "⚠️ Sorry, this file exceeds the 50 MB Telegram upload limit.",
        "sub_required": "⚠️ **To use the bot, you must subscribe to our channel!**",
        "check_sub_btn": "✅ I subscribed"
    }
}

async def is_subscribed(user_id):
    if not USE_MANDATORY_SUB or not REQUIRED_CHANNEL: return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=int(user_id))
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        # Agar bot kanalda admin bo'lmasa yoki xatolik bo'lsa, foydalanuvchini to'xtatmaymiz
        return True

def check_ban(func):
    async def wrapper(message_or_call, *args, **kwargs):
        user_id = message_or_call.from_user.id
        if db_is_banned(user_id):
            if isinstance(message_or_call, types.Message):
                await message_or_call.answer("🚫 Botdan foydalanish huquqingiz cheklangan.")
            elif isinstance(message_or_call, types.CallbackQuery):
                await message_or_call.answer("🚫 Bloklangansiz!", show_alert=True)
            return
        sig = inspect.signature(func)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await func(message_or_call, *args, **filtered_kwargs)
    return wrapper

# --- KOMANDALAR VA START ---
@dp.message(CommandStart())
@check_ban
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    db_add_user(user_id)
    
    if not await is_subscribed(user_id):
        sub_builder = InlineKeyboardBuilder()
        sub_builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        sub_builder.row(types.InlineKeyboardButton(text=LANGUAGES["uz"]["check_sub_btn"], callback_data="check_subscription"))
        await message.answer(LANGUAGES["uz"]["sub_required"], reply_markup=sub_builder.as_markup(), parse_mode="Markdown")
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
    )
    if message.from_user.id == ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"))
        
    await message.answer("🌐 Tilni tanlang / Choose language / Выберите язык:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("lang_"))
@check_ban
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    db_set_lang(callback.from_user.id, lang)
    await callback.message.edit_text(LANGUAGES[lang]["start"], parse_mode="Markdown")

# --- ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    users = db_get_all_users()
    admin_text = f"📊 **Bot Statistikasi**\n\n👥 Jami foydalanuvchilar: `{len(users)}` ta"
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📢 Xabar yuborish (Rassilka)", callback_data="admin_broadcast"),
        types.InlineKeyboardButton(text="🚫 Ban / Unban", callback_data="admin_ban")
    )
    await callback.message.edit_text(admin_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text("📢 Rassilka xabarini (matn, rasm yoki video) yuboring:")

@dp.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    
    users = db_get_all_users()
    status_msg = await message.answer(f"⏳ Xabar `{len(users)}` ta foydalanuvchiga yuborilmoqda...")
    success_count = 0; fail_count = 0
    
    for u in users:
        try:
            await bot.copy_message(chat_id=int(u), from_chat_id=message.chat.id, message_id=message.message_id)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1
        
    await status_msg.edit_text(f"✅ **Rassilka yakunlandi!**\n\n🚀 Muvaffaqiyatli: `{success_count}` ta\n❌ Yuborilmadi: `{fail_count}` ta", parse_mode="Markdown")

@dp.callback_query(F.data == "admin_ban")
async def start_ban(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_ban_id)
    await callback.message.edit_text("🚫 Bloklamoqchi bo'lgan ID raqamni yuboring:")

@dp.message(AdminStates.waiting_for_ban_id)
async def do_ban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    target_id = message.text.strip()
    
    if db_is_banned(target_id):
        db_set_ban(target_id, False)
        msg = f"✅ Foydalanuvchi ({target_id}) blokdan chiqarildi."
    else:
        db_set_ban(target_id, True)
        msg = f"🚫 Foydalanuvchi ({target_id}) bloklandi."
    await message.answer(msg)

@dp.callback_query(F.data == "check_subscription")
async def check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await is_subscribed(user_id):
        await callback.message.delete()
        await callback.message.answer("🎉 Rahmat! Havola yuborishingiz mumkin.")
    else:
        await callback.answer("⚠️ Kanalga a'zo bo'ling!", show_alert=True)

# --- HAVOLALARNI QABUL QILISH TIZIMI ---
@dp.message(F.text)
@check_ban
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    db_add_user(user_id)
    lang = db_get_lang(user_id)
    urls = re.findall(r'(https?://[^\s]+)', message.text)
    if not urls: return

    url = urls[0]
    print(f"📥 [LOG] Yangi havola keldi (User {user_id}): {url}", flush=True)

    if not await is_subscribed(user_id):
        sub_builder = InlineKeyboardBuilder()
        sub_builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        sub_builder.row(types.InlineKeyboardButton(text=LANGUAGES[lang]["check_sub_btn"], callback_data="check_subscription"))
        return await message.answer(LANGUAGES[lang]["sub_required"], reply_markup=sub_builder.as_markup())

    platform = None
    if "instagram.com" in url or "instagr.am" in url: platform = "instagram"
    elif "tiktok.com" in url or "douyin.com" in url or "tikwm.com" in url: platform = "tiktok"
    elif "youtube.com" in url or "youtu.be" in url: platform = "youtube"
    elif "pinterest.com" in url or "pin.it" in url: platform = "pinterest"
    elif "twitter.com" in url or "x.com" in url: platform = "twitter"
    elif "facebook.com" in url or "fb.watch" in url or "fb.com" in url: platform = "facebook"
    else: platform = "generic"

    print(f"🎯 [LOG] Aniqlangan platforma: {platform}", flush=True)
    db_set_last_url(user_id, url)

    if platform == "youtube":
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="🎬 720p Video (Tezkor)", callback_data="yt_dl|720"),
            types.InlineKeyboardButton(text="📺 360p Video (Tezkor)", callback_data="yt_dl|360")
        )
        builder.row(
            types.InlineKeyboardButton(text="🎵 MP3 Audio", callback_data="yt_dl|mp3")
        )
        await message.answer(LANGUAGES[lang]["choose_format"], reply_markup=builder.as_markup())
    else:
        status_msg = await message.answer(LANGUAGES[lang]["wait"])
        await process_media_download(status_msg, url, lang, platform=platform, is_audio=False)

@dp.callback_query(F.data.startswith("yt_dl|"))
@check_ban
async def youtube_download_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = db_get_lang(user_id)
    url = db_get_last_url(user_id)
    if not url:
        return await callback.answer("Havola topilmadi! Qaytadan havola yuboring.", show_alert=True)
    
    choice = callback.data.split("|")[1]
    if choice == "mp3":
        await callback.message.edit_text(LANGUAGES[lang]["audio_wait"])
        await process_media_download(callback.message, url, lang, platform="youtube", is_audio=True)
    else:
        await callback.message.edit_text(LANGUAGES[lang]["wait"])
        await process_media_download(callback.message, url, lang, platform="youtube", quality=choice, is_audio=False)

# --- INLINE REJIM ---
@dp.inline_query()
async def inline_share_video(inline_query: types.InlineQuery):
    file_id = inline_query.query.strip()
    if not file_id: return
    result = types.InlineQueryResultCachedVideo(
        id="share_video_res",
        video_file_id=file_id,
        title="Yuklab olingan video",
        caption="⚡️ @tezzzsaverbot orqali yuklab olindi!"
    )
    await inline_query.answer([result], cache_time=1)

# --- DIRECT DOWNLOADERS (TIKTOK, INSTAGRAM & PINTEREST BACKENDS) ---
async def download_tiktok_direct(url, out_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            if "vt.tiktok.com" in url or "vm.tiktok.com" in url:
                try:
                    async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=4)) as r:
                        url = str(r.url)
                except Exception:
                    pass

            async with session.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    if res.get("code") == 0:
                        video_url = res["data"].get("play") or res["data"].get("wmplay")
                        title = res["data"].get("title", "TikTok Video")
                        if video_url:
                            async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=15)) as vresp:
                                if vresp.status == 200:
                                    with open(out_path, "wb") as f:
                                        while True:
                                            chunk = await vresp.content.read(65536)
                                            if not chunk: break
                                            f.write(chunk)
                                    return True, title
    except Exception as e:
        print(f"TikTok direct error: {e}")
    return False, None

async def download_instagram_direct(url, out_path):
    shortcode_match = re.search(r'(?:p|reel|reels|tv|share/reel)/([A-Za-z0-9_-]+)', url)
    if not shortcode_match:
        return False, None

    shortcode = shortcode_match.group(1)
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(embed_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                html = await resp.text()
                clean_html = html.replace(r'\/', '/').replace(r'\u002F', '/')
                video_match = re.findall(r'"video_url":"([^"]+)"', clean_html)
                if not video_match:
                    video_match = re.findall(r'<video[^>]+src="([^">]+)"', clean_html)
                if not video_match:
                    video_match = re.findall(r'<meta[^>]+property=["\']og:video(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']', clean_html)

                if video_match:
                    raw_url = video_match[0].replace('&amp;', '&')
                    async with session.get(raw_url, timeout=aiohttp.ClientTimeout(total=15)) as vresp:
                        if vresp.status == 200:
                            with open(out_path, "wb") as f:
                                while True:
                                    chunk = await vresp.content.read(65536)
                                    if not chunk: break
                                    f.write(chunk)
                            return True, "Instagram Video"
    except Exception as e:
        print(f"Instagram embed error: {e}")
    return False, None

async def download_pinterest_direct(url, out_path_base):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                html = await resp.text()

            clean_html = html.replace(r'\/', '/').replace(r'\u002F', '/')

            # 1. Video pinlarni qidirish (.mp4 yoki .m3u8)
            video_matches = re.findall(r'(https?://[a-zA-Z0-9.-]*pinimg\.com/videos/[a-zA-Z0-9_./-]+\.(?:mp4|m3u8))', clean_html)
            if not video_matches:
                video_matches = re.findall(r'(https?://(?:v|v1|v2|media)\.pinimg\.com/[a-zA-Z0-9_./-]+\.(?:mp4|m3u8))', clean_html)
            if not video_matches:
                video_matches = re.findall(r'<meta[^>]+property=["\']og:video(?::secure_url)?["\'][^>]+content=["\']([^"\']+\.(?:mp4|m3u8))["\']', clean_html)
            if not video_matches:
                video_matches = re.findall(r'<source[^>]+src=["\']([^"\']+\.(?:mp4|m3u8))["\']', clean_html)

            best_video = None
            for v in video_matches:
                v = v.replace('&amp;', '&')
                if ".mp4" in v:
                    if "720p" in v or not best_video:
                        best_video = v
                elif not best_video:
                    best_video = v

            if best_video:
                v_out = f"{out_path_base}.mp4"
                if FFMPEG_PATH:
                    cmd = [
                        FFMPEG_PATH, '-y',
                        '-headers', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n',
                        '-i', best_video,
                        '-c', 'copy',
                        '-movflags', '+faststart',
                        v_out
                    ]
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
                    if os.path.exists(v_out) and os.path.getsize(v_out) > 1024:
                        return True, "video", v_out
                else:
                    async with session.get(best_video, timeout=aiohttp.ClientTimeout(total=20)) as r:
                        if r.status == 200:
                            with open(v_out, "wb") as f:
                                while True:
                                    chunk = await r.content.read(65536)
                                    if not chunk: break
                                    f.write(chunk)
                            return True, "video", v_out

            # 2. Rasm pinlarni qidirish (Original sifat .png, .jpg)
            image_matches = re.findall(r'(https?://i\.pinimg\.com/originals/[a-zA-Z0-9_./-]+\.(?:jpg|jpeg|png|webp|gif))', clean_html)
            if not image_matches:
                image_matches = re.findall(r'(https?://i\.pinimg\.com/736x/[a-zA-Z0-9_./-]+\.(?:jpg|jpeg|png|webp|gif))', clean_html)
            if not image_matches:
                image_matches = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', clean_html)

            if image_matches:
                best_img = image_matches[0].replace('&amp;', '&')
                ext = best_img.split('?')[0].split('.')[-1].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']: ext = 'jpg'
                img_out = f"{out_path_base}.{ext}"
                async with session.get(best_img, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        with open(img_out, "wb") as f:
                            while True:
                                chunk = await r.content.read(65536)
                                if not chunk: break
                                f.write(chunk)
                        return True, "image", img_out
    except Exception as e:
        print(f"Pinterest direct error: {e}")

    return False, None, None

def download_via_ytdlp(url, out_template, is_audio=False, quality=None):
    # Universal format tanlash
    if is_audio:
        fmt = 'ba/b'
    elif quality:
        if str(quality) == '360':
            fmt = 'bv*[height<=360]+ba/b[height<=360]/bv*+ba/b'
        elif str(quality) == '720':
            fmt = 'bv*[height<=720]+ba/b[height<=720]/bv*+ba/b'
        else:
            fmt = f'bv*[height<={quality}]+ba/b[height<={quality}]/bv*+ba/b'
    else:
        fmt = 'bv*[height<=720]+ba/b[height<=720]/bv*+ba/b'

    ydl_opts = {
        'format': fmt,
        'outtmpl': out_template,
        'merge_output_format': 'mp4' if not is_audio else None,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 15,
        'max_filesize': MAX_FILE_SIZE,
    }

    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH
        ydl_opts['postprocessor_args'] = {
            'ffmpeg': ['-movflags', '+faststart']
        }

    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL

    if 'youtube' in url or 'youtu.be' in url:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
        ydl_opts['concurrent_fragment_downloads'] = 5

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info

def prepare_video_for_telegram(video_path):
    if not FFMPEG_PATH or not os.path.exists(video_path):
        return video_path, 0, 0, 0, None

    out_dir = os.path.dirname(video_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    fixed_path = os.path.join(out_dir, f"{base_name}_fast.mp4")
    thumb_path = os.path.join(out_dir, f"{base_name}_thumb.jpg")

    # Single-pass FFmpeg (FastStart + Thumbnail + Video Info in <0.08s)
    cmd = [
        FFMPEG_PATH, '-y',
        '-i', video_path,
        '-c', 'copy',
        '-movflags', '+faststart',
        fixed_path,
        '-ss', '00:00:00.500',
        '-vframes', '1',
        '-q:v', '2',
        thumb_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
    stderr_text = res.stderr

    duration = 0
    width = 0
    height = 0
    try:
        dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', stderr_text)
        if dur_match:
            hours = int(dur_match.group(1))
            mins = int(dur_match.group(2))
            secs = float(dur_match.group(3))
            duration = int(hours * 3600 + mins * 60 + secs)

        res_match = re.search(r'Video:.*,\s*(\d{2,5})x(\d{2,5})', stderr_text)
        if res_match:
            width = int(res_match.group(1))
            height = int(res_match.group(2))
    except Exception:
        pass

    target_video = fixed_path if (os.path.exists(fixed_path) and os.path.getsize(fixed_path) > 0) else video_path
    final_thumb = thumb_path if (os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0) else None

    return target_video, duration, width, height, final_thumb

# --- ASOSIY MEDIA YUKLASH FUNKSIYASI ---
async def process_media_download(msg_to_edit, url, lang, platform=None, quality=None, is_audio=False):
    bot_info = await bot.get_me()
    downloaded_files = []
    
    timestamp = int(datetime.now().timestamp() * 1000)
    unique_prefix = f"dl_{msg_to_edit.chat.id}_{timestamp}"
    target_filename = os.path.join(DOWNLOAD_DIR, f"{unique_prefix}.{'m4a' if is_audio else 'mp4'}")
    outtmpl_pattern = os.path.join(DOWNLOAD_DIR, f"{unique_prefix}.%(ext)s")

    try:
        print(f"🚀 [LOG] Yuklash jarayoni boshlandi: {platform} -> {url}", flush=True)
        loop = asyncio.get_event_loop()
        info = {}
        download_success = False
        media_type = "video" if not is_audio else "audio"

        # 1. TikTok maxsus yuklash
        if platform == "tiktok":
            ok, tt_title = await download_tiktok_direct(url, target_filename)
            if ok:
                download_success = True
                info = {'title': tt_title or 'TikTok Video', 'uploader': 'TikTok'}

        # 2. Instagram maxsus yuklash
        elif platform == "instagram":
            ok, ig_title = await download_instagram_direct(url, target_filename)
            if ok:
                download_success = True
                info = {'title': ig_title or 'Instagram Video', 'uploader': 'Instagram'}

        # 3. Pinterest maxsus yuklash (Video va Rasm pinlar)
        elif platform == "pinterest":
            ok, p_type, p_path = await download_pinterest_direct(url, os.path.join(DOWNLOAD_DIR, unique_prefix))
            if ok and p_path and os.path.exists(p_path):
                download_success = True
                media_type = p_type
                downloaded_files.append(p_path)
                info = {'title': 'Pinterest Pin', 'uploader': 'Pinterest'}

        # 4. Agar direct usul ishlamasa yoki YouTube/Twitter/FB bo'lsa -> yt-dlp
        if not download_success:
            try:
                info = await loop.run_in_executor(
                    None, 
                    lambda: download_via_ytdlp(url, outtmpl_pattern, is_audio=is_audio, quality=quality)
                )
                download_success = True
            except Exception as ytdlp_err:
                print(f"yt-dlp download failed: {ytdlp_err}")

        # Yuklangan faylni aniqlash
        found_file = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(unique_prefix) and not f.endswith("_thumb.jpg") and not f.endswith("_fast.mp4"):
                full_path = os.path.join(DOWNLOAD_DIR, f)
                downloaded_files.append(full_path)
                found_file = full_path

        if not found_file or not os.path.exists(found_file) or os.path.getsize(found_file) == 0:
            await msg_to_edit.edit_text(LANGUAGES[lang]["fail"])
            return

        # 50 MB Telegram Bot cheklovi
        if os.path.getsize(found_file) > MAX_FILE_SIZE:
            await msg_to_edit.edit_text(LANGUAGES[lang]["too_large"])
            return

        # Vertikal tugmalar
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="👈 Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true"))
        builder.row(types.InlineKeyboardButton(text="🚀 Ulashish", switch_inline_query=""))

        if media_type == "image":
            file_input = types.FSInputFile(found_file)
            await bot.send_photo(
                chat_id=msg_to_edit.chat.id,
                photo=file_input,
                caption=LANGUAGES[lang]["success"],
                reply_markup=builder.as_markup()
            )
        elif is_audio or media_type == "audio":
            file_input = types.FSInputFile(found_file)
            title = info.get('title', 'Audio') if info else 'Audio'
            performer = info.get('uploader', info.get('channel', 'Saver Bot')) if info else 'Saver Bot'
            duration = int(info.get('duration', 0)) if info else 0

            await bot.send_audio(
                chat_id=msg_to_edit.chat.id,
                audio=file_input,
                title=str(title)[:64],
                performer=str(performer)[:64],
                duration=duration,
                caption=LANGUAGES[lang]["success"],
                reply_markup=builder.as_markup()
            )
        else:
            # Video uchun Telegram mosligini ta'minlash (+faststart, duration, thumbnail)
            target_vid, duration, width, height, thumb_path = await loop.run_in_executor(
                None, lambda: prepare_video_for_telegram(found_file)
            )
            if target_vid != found_file:
                downloaded_files.append(target_vid)
            if thumb_path:
                downloaded_files.append(thumb_path)

            video_file = types.FSInputFile(target_vid)
            thumb_file = types.FSInputFile(thumb_path) if thumb_path else None

            await bot.send_video(
                chat_id=msg_to_edit.chat.id,
                video=video_file,
                duration=duration if duration > 0 else None,
                width=width if width > 0 else None,
                height=height if height > 0 else None,
                thumbnail=thumb_file,
                supports_streaming=True,
                caption=LANGUAGES[lang]["success"],
                reply_markup=builder.as_markup()
            )

        await msg_to_edit.delete()

    except Exception as e:
        import traceback
        print(f"Umumiy yuklash xatoligi: {e}")
        traceback.print_exc()
        try:
            await msg_to_edit.edit_text(LANGUAGES[lang]["fail"])
        except Exception:
            pass
    finally:
        # Har doim vaqtinchalik fayllarni o'chirish (xotira toza qoladi)
        for fpath in downloaded_files:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception as del_err:
                    print(f"Fayl o'chirish xatosi: {del_err}")

# --- WEB SERVER (HOSTINGDA Uxlab qolmasligi uchun) ---
async def handle_root(request):
    return web.Response(text="Bot is running safely with Multi-Platform Media Saver!")

async def start_web_server():
    port = int(os.getenv("PORT", 10000))
    try:
        app = web.Application()
        app.router.add_get('/', handle_root)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', port).start()
    except Exception as e:
        print(f"Web server port {port} ochilmadi (lokal rejimda bu normal): {e}")

async def main():
    await start_web_server()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        print(f"Webhook tozalashda xatolik: {e}")
    print("✅ Saver Bot muvaffaqiyatli ishga tushdi va xabarlarni qabul qilmoqda!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(main())