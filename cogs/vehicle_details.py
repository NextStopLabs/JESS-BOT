# cogs/vehicle_details.py

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from main import GUILD_ID

class VehicleDetails(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="vehicle-details", description="Search for vehicle details by reg, fleet number, or operator name.")
    @app_commands.describe(
        reg="The vehicle registration (optional)",
        fleet_number="The fleet number (optional)",
        operator_name="The operator name (optional)"
    )
    async def vehicle_details(
        self,
        interaction: discord.Interaction,
        reg: str = '',
        fleet_number: str = '',
        operator_name: str = ''
    ):
        await interaction.response.defer(thinking=True)

        url = (
            f"https://v2.mybustimes.cc/api/operator/fleet/"
            f"?operator__operator_name={operator_name}&fleet_number={fleet_number}&reg={reg}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Failed to fetch data (HTTP {resp.status})")
                    return

                data = await resp.json()

        if not data:
            await interaction.followup.send("No vehicle found with the given details.")
            return

        # Adjust this depending on the actual structure of your API response
        vehicle = data[0]  # Use the first result

        embed = discord.Embed(
            title="Vehicle Details",
            description=f"Search result for Reg: `{reg}`, Fleet Number: `{fleet_number}`, Operator: `{operator_name}`",
            color=discord.Color.blue()
        )

        for key, value in vehicle.items():
            embed.add_field(name=key.replace('_', ' ').title(), value=str(value), inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VehicleDetails(bot))
