from discord import app_commands
import discord
import os
import sys
import asyncio

description = """
Restarts the bot. Must be me to use.
"""

@app_commands.command(name='restart', description=description)
async def restart(interaction: discord.Interaction):
    if interaction.user.id != interaction.client.application.owner.id:
        await interaction.response.send_message("You are not the owner of this bot!", ephemeral=True)
        return
    await interaction.response.send_message("Restarting...", ephemeral=True)
    
    # Wait a moment to ensure the message is sent
    await asyncio.sleep(1)
    
    # Restart the program
    print("Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)
