import os
import discord
from discord.ext import commands
import httpx
import requests

ALLOWED_FORUM_IDS = [
    1399863670581891222,  # Forum forum
    1397600257398800496,  # V2 Bugs forum
    1374761374684676147,  # V2 Questions forum
    1349105620669698048,  # V2 Suggestions forum
    1351659604614058109,  # Company Updates
    1348465750926430249,  # General
    1390371616063750164,  # General Test
]

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
        print(f"Received message: {message.content} in channel {message.channel.id}")
        if message.author == self.bot.user:
            return

        channel = message.channel

        process_message = False
        thread_id = None
        forum_id = None

        print(f"Processing message in channel: {channel.id} ({channel.name})")

        # Case 1: Message is in a thread inside an allowed forum
        print(isinstance(channel, discord.Thread))
        if isinstance(channel, discord.Thread):
            parent_id = channel.parent.id if channel.parent else None
            if parent_id in ALLOWED_FORUM_IDS:
                process_message = True
                thread_id = str(channel.id)
                forum_id = str(parent_id)

        elif isinstance(channel, discord.TextChannel):
            print(f"TextChannel detected. ID in allowed list? {channel.id in ALLOWED_FORUM_IDS}")
            if channel.id in ALLOWED_FORUM_IDS:
                print("✅ Text channel allowed, processing message")
                process_message = True
                thread_id = str(channel.id)
                forum_id = str(channel.id)
            else:

                # Check if a ticket exists and if so send the message to that ticket rather than the forum
                response = requests.get(f"https://www.mybustimes.cc/api/tickets/?discord_channel_id={channel.id}")

                print(f"Response status code: {response.status_code}")

                if response.status_code == 200:
                    ticket = response.json()
                    print(f"✅ Found existing ticket: {ticket}")

                    Username = os.getenv("Username")
                    Password = os.getenv("Password")
                    
                    async with httpx.AsyncClient() as client:
                        # Authenticate user via API key
                        auth_resp = await client.post(
                            "https://www.mybustimes.cc/api/user/",
                            json={"username": Username, "password": Password},
                            timeout=10.0
                        )
                        auth_resp.raise_for_status()
                        key = auth_resp.json()["session_key"]

                        # Send message to ticket
                        ticket_resp = await client.get(f"https://www.mybustimes.cc/api/tickets/?discord_channel_id={channel.id}", timeout=10.0)
                        ticket_resp.raise_for_status()
                        ticket = ticket_resp.json()

                        ticket_msg_payload = {"content": message.content, "username": str(message.author)}
                        headers = {"Authorization": key}

                        files = {}
                        data = {"content": message.content, "username": str(message.author)}

                        # If there is an attachment in Discord
                        if message.attachments:
                            for i, attachment in enumerate(message.attachments):
                                file_bytes = await attachment.read()
                                files[f"file{i}"] = (attachment.filename, file_bytes, attachment.content_type)

                        await client.post(
                            f"https://www.mybustimes.cc/api/key-auth/{ticket['id']}/messages/",
                            data=data,
                            files=files,
                            headers=headers,
                            timeout=10.0
                        )

                else:
                    print("❌ Text channel not in allowed list")

        if process_message:
            print(f"Processing message for thread ID: {thread_id} and forum ID: {forum_id}")
            async with httpx.AsyncClient() as client:
                check_response = await client.get(f"https://www.mybustimes.cc/api/check-thread/{thread_id}/")
                print(f"Check response status code: {check_response.status_code}")
                if check_response.status_code == 404:
                    create_payload = {
                        "discord_channel_id": thread_id,
                        "forum_id": forum_id,
                        "title": channel.name,
                        "created_by": str(message.author),
                        "first_post": message.content,
                    }
                    print(f"Creating new thread with payload: {create_payload}")
                    await client.post("https://www.mybustimes.cc/api/create-thread/", json=create_payload)
                    print(f"Created new thread: {create_payload}")

                payload = {
                    "thread_channel_id": thread_id,
                    "forum_id": forum_id,
                    "author": str(message.author),
                    "content": message.content,
                }

            files = None
            if message.attachments:
                attachment = message.attachments[0]
                file_bytes = await attachment.read()
                files = {"image": (attachment.filename, file_bytes)}

            async with httpx.AsyncClient() as client:
                print(f"Sending message to Django API: {payload}")
                try:
                    if files:
                        print(f"Sending message with attachment to Django API: {payload}")
                        await client.post(
                            "https://www.mybustimes.cc/api/discord-message/",
                            data=payload,
                            files=files,
                        )
                        print(f"Sent message with attachment to Django API: {payload}")
                    else:
                        print(f"Sending message without attachment to Django API: {payload}")
                        await client.post(
                            "https://www.mybustimes.cc/api/discord-message/",
                            json=payload,
                        )
                        print(f"Sent message without attachment to Django API: {payload}")
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
