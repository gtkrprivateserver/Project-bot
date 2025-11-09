import subprocess
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# File bot
BOT_UTAMA = "main.py"
BOT_RENT = "bot_rent.py"

def run_bot(file):
    return subprocess.Popen(["python", file])

if __name__ == "__main__":
    print("🚀 Menjalankan Bot Utama dan Bot Rent...")
    
    # Jalankan Bot Utama
    bot_utama_process = run_bot(BOT_UTAMA)
    print("✅ Bot Utama sedang berjalan.")

    # Jalankan Bot Rent
    bot_rent_process = run_bot(BOT_RENT)
    print("✅ Bot Rent sedang berjalan.")

    try:
        # Tunggu kedua bot berjalan
        bot_utama_process.wait()
        bot_rent_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 KeyboardInterrupt diterima, menghentikan bot...")
        bot_utama_process.terminate()
        bot_rent_process.terminate()
        print("✅ Kedua bot berhasil dihentikan.")
