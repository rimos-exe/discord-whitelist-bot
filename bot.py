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

LOG_CHANNEL_ID = 1482425084990849218
ACCEPTED_CHANNEL_ID = 1481423477985644640
DENIED_CHANNEL_ID = 1468666605188812913

INTERVIEW_CHANNEL_ID = 1468666567607718140
STAFF_ROLE_ID = 1471815776783826975
WHITELIST_TEAM_ROLE_ID = 1471815776783826975

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
            if not denied_channel:
                await interaction.response.send_message("❌ Denied channel not found.", ephemeral=True)
                return

            embed = discord.Embed(
                title="Application Denied ❌",
                color=discord.Color.red(),
                description=(
                    f"**Applicant:** {self.applicant.mention}\n"
                    f"**Denied by:** {self.staff.mention}\n"
                    f"**Reason:** {self.reason.value}"
                )
            )

            await denied_channel.send(embed=embed)

            for item in self.view.children:
                if item.custom_id in ["accept_user", "deny_user"]:
                    item.disabled = True

            await self.message.edit(
                content=f"❌ Denied by {self.staff.name}",
                view=self.view
            )

            await interaction.response.send_message("Denied.", ephemeral=True)
            applied_users.discard(self.applicant.id)

        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)


# --- STAFF BUTTONS ---
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
            interview_channel = interaction.guild.get_channel(INTERVIEW_CHANNEL_ID)

            if not accepted_channel:
                await interaction.followup.send("❌ Accepted channel not found.", ephemeral=True)
                return

            msg = f"🎉 {self.applicant.mention} accepted by {interaction.user.mention}"
            if interview_channel:
                msg += f"\nJoin {interview_channel.mention}"
            await accepted_channel.send(msg)

            if interview_channel:
                try:
                    invite = await interview_channel.create_invite(max_age=0, max_uses=0)
                    await self.applicant.send(
                        f"🎉 Congratulations! Your application was accepted.\n"
                        f"Click here to join your interview: {invite.url}"
                    )
                except discord.Forbidden:
                    await accepted_channel.send(
                        f"⚠️ Could not DM {self.applicant.mention}. They might have DMs disabled."
                    )

            for item in self.children:
                if item.custom_id in ["accept_user", "deny_user"]:
                    item.disabled = True

            await interaction.edit_original_response(
                content=f"✅ Accepted by {interaction.user.name}",
                view=self
            )
            applied_users.discard(self.applicant.id)

        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_user")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(DenyModal(self.applicant, interaction.user, interaction.message, self))
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)

    @discord.ui.button(label="Call Player", style=discord.ButtonStyle.blurple, custom_id="call_player")
    async def call(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            interview_channel = interaction.guild.get_channel(INTERVIEW_CHANNEL_ID)
            if not interview_channel:
                await interaction.response.send_message("❌ Interview channel not found.", ephemeral=True)
                return

            try:
                invite = await interview_channel.create_invite(max_age=0, max_uses=0)
                await self.applicant.send(
                    f"📢 Staff is calling you for your YBN DZ whitelist interview!\n"
                    f"Join here: {invite.url}"
                )
                await interaction.response.send_message(
                    f"✅ {self.applicant.mention} has been called via DM.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"⚠️ Cannot DM {self.applicant.mention}.",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)


# --- APPLICATION FORM ---
class YBNDZModal(discord.ui.Modal, title='YBN DZ RolePlay Whitelist'):

    name_irl = discord.ui.TextInput(
        label='Real Name',
        placeholder='Enter your real name here',
        required=True
    )

    real_age = discord.ui.TextInput(
        label='Real Age',
        placeholder='Example: 18',
        min_length=1,
        max_length=2,
        required=True
    )

    experience = discord.ui.TextInput(
        label='Experience',
        style=discord.TextStyle.paragraph,
        placeholder='Your Experience in RP',
        required=True
    )

    steam_link = discord.ui.TextInput(
        label='Steam Link',
        style=discord.TextStyle.paragraph,
        placeholder='https://steamcommunity.com/id/yourprofile',
        required=True
    )

    story = discord.ui.TextInput(
        label='Invited By',
        style=discord.TextStyle.paragraph,
        placeholder='Who invited you / Username ?',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id in applied_users:
            await interaction.response.send_message(
                "❌ You already submitted an application.", ephemeral=True
            )
            return

        applied_users.add(interaction.user.id)

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="📥 New Application | YBN DZ",
                color=discord.Color.dark_gray()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="User", value=interaction.user.mention, inline=False)
            embed.add_field(name="Real Name", value=self.name_irl.value, inline=False)
            embed.add_field(name="Age", value=self.real_age.value, inline=False)
            embed.add_field(name="Experience", value=f"```{self.experience.value}```", inline=False)
            embed.add_field(name="Steam", value=f"```{self.steam_link.value}```", inline=False)
            embed.add_field(name="Invited By", value=f"```{self.story.value}```", inline=False)

            whitelist_role = interaction.guild.get_role(WHITELIST_TEAM_ROLE_ID)
            await log_channel.send(content=whitelist_role.mention if whitelist_role else "", embed=embed, view=StaffActionView(interaction.user))

        await interaction.response.send_message(
            "✅ Your application has been sent to the staff!",
            ephemeral=True
        )


# --- APPLY BUTTON WITH COOLDOWN ---
class YBNView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.cooldowns = {}

    @discord.ui.button(
        label='APPLY FOR WHITELIST', 
        style=discord.ButtonStyle.green, 
        custom_id='apply_btn',
        emoji='✅'
    )
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in self.cooldowns:
            await interaction.response.send_message("⏳ Please wait before applying again.", ephemeral=True)
            return

        self.cooldowns[user_id] = True
        await interaction.response.send_modal(YBNDZModal())

        async def remove_cooldown():
            await asyncio.sleep(60)
            self.cooldowns.pop(user_id, None)
        
        asyncio.create_task(remove_cooldown())


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

# --- SETUP COMMAND ---
@bot.tree.command(
    name="setup_ybn_whitelist",
    description="Post the YBN DZ Whitelist message",
    guild=GUILD_ID
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_ybn(interaction: discord.Interaction):
    # Back to a single embed for a clean, unified look
    embed = discord.Embed(
        title="📝 YBN DZ Roleplay Whitelist",
        description=(
            "**Welcome! 👋**\n\n"
            "We’re glad to have you here. Please fill out the information below to apply for access to the server.\n\n"
            "• **Name**\n"
            "• **Age**\n"
            "• **Experience**\n"
            "• **Steam Link**\n"
            "• **Invited By**\n\n"
            "> **Once accepted, you will receive an interview link.**"
        ),
        color=discord.Color.dark_gray()
    )
    
    # Adding branding inside the same frame
    embed.set_thumbnail(url=THUMBNAIL_URL)
    embed.set_image(url=WHITELIST_IMAGE)
    
    embed.set_footer(
        text="© Code by rimos.exe | discord.gg/ybndz", 
        icon_url=THUMBNAIL_URL 
    )

    # Send as one message with the button directly below it
    await interaction.channel.send(embed=embed, view=YBNView())
    await interaction.response.send_message("Whitelist setup complete!", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)