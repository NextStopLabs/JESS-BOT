import discord
from discord.ext import commands
import httpx

class ForumCog(commands.Cog):
    def __init__(self, bot, guild_id, forum_channel_id, bot_ready_event):
        self.bot = bot
        self.guild_id = guild_id
        self.forum_channel_id = forum_channel_id
        self.bot_ready = bot_ready_event

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.bot.user} is connected!")
        self.bot_ready.set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        channel = message.channel

        if isinstance(channel, discord.Thread) and isinstance(channel.parent, discord.ForumChannel):
            thread_id = str(channel.id)

            async with httpx.AsyncClient() as client:
                check_response = await client.get(f"http://host.docker.internal:8000/api/check-thread/{thread_id}/")
                if check_response.status_code == 404:
                    create_payload = {
                        "discord_channel_id": thread_id,
                        "title": channel.name,
                        "created_by": str(message.author),
                        "first_post": message.content,
                    }
                    await client.post("http://host.docker.internal:8000/api/create-thread/", json=create_payload)

        payload = {
            "thread_channel_id": channel.id,
            "author": str(message.author),
            "content": message.content,
        }

        files = None
        if message.attachments:
            attachment = message.attachments[0]
            file_bytes = await attachment.read()
            files = {"image": (attachment.filename, file_bytes)}

        async with httpx.AsyncClient() as client:
            try:
                if files:
                    await client.post(
                        "http://host.docker.internal:8000/api/discord-message/",
                        data=payload,
                        files=files,
                    )
                else:
                    await client.post(
                        "http://host.docker.internal:8000/api/discord-message/",
                        json=payload,
                    )
            except Exception as e:
                print(f"Failed to send message to Django API: {e}")

        await self.bot.process_commands(message)

# This is the key fix: async setup function
async def setup(bot):
    guild_id = getattr(bot, "GUILD_ID", None)
    forum_channel_id = getattr(bot, "FORUM_CHANNEL_ID", None)
    bot_ready = getattr(bot, "bot_ready", None)

    if guild_id is None or forum_channel_id is None or bot_ready is None:
        raise ValueError("Bot missing required attributes: GUILD_ID, FORUM_CHANNEL_ID, or bot_ready")

    await bot.add_cog(ForumCog(bot, guild_id, forum_channel_id, bot_ready))
