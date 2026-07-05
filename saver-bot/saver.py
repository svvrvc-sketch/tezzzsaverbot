import yt_dlp
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

API_TOKEN = '8747746960:AAFPVKsQ4o5gfbayRUlbOOQ_rXGGoY5hMJY'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Videoning toza URL manzilini olish funksiyasi
def get_video_url(url):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False) # download=False -> Diskka yuklamaydi!
        
        # Agar bu playlist yoki ko'p formatli bo'lsa, toza urlni ajratamiz
        if 'url' in info:
            return info['url']
        elif 'formats' in info:
            return info['formats'][-1]['url']
        return None

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Salom! Menga ijtimoiy tarmoqdan video havolasini yuboring, men uni sizga yuklab beraman.")

@dp.message(F.text.regexp(r'(https?://[^\s]+)'))
async def handle_links(message: types.Message):
    url = message.text
    status_message = await message.reply("⏳ Havola tekshirilmoqda...")
    
    try:
        loop = asyncio.get_event_loop()
        # Videoning toza havolasini olamiz
        direct_video_url = await loop.run_in_executor(None, get_video_url, url)
        
        if direct_video_url:
            await status_message.edit_text("🚀 Telegram'ga yuklanmoqda...")
            # Telegramga to'g'ridan-to'g'ri URL orqali yuboramiz
            await message.reply_video(video=direct_video_url, caption="✨ Bepul bot orqali yuklandi!")
            await status_message.delete()
        else:
            await status_message.edit_text("❌ Videoni yuklash uchun havola topilmadi.")
            
    except Exception as e:
        await status_message.edit_text("❌ Xatolik: Havola noto'g'ri yoki bu ijtimoiy tarmoq hozircha qo'llab-quvvatlanmaydi.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())