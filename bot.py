import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta
import os
import asyncio
from flask import Flask
from waitress import serve
from threading import Thread
import pytz

# ==================== Environment ====================
TOKEN_MAIN = os.getenv("DISCORD_TOKEN")
ADMIN_IDS = [int(a) for a in os.getenv("ADMIN_IDS", "").split(",") if a]
UPLOAD_CHANNEL_ID = int(os.getenv("UPLOAD_CHANNEL_ID", 0))
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", 0))
BRIDGE_CHANNEL_ID = int(os.getenv("BRIDGE_CHANNEL_ID", 0))

# ==================== Bot & Intents ====================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== Flask App ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_server():
    serve(app, host='0.0.0.0', port=8080)

Thread(target=run_server).start()

# ==================== State ====================
active_users = set()  # user yang sudah approve connect ke bot rent

# ==================== Decorator ====================
from functools import wraps

def admin_only(func):
    @wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        if interaction.user.id not in ADMIN_IDS:
            await interaction.response.send_message("❌ Hanya admin yang bisa menggunakan command ini.", ephemeral=True)
            return
        return await func(interaction, *args, **kwargs)
    return wrapper

# ==================== /start Command ====================
@bot.tree.command(name="start", description="Connect ke Bot Rent")
async def start_cmd(interaction: discord.Interaction):
    view = View()
    button = Button(label="Connect ke Security Rent", style=discord.ButtonStyle.primary)

    async def button_callback(bi: discord.Interaction):
        class ConnectModal(Modal, title="Form Connect ke Bot Rent"):
            full_name = TextInput(label="Nama Lengkap")
            discord_name = TextInput(label="Nama Discord")

            async def on_submit(self, modal_interaction: discord.Interaction):
                for aid in ADMIN_IDS:
                    admin = bot.get_user(aid)
                    if admin:
                        admin_view = View()
                        approve_btn = Button(label="✅ Setuju", style=discord.ButtonStyle.success)
                        deny_btn = Button(label="❌ Tolak", style=discord.ButtonStyle.danger)

                        async def approve_callback(bi2):
                            active_users.add(modal_interaction.user.id)
                            # Kirim ke bridge channel Bot Rent
                            bridge_channel = bot.get_channel(BRIDGE_CHANNEL_ID)
                            if bridge_channel:
                                await bridge_channel.send(f"__connect__:{modal_interaction.user.id}")
                            await modal_interaction.user.send("✅ Connect ke Bot Rent disetujui admin.")
                            await bi2.response.send_message("✅ User disetujui.", ephemeral=True)

                        async def deny_callback(bi2):
                            await modal_interaction.user.send("❌ Connect ke Bot Rent ditolak admin.")
                            await bi2.response.send_message("❌ User ditolak.", ephemeral=True)

                        approve_btn.callback = approve_callback
                        deny_btn.callback = deny_callback
                        admin_view.add_item(approve_btn)
                        admin_view.add_item(deny_btn)

                        await admin.send(
                            f"📩 Permintaan Connect Bot Rent dari {modal_interaction.user.mention}\nNama: {self.full_name.value}\nDiscord: {self.discord_name.value}",
                            view=admin_view
                        )
                await modal_interaction.response.send_message("✅ Form terkirim ke admin.", ephemeral=True)

        await bi.response.send_modal(ConnectModal())

    button.callback = button_callback
    view.add_item(button)
    await interaction.response.send_message("Klik tombol untuk connect ke Security Rent!", view=view, ephemeral=True)

# ==================== /upload Command ====================
class UploadView(View):
    def __init__(self, user: discord.User, timeout=60):
        super().__init__(timeout=timeout)
        self.user = user

    @discord.ui.button(label="Kirim File/Video", style=discord.ButtonStyle.primary)
    async def upload_button(self, button: Button, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Hanya pengguna yang memulai bisa klik tombol.", ephemeral=True)
            return

        await interaction.response.send_message("📤 Silakan kirim file/video dalam 60 detik...", ephemeral=True)

        def check(m):
            return m.author == self.user and (m.attachments or m.content)

        try:
            msg = await bot.wait_for("message", timeout=60, check=check)
            for aid in ADMIN_IDS:
                admin = bot.get_user(aid)
                if admin:
                    files = [await a.to_file() for a in msg.attachments]
                    embed = discord.Embed(
                        title="📥 Upload File/Video",
                        description=f"Dari {self.user.mention}",
                        color=discord.Color.green()
                    )
                    await admin.send(embed=embed, files=files)
            await interaction.followup.send("✅ File berhasil dikirim ke admin!", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Waktu upload habis, silakan coba lagi.", ephemeral=True)

@bot.tree.command(name="upload", description="Upload file/video ke admin")
async def upload_cmd(interaction: discord.Interaction):
    if interaction.channel.id != UPLOAD_CHANNEL_ID:
        await interaction.response.send_message("⚠️ Gunakan /upload hanya di channel khusus!", ephemeral=True)
        return
    view = UploadView(interaction.user)
    await interaction.response.send_message("📤 Upload aktif, klik tombol di bawah.", view=view, ephemeral=True)

# ==================== /report Command ====================
@bot.tree.command(name="report", description="Kirim laporan ke admin")
async def report_cmd(interaction: discord.Interaction):
    if interaction.channel.id != REPORT_CHANNEL_ID:
        await interaction.response.send_message("⚠️ Gunakan /report hanya di channel laporan!", ephemeral=True)
        return

    class ReportModal(Modal, title="Form Laporan Profesional"):
        laporan = TextInput(label="Isi laporan")

        async def on_submit(self, modal_interaction: discord.Interaction):
            embed = discord.Embed(
                title="📢 Laporan Baru",
                description=f"Dari {interaction.user.mention}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Isi Laporan", value=self.laporan.value, inline=False)
            for aid in ADMIN_IDS:
                admin = bot.get_user(aid)
                if admin:
                    await admin.send(embed=embed)
            await modal_interaction.response.send_message("✅ Laporan terkirim ke admin!", ephemeral=True)

    await interaction.response.send_modal(ReportModal())

# ==================== /about Command ====================
@bot.tree.command(name="about", description="Info Bot Utama")
async def about_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Utama",
        description="Bot utama untuk manajemen connect ke Bot Rent, upload, dan laporan.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== /help Command ====================
@bot.tree.command(name="help", description="Deskripsi commands Bot Utama")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Help Bot Utama", color=discord.Color.blue())
    embed.add_field(name="/start", value="Connect ke Bot Rent", inline=False)
    embed.add_field(name="/upload", value="Upload file/video ke admin", inline=False)
    embed.add_field(name="/report", value="Kirim laporan ke admin", inline=False)
    embed.add_field(name="/about", value="Info bot utama", inline=False)
    embed.add_field(name="/help", value="Deskripsi commands", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== /status Command ====================
@bot.tree.command(name="status", description="Cek user yang connect ke Bot Rent")
@admin_only
async def status_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📡 Active Users Bot Rent", color=discord.Color.orange())
    if active_users:
        embed.description = "\n".join([f"<@{uid}>" for uid in active_users])
    else:
        embed.description = "Belum ada user yang connect."
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== on_ready ====================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot Utama online: {bot.user}")

# ==================== Run Bot ====================
bot.run(TOKEN_MAIN)