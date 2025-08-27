import os
import random
import discord
from discord.ext import commands

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", 0))

# Path to your images folder
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "images")

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send a welcome message with a random image from local storage."""
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            print(f"Channel with ID {WELCOME_CHANNEL_ID} not found.")
            return

        # Pick a random image from the folder
        images = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
        if not images:
            await channel.send(f"Welcome {member.mention}! (no images found in {IMAGES_DIR})")
            return

        chosen_image = random.choice(images)
        file_path = os.path.join(IMAGES_DIR, chosen_image)

        # Create embed
        embed = discord.Embed(
            title="Welcome To MBT",
            description=f"Glad to have you here, {member.mention}!",
            color=discord.Color.blue()
        )
        file = discord.File(file_path, filename=chosen_image)
        embed.set_image(url=f"attachment://{chosen_image}")

        await channel.send(content=f"Welcome {member.mention}!", embed=embed, file=file)

async def setup(bot):
    await bot.add_cog(FunCog(bot))
