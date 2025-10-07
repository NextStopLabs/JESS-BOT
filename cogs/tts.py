import discord
from discord.ext import commands
import asyncio
import pyttsx3
import os

class TtsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tts_engine = pyttsx3.init()
        self.play_lock = asyncio.Lock()
        self.synced = False
        self.voice_client = None
        self.last_disconnect_time = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.manual_disconnect = False  # Flag to track manual disconnections
        self.connection_lock = asyncio.Lock()  # Prevent multiple simultaneous connections
        self.auto_reconnect_disabled = False  # Flag to completely disable auto-reconnect

    def get_voice_client(self):
        for vc in self.bot.voice_clients:
            if vc.guild.id == self.bot.GUILD_ID:
                return vc
        return None

    @discord.app_commands.command(name="join", description="Join your current voice channel")
    async def join(self, interaction: discord.Interaction):
        # Defer the response to prevent timeout
        await interaction.response.defer()
        
        async with self.connection_lock:  # Prevent multiple simultaneous connections
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("You are not connected to a voice channel!", ephemeral=False)
                return

            channel = interaction.user.voice.channel
            voice_client = self.get_voice_client()

            # Check if bot is already in the same channel
            if voice_client and voice_client.channel == channel and voice_client.is_connected():
                await interaction.followup.send(f"I'm already in {channel.name}!", ephemeral=False)
                return

            # Reset reconnection attempts and re-enable auto-reconnect when manually joining
            self.reconnect_attempts = 0
            self.auto_reconnect_disabled = False
            self.manual_disconnect = False  # This is a manual connection

            try:
                # Disconnect from current channel if connected
                if voice_client and voice_client.is_connected():
                    print(f"Disconnecting from {voice_client.channel} to move to {channel}")
                    self.manual_disconnect = True
                    await voice_client.disconnect(force=True)
                    await asyncio.sleep(2)  # Give more time for clean disconnection

                # Connect to the new channel
                print(f"Attempting to connect to {channel}")
                voice_client = await channel.connect()
                await interaction.followup.send(f"Joined {channel.name}!")

                # Update our reference
                self.voice_client = voice_client
                self.manual_disconnect = False

            except Exception as e:
                print(f"Error joining voice channel: {e}")
                await interaction.followup.send(f"Failed to join the voice channel: {str(e)}", ephemeral=False)

    @discord.app_commands.command(name="leave", description="Leave the current voice channel")
    async def leave(self, interaction: discord.Interaction):
        # Defer the response to prevent timeout
        await interaction.response.defer()
        
        voice_client = self.get_voice_client()
        
        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("I'm not connected to any voice channel!", ephemeral=False)
            return
        
        try:
            channel_name = voice_client.channel.name
            self.manual_disconnect = True  # Mark as manual disconnect
            await voice_client.disconnect(force=True)
            self.voice_client = None
            self.reconnect_attempts = 0  # Reset attempts
            self.auto_reconnect_disabled = False  # Re-enable for next manual join
            await interaction.followup.send(f"Left {channel_name}!")
        except Exception as e:
            print(f"Error leaving voice channel: {e}")
            await interaction.followup.send(f"Failed to leave the voice channel: {str(e)}", ephemeral=False)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Only handle bot's own voice state changes
        if member == self.bot.user:
            print(f"Voice state update: {member.display_name} moved from {before.channel} to {after.channel}")
            
            if after.channel is None:
                # Bot was disconnected from voice
                print("Bot got disconnected from voice.")
                
                if self.manual_disconnect:
                    print("This was a manual disconnect - not tracking as failure")
                    self.manual_disconnect = False
                    self.voice_client = None
                    return
                    
                self.voice_client = None
                self.last_disconnect_time = asyncio.get_event_loop().time()
                self.reconnect_attempts += 1
                
                # Do not automatically reconnect - only track disconnections
                print(f"Disconnection #{self.reconnect_attempts}. Not attempting automatic reconnection.")
                
                # If we get too many disconnections, disable auto-reconnect completely
                if self.reconnect_attempts >= 3:
                    self.auto_reconnect_disabled = True
                    print("AUTOMATIC RECONNECTION DISABLED due to repeated failures.")
                    print("This indicates a configuration issue. Please check:")
                    print("1. Bot has 'Connect' and 'Speak' permissions in the voice channel")
                    print("2. Voice channel is not full or restricted")
                    print("3. Bot is not being moved/kicked by server admins or bots")
                    print("4. Your Discord server doesn't have auto-moderation affecting voice")
                    print("\nUse /leave and then /join to try connecting again manually.")
                    
                    # Forcefully disconnect any remaining voice clients to stop the loop
                    for vc in self.bot.voice_clients:
                        if vc.guild.id == self.bot.GUILD_ID:
                            try:
                                print(f"Forcefully disconnecting from {vc.channel}")
                                await vc.disconnect(force=True)
                            except Exception as e:
                                print(f"Error forcing disconnect: {e}")
                    
                    return
                    
            elif before.channel != after.channel and after.channel is not None:
                # Bot moved to a different channel (successful connection)
                if self.auto_reconnect_disabled and not self.manual_disconnect:
                    print("BLOCKING automatic reconnection - auto-reconnect is disabled!")
                    print("Please use /leave and /join commands to control voice connection manually.")
                    # Disconnect immediately
                    try:
                        voice_client = self.get_voice_client()
                        if voice_client:
                            await voice_client.disconnect(force=True)
                    except Exception as e:
                        print(f"Error blocking reconnection: {e}")
                    return
                
                print(f"Bot successfully connected to {after.channel}")
                self.voice_client = self.get_voice_client()
            
            # Update our voice client reference
            self.voice_client = self.get_voice_client()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            await self.bot.tree.sync(guild=discord.Object(id=self.bot.GUILD_ID))
            self.synced = True
            print(f"Synced commands to guild {self.bot.GUILD_ID}!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or not message.guild:
            return

        voice_client = self.get_voice_client()
        if not voice_client or not voice_client.is_connected():
            return

        if message.content.startswith("/"):  # Ignore commands
            return

        self.voice_client = voice_client  # ensure voice_client is updated

        await self.read_tts(message.content)

    #async def read_tts(self, text):
    #    async with self.play_lock:
    #        try:
    #            filename = "tts_output.wav"
    #            self.tts_engine.save_to_file(text, filename)
    #            self.tts_engine.runAndWait()
#
    #            if self.voice_client and self.voice_client.is_playing():
    #                self.voice_client.stop()
#
    #            if self.voice_client and self.voice_client.is_connected():
    #                source = discord.FFmpegPCMAudio(filename)
    #                self.voice_client.play(source)
#
    #                while self.voice_client.is_playing():
    #                    await asyncio.sleep(0.1)
#
    #        except Exception as e:
    #            print(f"Error during TTS playback: {e}")
#
    #        finally:
    #            try:
    #                os.remove(filename)
    #            except Exception:
    #                pass

async def setup(bot):
    await bot.add_cog(TtsCog(bot))
