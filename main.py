import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from cogs.forum import ForumCog
from cogs.messaging import setup_routes

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
FORUM_CHANNEL_ID = int(os.getenv("FORUM_CHANNEL_ID"))

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.voice_states = True


bot = commands.Bot(command_prefix="!", intents=intents)
bot_ready = asyncio.Event()

app = FastAPI()

async def main():
    bot.GUILD_ID = GUILD_ID
    bot.FORUM_CHANNEL_ID = FORUM_CHANNEL_ID
    bot.bot_ready = bot_ready

    # Load only the actual discord cog
    await bot.load_extension("cogs.forum")
    await bot.load_extension("cogs.tts")
    await bot.load_extension("cogs.vehicle_details")


    # Add FastAPI routes manually
    app.include_router(setup_routes(bot, GUILD_ID, FORUM_CHANNEL_ID, bot_ready))

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await bot.start(TOKEN)
    await server_task

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands for guild {GUILD_ID}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    bot.bot_ready.set()


if __name__ == "__main__":
    asyncio.run(main())