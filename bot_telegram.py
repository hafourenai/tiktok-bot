# -*- coding: utf-8 -*-
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN, PUBLIC_DIR, MENU_IMAGE
from generate_menu import main as generate_menu

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MenuBot:
    def __init__(self):
        self.menu_path = os.path.join(PUBLIC_DIR, MENU_IMAGE)
        self.app = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_text = (
            "Selamat datang di Bot Menu!\n\n"
            "Cukup ketik:\n"
            "* menu nya apa saja?\n"
            "* apa menu hari ini?\n"
            "* menu\n\n"
            "Dan saya akan mengirimkan gambar menu tersedia"
        )
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "[PERINTAH]\n\n"
            "/start - Tampilkan pesan sambutan\n"
            "/help - Tampilkan bantuan ini\n"
            "/menu - Tampilkan menu gambar\n\n"
            "[ATAU KETIK]\n"
            "* menu nya apa saja?\n"
            "* menu apa saja?\n"
            "* apa menu?\n"
            "* menu hari ini?\n"
            "* menu\n"
        )
        await update.message.reply_text(help_text)
    
    async def handle_menu_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu request"""
        # Show typing indicator
        await update.message.chat.send_action("upload_photo")
        
        # Check if menu image exists
        if not os.path.exists(self.menu_path):
            print("[*] Menu image not found. Generating now...")
            generate_menu()
        
        # Send image if exists
        if os.path.exists(self.menu_path):
            try:
                with open(self.menu_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="[MENU TERSEDIA]\n\nSilakan pilih dari daftar di atas ^"
                    )
                logger.info(f"[OK] Menu sent to {update.effective_user.id}")
            except Exception as e:
                logger.error(f"[ERROR] Error sending photo: {e}")
                await update.message.reply_text(
                    "Maaf, terjadi kesalahan saat mengirim menu. Silakan coba lagi."
                )
        else:
            await update.message.reply_text(
                "Maaf, menu tidak tersedia saat ini. Silakan coba lagi nanti."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        if update.message.text is None:
            return
        
        text = update.message.text.lower().strip()
        
        # Keywords untuk trigger menu
        menu_keywords = [
            "menu nya apa saja",
            "menu apa saja",
            "apa menu",
            "menu hari ini",
            "menu",
        ]
        
        # Check if any keyword matches
        for keyword in menu_keywords:
            if keyword in text:
                await self.handle_menu_request(update, context)
                return
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
    
    def run(self):
        """Start the bot"""
        if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_token_here":
            print("[ERROR] Error: TELEGRAM_TOKEN not set in .env file")
            print("Please set TELEGRAM_TOKEN in .env and try again.")
            return
        
        # Create application
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("menu", self.handle_menu_request))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        self.app.add_error_handler(self.error_handler)
        
        print("="*50)
        print("[OK] Bot is running...")
        print("="*50)
        print("Press Ctrl+C to stop the bot\n")
        
        # Start polling
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    bot = MenuBot()
    bot.run()

if __name__ == "__main__":
    main()
