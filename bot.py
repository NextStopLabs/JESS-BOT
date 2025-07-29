import os
import io
import discord
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import uvicorn
import asyncio
import httpx

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
FORUM_CHANNEL_ID = int(os.getenv("FORUM_CHANNEL_ID"))  # Forum channel ID now

# Discord bot setup
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot_ready = asyncio.Event()

# FastAPI app setup
app = FastAPI()

# API request model
class ChannelRequest(BaseModel):
    title: str
    content: str = "Discussion started via API"

@app.post("/create-thread")
async def create_thread(request: ChannelRequest):
    await bot_ready.wait()

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")

    forum_channel = guild.get_channel(FORUM_CHANNEL_ID)
    if forum_channel is None or not isinstance(forum_channel, discord.ForumChannel):
        raise HTTPException(status_code=404, detail="Forum channel not found")

    # Create thread (forum post)
    result = await forum_channel.create_thread(name=request.title, content=request.content)

    # Some forks return (thread, message), some return thread
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


@app.post("/send-message")
async def send_message(
    channel_id: int = Form(...),
    send_by: str = Form(...),
    message: str = Form(...),
    image: UploadFile = File(None)
):
    await bot_ready.wait()

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

@bot.event
async def on_ready():
    print(f"{bot.user} is connected!")
    bot_ready.set()

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    channel = message.channel

    payload = {
        "thread_channel_id": channel.id,
        "author": str(message.author),
        "content": message.content,
    }

    print(f"Sending message to Django API: {payload}")

    files = None
    if message.attachments:
        attachment = message.attachments[0]
        file_bytes = await attachment.read()
        files = {"image": (attachment.filename, file_bytes)}

    async with httpx.AsyncClient() as client:
        try:
            if files:
                response = await client.post(
                    "https://v2.mybustimes.cc/api/discord-message/",
                    data=payload,
                    files=files,
                )
            else:
                response = await client.post(
                    "https://v2.mybustimes.cc/api/discord-message/",
                    json=payload,
                )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send message to Django API: {e}")

    await bot.process_commands(message)

async def main():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await bot.start(TOKEN)
    await server_task

if __name__ == "__main__":
    asyncio.run(main())
