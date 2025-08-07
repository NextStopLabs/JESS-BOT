import io
import discord
from discord.ext import commands
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import asyncio
from typing import Union

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

    @router.post("/send-message")
    async def send_message(
        channel_id: Union[int, str] = Form(...),
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
