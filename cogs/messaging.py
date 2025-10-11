import io
import discord
from discord.ext import commands
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
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

        result = await forum_channel.create_thread(name=request.title, content=request.content)

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

        content = f"{message}"

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

        content = f"**{send_by}:** {message}"

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
