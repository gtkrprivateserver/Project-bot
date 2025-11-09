import discord
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, View, Button
from datetime import datetime, timedelta
import os
import pytz
from functools import wraps
import asyncio

# ==================== Environment ====================
TOKEN_RENT = os.getenv("DISCORD_TOKEN_RENT")
BOT_CLIENT_ID = os.getenv("BOT_CLIENT_ID")
OWNER_CONTACT = os.getenv("OWNER_CONTACT", "https://discord.com/users/OWNER_ID")
ADMIN_IDS = [int(a) for a in os.getenv("ADMIN_IDS", "").split(",") if a]
BRIDGE_CHANNEL_ID = int(os.getenv("BRIDGE_CHANNEL_ID", 0))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== State ====================
active_users = set()   # user yang sudah verifikasi di Bot Utama
approved_users = {}    # user_id : expire_time
muted_users = {}       # user_id : unmute_time

# ==================== Decorators ====================
def connected_only(func):
    @wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        if interaction.user.id not in active_users:
            await interaction.response.send_message(
                "❌ Anda belum verifikasi di Bot Utama. Gunakan /start dan Connect ke Security Rent.",
                ephemeral=True
            )
            return
        return await func(interaction, *args, **kwargs)
    return wrapper

def approved_only(func):
    @wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        if interaction.user.id not in approved_users:
            await interaction.response.send_message(
                "❌ Anda belum disetujui admin. Tunggu konfirmasi admin.",
                ephemeral=True
            )
            return
        return await func(interaction, *args, **kwargs)
    return wrapper

# ==================== Unmute Loop ====================
@tasks.loop(minutes=1)
async def unmute_check():
    now = datetime.utcnow()
    for uid, t in list(muted_users.items()):
        if now >= t:
            muted_users.pop(uid, None)
            user = bot.get_user(uid)
            if user:
                await user.send("✅ Mute 1 hari selesai. Anda bisa mencoba /rent lagi.")

# ==================== Bridge Listener dari Bot Utama ====================
async def bridge_listener():
    await bot.wait_until_ready()
    channel = bot.get_channel(BRIDGE_CHANNEL_ID)
    if not channel:
        print("❌ Channel bridge Bot Rent tidak ditemukan")
        return
    while not bot.is_closed():
        try:
            msg = await bot.wait_for("message", check=lambda m: m.channel.id == BRIDGE_CHANNEL_ID)
            if msg.author.bot and msg.content.startswith("__connect__:"):
                user_id = int(msg.content.split(":")[1])
                active_users.add(user_id)
                user = bot.get_user(user_id)
                if user:
                    await user.send("✅ Security Rent aktif! Sekarang Anda bisa menggunakan /rent.")
        except Exception as e:
            print(f"Error bridge_listener: {e}")

# ==================== /rent Command ====================
@bot.tree.command(name="rent", description="Form sewa Bot Rent")
@connected_only
async def rent_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in muted_users:
        await interaction.response.send_message("❌ Anda sedang diblok 1 hari.", ephemeral=True)
        return

    class RentModal(Modal, title="Form Sewa Bot Rent Profesional"):
        full_name = TextInput(label="Nama Lengkap")
        discord_name = TextInput(label="Nama Discord")
        server_link = TextInput(label="Link Server")
        price = TextInput(label="Harga Penyewa")
        sewa_hari = TextInput(label="Hari Sewa (contoh: 7)")

        async def on_submit(self, modal_interaction: discord.Interaction):
            try:
                hari_sewa = int(self.sewa_hari.value)
            except:
                hari_sewa = 7
            expire_time = datetime.utcnow() + timedelta(days=hari_sewa)

            await modal_interaction.user.send(embed=discord.Embed(
                title="✅ Security Rent Aktif",
                description="Tunggu persetujuan admin.",
                color=discord.Color.green()
            ))

            for aid in ADMIN_IDS:
                admin = bot.get_user(aid)
                if admin:
                    view = View()

                    async def approve_callback(bi: discord.Interaction):
                        approved_users[user_id] = expire_time
                        oauth_view = View()

                        oauth_btn = Button(
                            label="Tambahkan Bot",
                            style=discord.ButtonStyle.link,
                            url=f"https://discord.com/oauth2/authorize?client_id={BOT_CLIENT_ID}&scope=bot&permissions=8"
                        )
                        oauth_view.add_item(oauth_btn)

                        status_btn = Button(label="Cek Status Bot Rent", style=discord.ButtonStyle.primary)
                        async def status_callback(bi_status: discord.Interaction):
                            embed = discord.Embed(title="📡 Status Bot Rent", color=discord.Color.orange())
                            expire_time2 = approved_users.get(user_id)
                            embed.add_field(name="Expire", value=expire_time2.strftime("%Y-%m-%d %H:%M:%S UTC"))
                            await bi_status.response.send_message(embed=embed, ephemeral=True)
                        status_btn.callback = status_callback
                        oauth_view.add_item(status_btn)

                        contact_btn = Button(label="Contact Owner", style=discord.ButtonStyle.secondary)
                        async def contact_callback(bi_contact: discord.Interaction):
                            mentions = " ".join([f"<@{aid}>" for aid in ADMIN_IDS])
                            await bi_contact.response.send_message(f"📩 Hubungi admin: {mentions}\nLink: {OWNER_CONTACT}", ephemeral=True)
                        contact_btn.callback = contact_callback
                        oauth_view.add_item(contact_btn)

                        await modal_interaction.user.send(
                            embed=discord.Embed(
                                title="✅ Sewa Disetujui",
                                description=f"Sewa aktif sampai {expire_time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                                color=discord.Color.green()
                            ),
                            view=oauth_view
                        )
                        await bi.response.send_message("✅ User disetujui.", ephemeral=True)

                    async def deny_callback(bi: discord.Interaction):
                        muted_users[user_id] = datetime.utcnow() + timedelta(days=1)
                        await modal_interaction.user.send(embed=discord.Embed(
                            title="❌ Sewa Ditolak",
                            description="Diblok 1 hari.",
                            color=discord.Color.red()
                        ))
                        await bi.response.send_message("❌ User ditolak.", ephemeral=True)

                    btn_approve = Button(label="✅ Setuju", style=discord.ButtonStyle.success)
                    btn_approve.callback = approve_callback
                    btn_deny = Button(label="❌ Tolak", style=discord.ButtonStyle.danger)
                    btn_deny.callback = deny_callback
                    view.add_item(btn_approve)
                    view.add_item(btn_deny)

                    embed = discord.Embed(title="📩 Permintaan Sewa Bot Rent", color=discord.Color.orange())
                    embed.add_field(name="Nama", value=self.full_name.value, inline=False)
                    embed.add_field(name="Discord", value=self.discord_name.value, inline=False)
                    embed.add_field(name="Server", value=self.server_link.value, inline=False)
                    embed.add_field(name="Harga", value=self.price.value, inline=False)
                    embed.add_field(name="Hari Sewa", value=self.sewa_hari.value, inline=False)
                    await admin.send(embed=embed, view=view)

            await modal_interaction.response.send_message("✅ Form terkirim ke admin.", ephemeral=True)

    await interaction.response.send_modal(RentModal())

# ==================== /status Command ====================
@bot.tree.command(name="status", description="Cek status bot rent")
@connected_only
@approved_only
async def status_cmd(interaction: discord.Interaction):
    expire_time = approved_users.get(interaction.user.id)
    embed = discord.Embed(title="📡 Status Bot Rent", color=discord.Color.orange())
    embed.add_field(name="User Approved", value="✅ Ya", inline=True)
    embed.add_field(name="Expire", value=expire_time.strftime("%Y-%m-%d %H:%M:%S UTC") if expire_time else "-", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== /help Command ====================
@bot.tree.command(name="help", description="Deskripsi commands Bot Rent")
@connected_only
@approved_only
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Help Bot Rent", color=discord.Color.blue())
    embed.add_field(name="/rent", value="Form sewa bot rent", inline=False)
    embed.add_field(name="/status", value="Cek status sewa", inline=False)
    embed.add_field(name="/help", value="Deskripsi commands", inline=False)
    embed.add_field(name="/about", value="Info bot rent", inline=False)
    embed.add_field(name="/pay", value="Instruksi pembayaran sewa", inline=False)
    embed.add_field(name="/paysuccess", value="Upload bukti pembayaran", inline=False)
    embed.add_field(name="/time", value="Waktu Indonesia sekarang", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== /about Command ====================
@bot.tree.command(name="about", description="Info Bot Rent")
@connected_only
@approved_only
async def about_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Rent",
        description="Bot untuk menyewa bot dengan Oauth2 link setelah disetujui admin.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== /pay Command ====================
@bot.tree.command(name="pay", description="Instruksi pembayaran sewa")
@connected_only
@approved_only
async def pay_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "💰 Kirim pembayaran ke admin sesuai instruksi.", ephemeral=True
    )

# ==================== /paysuccess Command ====================
@bot.tree.command(name="paysuccess", description="Upload bukti pembayaran")
@connected_only
@approved_only
async def paysuccess_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📤 Silahkan upload file/video sebagai bukti pembayaran.", ephemeral=True
    )

# ==================== /time Command ====================
@bot.tree.command(name="time", description="Waktu Indonesia sekarang")
@connected_only
async def time_cmd(interaction: discord.Interaction):
    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.now(tz)
    await interaction.response.send_message(f"🕒 Waktu Indonesia: {now.strftime('%Y-%m-%d %H:%M:%S')}", ephemeral=True)

# ==================== /admin Command ====================
@bot.tree.command(name="admin", description="Admin Panel Bot Rent")
async def admin_cmd(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ Hanya admin yang bisa menggunakan.", ephemeral=True)
        return

    view = View()
    ban_btn = Button(label="Ban User", style=discord.ButtonStyle.danger)
    leave_btn = Button(label="Leave Bot dari Server", style=discord.ButtonStyle.secondary)

    async def ban_callback(bi: discord.Interaction):
        await bi.response.send_message("🔨 Fitur Ban user aktif (admin action).", ephemeral=True)

    async def leave_callback(bi: discord.Interaction):
        await bi.response.send_message("🚪 Bot telah keluar dari server.", ephemeral=True)

    ban_btn.callback = ban_callback
    leave_btn.callback = leave_callback
    view.add_item(ban_btn)
    view.add_item(leave_btn)

    await interaction.response.send_message("🛠 Admin Panel", view=view, ephemeral=True)

# ==================== Bot Ready ====================
@bot.event
async def on_ready():
    await bot.tree.sync()
    unmute_check.start()
    bot.loop.create_task(bridge_listener())
    print(f"✅ Bot Rent online: {bot.user}")

# ==================== Run Bot ====================
bot.run(TOKEN_RENT)