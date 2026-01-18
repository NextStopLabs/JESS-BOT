import io
import discord
from discord.ext import commands
from discord.utils import escape_mentions
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from datetime import datetime
from pydantic import BaseModel
import asyncio

router = APIRouter()

class ChannelRequest(BaseModel):
    title: str
    content: str = "Discussion started via API"

def setup_routes(bot, guild_id, forum_channel_id, bot_ready_event):
    @router.post("/create-thread")
    async def create_thread(request: ChannelRequest):
        await bot_ready_event.wait()

        guild = bot.get_guild(guild_id)
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild not found")

        forum_channel = guild.get_channel(forum_channel_id)
        if forum_channel is None or not isinstance(forum_channel, discord.ForumChannel):
            raise HTTPException(status_code=404, detail="Forum channel not found")

        # Escape mentions to prevent pings/abuse via the API
        safe_title = escape_mentions(request.title)
        safe_content = escape_mentions(request.content)

        result = await forum_channel.create_thread(name=safe_title, content=safe_content)

        if isinstance(result, tuple):
            thread, message = result
        else:
            thread = result
            message = None

        return {
            "thread_id": thread.id,
            "thread_name": thread.name,
            "forum_name": forum_channel.name,
            "first_message_id": message.id if message else None,
        }
    
    @router.post("/create-channel")
    async def create_channel(
        channel_name: str = Form(...),
        category_id: int = Form(...),
    ):
        await bot_ready_event.wait()

        guild = bot.get_guild(guild_id)
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild not found")

        category = guild.get_channel(category_id)
        if category is None or not isinstance(category, discord.CategoryChannel):
            raise HTTPException(status_code=404, detail="Category not found")

        channel = await category.create_text_channel(name=channel_name)

        return {
            "channel_id": channel.id,
            "channel_name": channel.name,
            "channel_type": channel.type,
        }
    
    @router.post("/delete-channel")
    async def delete_channel(
        channel_id: int = Form(...),
    ):
        await bot_ready_event.wait()

        guild = bot.get_guild(guild_id)
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild not found")

        channel = guild.get_channel(channel_id)
        if channel is None:
            raise HTTPException(status_code=404, detail="Channel not found")

        await channel.delete()

        return {
            "detail": f"Channel {channel_id} deleted successfully"
        }

    @router.post("/send-embed")
    async def send_embed(
        payload: dict = Body(...),
    ):
        """
        Accepts a JSON body like:
        {
            "channel_id": 123456789,
            "embed": {
                "title": "Example",
                "description": "An example embed",
                "color": 16776960,
                "fields": [
                    {"name": "Field 1", "value": "Value 1", "inline": True}
                ]
            }
        }
        """
        await bot_ready_event.wait()

        channel_id = payload.get("channel_id")
        embed_data = payload.get("embed")

        if not channel_id or not embed_data:
            raise HTTPException(status_code=400, detail="Missing 'channel_id' or 'embed' in JSON body")

        channel = bot.get_channel(channel_id)
        if channel is None:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Convert dict -> discord.Embed
        # Escape mentions in embed content to avoid accidental pings
        embed = discord.Embed(
            title=escape_mentions(embed_data.get("title")) if embed_data.get("title") else None,
            description=escape_mentions(embed_data.get("description")) if embed_data.get("description") else None,
            color=embed_data.get("color", 0x00BFFF)
        )

        # Add fields
        for field in embed_data.get("fields", []):
            name = field.get("name", "Unnamed Field")
            value = field.get("value", "—")
            embed.add_field(
                name=escape_mentions(name),
                value=escape_mentions(value),
                inline=field.get("inline", False)
            )

        # Add footer
        if "footer" in embed_data:
            footer_text = embed_data["footer"].get("text")
            if footer_text:
                embed.set_footer(text=escape_mentions(footer_text))

        # Add timestamp
        if "timestamp" in embed_data:
            try:
                embed.timestamp = datetime.fromisoformat(embed_data["timestamp"])
            except Exception:
                pass

        await channel.send(embed=embed)

        return {"status": "embed sent"}

    @router.post("/send-message-clean")
    async def send_message(
        channel_id: int = Form(...),
        message: str = Form(...),
        image: UploadFile = File(None)
    ):
        await bot_ready_event.wait()

        channel = bot.get_channel(channel_id)
        if channel is None:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Escape mentions to prevent pings
        content = f"{message}"
        content = escape_mentions(content)

        if image:
            file_data = await image.read()
            discord_file = discord.File(fp=io.BytesIO(file_data), filename=image.filename)
            await channel.send(content=content, file=discord_file)
        else:
            await channel.send(content=content)

        return {"status": "sent"}

    @router.post("/send-message")
    async def send_message(
        channel_id: int = Form(...),
        send_by: str = Form(...),
        message: str = Form(...),
        image: UploadFile = File(None)
    ):
        await bot_ready_event.wait()

        channel = bot.get_channel(channel_id)
        if channel is None:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Escape mentions in both sender and message
        content = f"**{send_by}:** {message}"
        content = escape_mentions(content)

        if image:
            file_data = await image.read()
            discord_file = discord.File(fp=io.BytesIO(file_data), filename=image.filename)
            await channel.send(content=content, file=discord_file)
        else:
            await channel.send(content=content)

        return {"status": "sent"}

    return router

@commands.Cog.listener()
async def on_ready(self):
    self.bot.bot_ready.set()
