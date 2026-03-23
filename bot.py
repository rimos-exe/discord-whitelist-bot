import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("⚠️ Discord token not set in environment variable 'DISCORD_TOKEN'")

GUILD_ID = discord.Object(id=1053841185694818414)

# Channel IDs
LOG_CHANNEL_ID = 1482425084990849218       # Staff log where buttons appear
ACCEPTED_CHANNEL_ID = 1481423477985644640  # Public "Congratulations" channel
DENIED_CHANNEL_ID = 1468666605188812913    # Channel for denial logs
INFO_LOG_CHANNEL_ID = 1468666603234267179  # Channel where full applicant info is stored
INTERVIEW_CHANNEL_ID = 1468666567607718140 # Interview voice/text channel

# Role IDs
STAFF_ROLE_ID = 1471815776783826975
WHITELIST_TEAM_ROLE_ID = 1471815776783826975
WHITELISTED_ROLE_ID = 1485673450411528355

# Branding
WHITELIST_IMAGE = "https://cdn.discordapp.com/attachments/1471892583474004018/1482428049541693471/WL.png"
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1471892583474004018/1484868157704503447/last_logo512.PNG"

# --- TRACK APPLICANTS ---
applied_users = set()

# --- DENY MODAL ---
class DenyModal(discord.ui.Modal, title="Deny Application"):
    reason = discord.ui.TextInput(
        label="Reason for denial",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300
    )

    def __init__(self, applicant, staff, message, view):
        super().__init__()
        self.applicant = applicant
        self.staff = staff
        self.message = message
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            denied_channel = interaction.guild.get_channel(DENIED_CHANNEL_ID)
            
            embed = discord.Embed(
                title="Application Denied ❌",
                color=discord.Color.red(),
                description=(
                    f"**Applicant:** {self.applicant.mention}\n"
                    f"**Denied by:** {self.staff.mention}\n"
                    f"**Reason:** {self.reason.value}"
                )
            )
            if denied_channel:
                await denied_channel.send(embed=embed)

            try:
                dm_embed = discord.Embed(
                    title="YBN DZ Whitelist Update",
                    description=f"Hello, your application was reviewed and unfortunately **denied**.",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Reason", value=self.reason.value)
                await self.applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            for item in self.view.children:
                if item.custom_id in ["accept_user", "deny_user"]:
                    item.disabled = True
            
            await self.message.edit(content=f"❌ Denied by {self.staff.name}", view=self.view)
            await interaction.response.send_message("Denied and DM sent.", ephemeral=True)
            applied_users.discard(self.applicant.id)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)

# --- STAFF ACTION VIEW ---
class StaffActionView(discord.ui.View):
    def __init__(self, applicant):
        super().__init__(timeout=None)
        self.applicant = applicant

    async def interaction_check(self, interaction: discord.Interaction):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Not allowed.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="accept_user")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            accepted_channel = interaction.guild.get_channel(ACCEPTED_CHANNEL_ID)
            info_log_channel = interaction.guild.get_channel(INFO_LOG_CHANNEL_ID)
            interview_channel = interaction.guild.get_channel(INTERVIEW_CHANNEL_ID)
            
            # --- AUTO ROLE ---
            whitelist_role = interaction.guild.get_role(WHITELISTED_ROLE_ID)
            if whitelist_role:
                try: await self.applicant.add_roles(whitelist_role)
                except: pass

            # --- EXTRACT DATA ---
            original_embed = interaction.message.embeds[0]
            real_name = original_embed.fields[1].value
            real_age = original_embed.fields[2].value
            experience = original_embed.fields[3].value
            steam_link = original_embed.fields[4].value
            invited_by = original_embed.fields[5].value

            # --- 1. CLEAN PUBLIC EMBED (TAGS INSIDE ONLY) ---
            congrats_embed = discord.Embed(
                title="APPLICATION ACCEPTED ✅",
                description=(
                    f"🎉 {self.applicant.mention} has been accepted to **YBN DZ**!\n\n"
                    f"**Welcome!** Please proceed to {interview_channel.mention if interview_channel else '#interview'} "
                    "for your final briefing.\n\n"
                    "> Check your DMs for your private invite link."
                ),
                color=discord.Color.green()
            )
            congrats_embed.set_thumbnail(url=THUMBNAIL_URL)
            congrats_embed.set_footer(text="YBN DZ Roleplay • Whitelist System", icon_url=THUMBNAIL_URL)
            
            if accepted_channel:
                # Removed 'content=' so no external tag/text is sent
                await accepted_channel.send(embed=congrats_embed)

            # --- 2. PRIVATE DATA LOG ---
            info_embed = discord.Embed(
                title="Detailed Applicant Info 📋",
                color=discord.Color.blue(),
                description=(
                    f"**Applicant:** {self.applicant.mention} ({self.applicant.id})\n"
                    f"**Accepted by:** {interaction.user.mention}\n\n"
                    f"**Real Name:** {real_name}\n"
                    f"**Age:** {real_age}\n"
                    f"**Experience:** {experience}\n"
                    f"**Steam:** {steam_link}\n"
                    f"**Invited By:** {invited_by}"
                )
            )
            if info_log_channel:
                await info_log_channel.send(embed=info_embed)

            # --- DMs ---
            try:
                invite = await interview_channel.create_invite(max_age=0, max_uses=0)
                await self.applicant.send(f"🎉 Congratulations! You were accepted.\nJoin the interview here: {invite.url}")
            except: pass

            # Disable Accept/Deny, keep Call Player
            for item in self.children:
                if item.custom_id in ["accept_user", "deny_user"]:
                    item.disabled = True
            
            await interaction.edit_original_response(content=f"✅ Processed by {interaction.user.name}", view=self)
            applied_users.discard(self.applicant.id)

        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_user")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DenyModal(self.applicant, interaction.user, interaction.message, self))

    @discord.ui.button(label="Call Player", style=discord.ButtonStyle.blurple, custom_id="call_player")
    async def call(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            interview_channel = interaction.guild.get_channel(INTERVIEW_CHANNEL_ID)
            invite = await interview_channel.create_invite(max_age=0, max_uses=0)
            await self.applicant.send(f"📢 Staff is calling you for your interview!\nJoin here: {invite.url}")
            await interaction.response.send_message(f"✅ Called {self.applicant.display_name}.", ephemeral=True)
        except:
            await interaction.response.send_message("⚠️ DMs locked.", ephemeral=True)

# --- APPLICATION FORM ---
class YBNDZModal(discord.ui.Modal, title='YBN DZ RolePlay Whitelist'):
    name_irl = discord.ui.TextInput(label='Real Name', placeholder='Enter your real name here', required=True)
    real_age = discord.ui.TextInput(label='Real Age', placeholder='Example: 18', min_length=1, max_length=2, required=True)
    experience = discord.ui.TextInput(label='Experience', style=discord.TextStyle.paragraph, placeholder='Your Experience in RP', required=True)
    steam_link = discord.ui.TextInput(label='Steam Link', style=discord.TextStyle.paragraph, placeholder='https://steamcommunity.com/id/yourprofile', required=True)
    story = discord.ui.TextInput(label='Invited By', style=discord.TextStyle.paragraph, placeholder='Who invited you / Username ?', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id in applied_users:
            await interaction.response.send_message("❌ You already submitted an application.", ephemeral=True)
            return

        applied_users.add(interaction.user.id)
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        
        if log_channel:
            embed = discord.Embed(title="📥 New Application | YBN DZ", color=discord.Color.dark_gray())
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="User", value=interaction.user.mention, inline=False)
            embed.add_field(name="Real Name", value=self.name_irl.value, inline=False)
            embed.add_field(name="Age", value=self.real_age.value, inline=False)
            embed.add_field(name="Experience", value=f"```{self.experience.value}```", inline=False)
            embed.add_field(name="Steam", value=f"```{self.steam_link.value}```", inline=False)
            embed.add_field(name="Invited By", value=f"```{self.story.value}```", inline=False)

            whitelist_role = interaction.guild.get_role(WHITELIST_TEAM_ROLE_ID)
            await log_channel.send(content=whitelist_role.mention if whitelist_role else "", embed=embed, view=StaffActionView(interaction.user))

        await interaction.response.send_message("✅ Your application has been sent to the staff!", ephemeral=True)

# --- APPLY BUTTON ---
class YBNView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='APPLY FOR WHITELIST', style=discord.ButtonStyle.green, custom_id='apply_btn', emoji='✅')
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(YBNDZModal())

# --- BOT ---
class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(YBNView())
        try:
            await self.tree.sync(guild=GUILD_ID)
        except Exception as e:
            print(f"⚠️ Error syncing commands: {e}")

bot = Bot()

# --- COMMANDS ---

@bot.tree.command(name="setup_ybn_whitelist", description="Post the YBN DZ Whitelist message", guild=GUILD_ID)
@app_commands.checks.has_permissions(administrator=True)
async def setup_ybn(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📝 YBN DZ Roleplay Whitelist",
        description=(
            "**Welcome! 👋**\n\n"
            "We’re glad to have you here. Please fill out the information below to apply.\n\n"
            "• **Name**\n• **Age**\n• **Experience**\n• **Steam Link**\n• **Invited By**\n\n"
            "> **Once accepted, you will receive an interview link.**"
        ),
        color=discord.Color.dark_gray()
    )
    embed.set_thumbnail(url=THUMBNAIL_URL)
    embed.set_image(url=WHITELIST_IMAGE)
    embed.set_footer(text="© Code by rimos.exe | discord.gg/ybndz", icon_url=THUMBNAIL_URL)

    await interaction.channel.send(embed=embed, view=YBNView())
    await interaction.response.send_message("Whitelist setup complete!", ephemeral=True)

@bot.tree.command(name="clear_applicant", description="Allow a user to apply again", guild=GUILD_ID)
@app_commands.checks.has_permissions(administrator=True)
async def clear_applicant(interaction: discord.Interaction, user: discord.Member):
    if user.id in applied_users:
        applied_users.discard(user.id)
        await interaction.response.send_message(f"✅ {user.mention} can now apply again.", ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ {user.mention} is not in the active applicant list.", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)