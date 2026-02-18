import os
import discord
from discord.ext import commands
import httpx
import requests
import logging
import traceback

# Basic logger for debug output; can be overridden by project logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ALLOWED_FORUM_IDS = [
    1473536551119228928,  # Forum forum
    1397600257398800496,  # V2 Bugs forum
    1374761374684676147,  # V2 Questions forum
    1349105620669698048,  # V2 Suggestions forum
    1351659604614058109,  # Company Updates
    1473516662945742996,  # General
    1390371616063750164,  # General Test
    1414748182675587203,  # Feedback
]

class ForumCog(commands.Cog):
    def __init__(self, bot, guild_id, forum_channel_id, bot_ready_event):
        self.bot = bot
        self.guild_id = guild_id
        self.forum_channel_id = forum_channel_id
        self.bot_ready = bot_ready_event

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot_ready.set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        channel = message.channel

        process_message = False
        thread_id = None
        forum_id = None

        # Case 1: Message is in a thread inside an allowed forum
        if isinstance(channel, discord.Thread):
            parent_id = channel.parent.id if channel.parent else None
            if parent_id in ALLOWED_FORUM_IDS:
                process_message = True
                thread_id = str(channel.id)
                forum_id = str(parent_id)

        elif isinstance(channel, discord.TextChannel):
            if channel.id in ALLOWED_FORUM_IDS:
                process_message = True
                thread_id = str(channel.id)
                forum_id = str(channel.id)
            else:

                # Check if a ticket exists and if so send the message to that ticket rather than the forum
                try:
                    response = requests.get(f"https://www.mybustimes.cc/api/tickets/?discord_channel_id={channel.id}")
                except Exception as e:
                    logger.exception("Synchronous ticket check failed for channel %s", channel.id)
                    response = None

                if response and response.status_code == 200:
                    ticket = response.json()

                    Username = os.getenv("Username")
                    Password = os.getenv("Password")
                    
                    async with httpx.AsyncClient() as client:
                        # Authenticate user via API key
                        auth_resp = await client.post(
                            "https://www.mybustimes.cc/api/user/",
                            json={"username": Username, "password": Password},
                            timeout=10.0
                        )
                        try:
                            auth_resp.raise_for_status()
                            key = auth_resp.json().get("session_key")
                        except Exception:
                            logger.exception("Authentication failed for API user %s", Username)
                            return

                        # Send message to ticket
                        ticket_resp = await client.get(f"https://www.mybustimes.cc/api/tickets/?discord_channel_id={channel.id}", timeout=10.0)
                        try:
                            ticket_resp.raise_for_status()
                            ticket = ticket_resp.json()
                        except Exception:
                            logger.exception("Failed to fetch ticket details for channel %s", channel.id)
                            ticket = None

                        ticket_msg_payload = {"content": message.content, "username": str(message.author)}
                        headers = {"Authorization": key}

                        files = {}
                        data = {"content": message.content, "sender_username": str(message.author)}

                        # If there is an attachment in Discord
                        if message.attachments:
                            attachment = message.attachments[0]
                            file_bytes = await attachment.read()
                            files = {"files": (attachment.filename, file_bytes, attachment.content_type)}
                        else:
                            files = {}

                        if ticket:
                            try:
                                ticket_post = await client.post(
                                    f"https://www.mybustimes.cc/api/key-auth/{ticket['id']}/messages/",
                                    data=data,
                                    files=files,
                                    headers=headers,
                                    timeout=10.0
                                )

                            except Exception:
                                logger.exception("Failed to POST message to ticket %s", ticket.get('id') if ticket else 'unknown')
                        else:
                            pass

        if process_message:
            async with httpx.AsyncClient() as client:
                check_response = await client.get(f"https://www.mybustimes.cc/api/check-thread/{thread_id}/")
                if check_response.status_code == 404:
                    create_payload = {
                        "discord_channel_id": thread_id,
                        "forum_id": forum_id,
                        "title": channel.name,
                        "created_by": str(message.author),
                        "first_post": message.content,
                    }
                    try:
                        create_resp = await client.post("https://www.mybustimes.cc/api/create-thread/", json=create_payload)
                    except Exception:
                        logger.exception("Failed to create thread for thread_id=%s forum_id=%s", thread_id, forum_id)
                else:
                    pass

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
                try:
                    if files:
                        resp = await client.post(
                            "https://www.mybustimes.cc/api/discord-message/",
                            data=payload,
                            files=files,
                        )
                    else:
                        resp = await client.post(
                            "https://www.mybustimes.cc/api/discord-message/",
                            json=payload,
                        )
                    
                    print(f"Sent message to forum thread {thread_id} by {str(message.author)} (status={resp.status_code})")
                except Exception:
                    logger.exception("Failed to send message to Django API for thread %s", thread_id)

        await self.bot.process_commands(message)

# This is the key fix: async setup function
async def setup(bot):
    guild_id = getattr(bot, "GUILD_ID", None)
    forum_channel_id = getattr(bot, "FORUM_CHANNEL_ID", None)
    bot_ready = getattr(bot, "bot_ready", None)

    if guild_id is None or forum_channel_id is None or bot_ready is None:
        raise ValueError("Bot missing required attributes: GUILD_ID, FORUM_CHANNEL_ID, or bot_ready")

    await bot.add_cog(ForumCog(bot, guild_id, forum_channel_id, bot_ready))
