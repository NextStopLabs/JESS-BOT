# cogs/vehicle_details.py

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import logging
from main import GUILD_ID
from urllib.parse import quote

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
        operator_name: str = '',
    ):
        await interaction.response.defer(thinking=True)

        url = (
            f"https://www.mybustimes.cc/api/operator/fleet/"
            f"?operator__operator_name={operator_name}&fleet_number={fleet_number}&reg={reg}&limit=10"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"Failed to fetch data (HTTP {resp.status})")
                        return

                    json_data = await resp.json()
        except Exception as e:
            logger.exception("Exception occurred while fetching vehicle details")
            await interaction.followup.send(f"An error occurred: {str(e)}")
            return

        results = json_data.get("results", [])
        if not results:
            await interaction.followup.send("No vehicle found with the given details.")
            return

        embeds = []
        for vehicle in results:

            # Build description based on provided search params
            description = "Result for"
            if reg:
                description += f", Reg: `{reg}`"
            if fleet_number:
                description += f", Fleet Number: `{fleet_number}`"
            if operator_name:
                description += f", Operator: `{operator_name}`"

            embed = discord.Embed(
                title="Vehicle Details",
                description=description,
                color=discord.Color.blue()
            )

            # Inline Group 1
            embed.add_field(name="Fleet Number", value=vehicle.get("fleet_number", "N/A"), inline=True)
            embed.add_field(name="Registration", value=vehicle.get("reg", "N/A"), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer

            # Inline Group 2
            vehicle_type = vehicle.get("vehicle_type_data", {})
            embed.add_field(name="Type Name", value=vehicle_type.get("type_name", "N/A"), inline=True)
            embed.add_field(name="Double Decker", value=str(vehicle_type.get("double_decker", "N/A")), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Inline Group 3
            embed.add_field(name="Type", value=vehicle_type.get("type", "N/A"), inline=True)
            embed.add_field(name="Fuel", value=vehicle_type.get("fuel", "N/A"), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Operator
            operator = vehicle.get("operator", {})
            
            # Link
            link = f"https://www.mybustimes.cc/operator/{operator.get('operator_slug', 'N/A')}/vehicles/{vehicle.get('id', 'N/A')}/"
            embed.add_field(name="More Info", value=f"[Click here]({link})", inline=False)

            embeds.append(embed)

        # Send all embeds — Discord has a limit of 10 embeds per message
        await interaction.followup.send(embeds=embeds[:10])


async def setup(bot):
    await bot.add_cog(VehicleDetails(bot))
