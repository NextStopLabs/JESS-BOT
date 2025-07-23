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
CATEGORY_ID = int(os.getenv("FORUM_CATEGORY_ID"))

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

class MessageRequest(BaseModel):
    channel_id: int
    send_by: str
    message: str
    image: UploadFile = File(None)

@app.post("/create-channel")
async def create_channel(request: ChannelRequest):
    await bot_ready.wait()

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")

    category = guild.get_channel(CATEGORY_ID)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    # Create channel
    channel = await guild.create_text_channel(name=request.title, category=category)

    return {
        "channel_id": channel.id,
        "channel_name": channel.name,
        "category": category.name
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
    # Ignore messages from the bot itself to avoid loops
    if message.author == bot.user:
        return

    # Check if message is from a channel we track (has an associated Thread)
    channel = message.channel

    payload = {
        "thread_channel_id": channel.id,  # or use channel.id directly
        "author": str(message.author),
        "content": message.content,
    }

    print(f"Sending message to Django API: {payload}")

    # If there is an attachment, send it as well (optional)
    files = None
    if message.attachments:
        # Take first attachment as example
        attachment = message.attachments[0]
        file_bytes = await attachment.read()
        files = {"image": (attachment.filename, file_bytes)}

    async with httpx.AsyncClient() as client:
        try:
            if files:
                # multipart/form-data with files
                response = await client.post(
                    "http://localhost:8000/api/discord-message/",
                    data=payload,
                    files=files,
                )
            else:
                # JSON payload
                response = await client.post(
                    "http://localhost:8000/api/discord-message/",
                    json=payload,
                )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send message to Django API: {e}")

    # Also process commands if you use commands.Bot
    await bot.process_commands(message)


async def main():
    # Start FastAPI server in the background
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Start Discord bot
    await bot.start(TOKEN)

    # Wait for both tasks (if bot exits)
    await server_task

if __name__ == "__main__":
    asyncio.run(main())
