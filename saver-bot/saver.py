import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# Bot tokeningizni shu yerga yozing
API_TOKEN = '8747746960:AAFPVKsQ4o5gfbayRUlbOOQ_rXGGoY5hMJY'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Yuklab olingan videolarni vaqtincha saqlash uchun papka
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    start_text = (
        "🚀Salom! Menga ijtimoiy tarmoqdan video havolasini yuboring, men uni sizga yuklab beraman."
    )
    await message.answer(start_text, parse_mode="Markdown")

@dp.message(F.text.startswith("http"))
async def download_video(message: types.Message):
    url = message.text
    
    # Faqat bizga kerakli tarmoqlarni tekshirish (Endi Pinterest ham bor)
    allowed_domains = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be", "pinterest.com", "pin.it"]
    if not any(domain in url for domain in allowed_domains):
        await message.answer("⚠️ Xatolik!\n\nIltimos, yuborgan havolangizni tekshirib ko‘ring. Havola faqat Instagram, YouTube, TikTok yoki Pinterest tarmog‘iga tegishli bo‘lishi kerak. 🔄")
        return

    status_msg = await message.answer("⏳ Video tahlil qilinmoqda va yuklanmoqda... Iltimos, biroz kuting.")

    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'no_warnings': True,
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
        # Videoni foydalanuvchiga yuborish
        video_file = types.FSInputFile(filename)
        caption_text = "⚡️ @tezzzsaverbot orqali muvaffaqiyatli yuklab olindi!"
        
        await message.answer_video(video=video_file, caption=caption_text)
        await status_msg.delete()
        
        # Server joyini to'ldirmaslik uchun videoni o'chirish
        if os.path.exists(filename):
            os.remove(filename)
            
    except Exception as e:
        await status_msg.edit_text("❌ Videoni yuklab olishda xatolik yuz berdi. Havola yopiq profildan olingan yoki xato bo‘lishi mumkin.")
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())