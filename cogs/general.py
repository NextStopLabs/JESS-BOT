import discord
from discord import app_commands
from discord.ext import commands
import os
import httpx
from main import GUILD_ID

guild_id = GUILD_ID


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.badge_choices = []
        self.allowed_user_ids = {
            int(uid.strip())
            for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
            if uid.strip().isdigit()
        }

    async def fetch_badges(self):
        """Fetch the list of available badges from the API."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://www.mybustimes.cc/api/all-available-badges/")
                resp.raise_for_status()
                data = resp.json()
                badges = data.get("badges", [])
                self.badge_choices = [
                    app_commands.Choice(name=b["badge_name"], value=b["badge_name"])
                    for b in badges
                ]
        except Exception as e:
            print(f"⚠️ Failed to fetch badges: {e}")
            self.badge_choices = [app_commands.Choice(name="Error loading badges", value="Error")]

    @app_commands.guilds(discord.Object(id=guild_id))
    @app_commands.command(name="badge", description="Gives a selected user a badge on the site.")
    @app_commands.describe(
        user="The username of the user to give the badge to",
        badge_name="Select a badge to give"
    )
    async def badge(
        self,
        interaction: discord.Interaction,
        user: str,
        badge_name: str,
        give: bool = True
    ):
        # Restrict access
        if interaction.user.id not in self.allowed_user_ids:
            await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=False)
            return

        await interaction.response.defer(thinking=True, ephemeral=False)

        username = os.getenv("Username")
        password = os.getenv("Password")

        if not username or not password:
            await interaction.followup.send("❌ Missing credentials in environment variables.")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Authenticate
                auth_resp = await client.post(
                    "https://www.mybustimes.cc/api/user/",
                    json={"username": username, "password": password},
                )
                auth_resp.raise_for_status()
                key = auth_resp.json().get("session_key")

                if not key:
                    await interaction.followup.send("❌ Failed to retrieve session key.")
                    return

                # Give badge
                resp = await client.post(
                    "https://www.mybustimes.cc/api/user/add_badge/",
                    json={"session_key": key, "badge": badge_name, "user": user, "give": give},
                )

            if resp.status_code == 200:
                await interaction.followup.send(
                    f"✅ Successfully {'given' if give else 'removed'} **{user}** the badge '**{badge_name}**'."
                )
            elif resp.status_code in (401, 403):
                await interaction.followup.send("❌ Unauthorized. Check your credentials or permissions.")
            elif resp.status_code == 404:
                await interaction.followup.send(f"❌ Badge '{badge_name}' or user '{user}' not found.")
            else:
                await interaction.followup.send(
                    f"❌ Failed to give badge. Status: {resp.status_code}\nResponse: {resp.text}"
                )

        except httpx.HTTPStatusError as e:
            await interaction.followup.send(f"❌ HTTP error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            await interaction.followup.send(f"❌ Request failed: {e}")
        except Exception as e:
            await interaction.followup.send(f"❌ Unexpected error: {e}")

    # 🔽 Attach autocomplete for the badge_name field
    @badge.autocomplete("badge_name")
    async def badge_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.badge_choices:
            await self.fetch_badges()
        return [
            choice for choice in self.badge_choices if current.lower() in choice.name.lower()
        ][:25]  # Discord only supports 25 max


    @app_commands.guilds(discord.Object(id=guild_id))
    @app_commands.command(name="github-issue", description="Create a new GitHub issue on MyBusTimes repo.")
    @app_commands.describe(
        title="Short title of the issue",
        body="Detailed description of the issue"
    )
    async def github_issue(
        self,
        interaction: discord.Interaction,
        title: str,
        body: str
    ):
        """Creates a GitHub issue in the MyBusTimes repo."""
        # Restrict access
        if interaction.user.id not in self.allowed_user_ids:
            await interaction.response.send_message(
                "❌ You are not authorized to use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        github_token = os.getenv("GITHUB_ISSUE_PK")
        if not github_token:
            await interaction.followup.send("❌ Missing GitHub token in environment variables.")
            return

        api_url = "https://api.github.com/repos/NestStopLabs/MyBusTimes/issues"

        payload = {
            "title": title,
            "body": f"{body}\n\n— Created by **{interaction.user}** via Discord",
        }

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "MyBusTimesBot",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(api_url, json=payload, headers=headers)

            if resp.status_code == 201:
                issue_data = resp.json()
                await interaction.followup.send(
                    f"✅ Issue created successfully!\n🔗 {issue_data['html_url']}"
                )
            elif resp.status_code == 401:
                await interaction.followup.send("❌ Unauthorized. Check your GitHub token.")
            else:
                await interaction.followup.send(
                    f"❌ Failed to create issue.\nStatus: {resp.status_code}\nResponse: {resp.text}"
                )

        except httpx.RequestError as e:
            await interaction.followup.send(f"❌ Request failed: {e}")
        except Exception as e:
            await interaction.followup.send(f"❌ Unexpected error: {e}")


async def setup(bot):
    cog = GeneralCog(bot)
    await cog.fetch_badges()  # Fetch badges at startup
    await bot.add_cog(cog)
