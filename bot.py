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

# --- TRACK APPLICANTS TO PREVENT DOUBLE APPLICATION ---
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
            msg = f"📢 <@{self.applicant.id}> come for interview!"
            if interview_channel:
                msg += f"\nJoin {interview_channel.mention}"

            await self.applicant.send(msg)
            await interaction.response.send_message("Player called.", ephemeral=True)

        except:
            await interaction.response.send_message("Cannot DM user.", ephemeral=True)


# --- APPLICATION MODAL ---
class YBNDZModal(discord.ui.Modal, title='YBN DZ Whitelist'):

    name = discord.ui.TextInput(label='Name', required=True)
    age = discord.ui.TextInput(label='Age', required=True)
    exp = discord.ui.TextInput(label='Experience', style=discord.TextStyle.paragraph)
    steam = discord.ui.TextInput(label='Steam Link')
    invited = discord.ui.TextInput(label='Invited By')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id in applied_users:
                await interaction.response.send_message("❌ You have already applied.", ephemeral=True)
                return

            applied_users.add(interaction.user.id)

            log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
            if not log_channel:
                await interaction.response.send_message("❌ Log channel not found.", ephemeral=True)
                return

            role = interaction.guild.get_role(WHITELIST_TEAM_ROLE_ID)

            embed = discord.Embed(title="New Application", color=discord.Color.dark_gray())
            embed.add_field(name="User", value=interaction.user.mention)
            embed.add_field(name="Name", value=self.name.value)
            embed.add_field(name="Age", value=self.age.value)
            embed.add_field(name="Experience", value=self.exp.value, inline=False)
            embed.add_field(name="Steam", value=self.steam.value, inline=False)
            embed.add_field(name="Invited", value=self.invited.value, inline=False)

            await log_channel.send(
                content=role.mention if role else "",
                embed=embed,
                view=StaffActionView(interaction.user)
            )

            await interaction.response.send_message("✅ Sent!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)


# --- APPLY BUTTON WITH COOLDOWN ---
class YBNView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.cooldowns = {}

    @discord.ui.button(label='Apply', style=discord.ButtonStyle.green, custom_id='apply_btn')
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        # Anti-spam cooldown: 60 seconds
        if user_id in self.cooldowns:
            await interaction.response.send_message("⏳ Please wait before applying again.", ephemeral=True)
            return

        self.cooldowns[user_id] = True
        await interaction.response.send_modal(YBNDZModal())

        # Remove cooldown after 60 seconds
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


# --- COMMAND ---
@bot.tree.command(name="setup", guild=GUILD_ID)
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            description="Click below to apply",
            color=discord.Color.dark_gray()
        )
        embed.set_image(url=WHITELIST_IMAGE)

        await interaction.channel.send(embed=embed, view=YBNView())
        await interaction.response.send_message("Done", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Error: {e}", ephemeral=True)


bot.run(TOKEN)