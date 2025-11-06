from discord import app_commands
import discord
import os
import sys
import asyncio


description = """
Sends a message to the channel.
"""
@app_commands.command(name='say', description=description)
async def say(interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
    if interaction.user.id != interaction.client.application.owner.id:
        await interaction.response.send_message("You are not the owner of this bot!", ephemeral=True)
        return
    
    # Process the message to properly handle newlines
    processed_message = message.replace('\\n', '\n')
    
    await interaction.response.send_message("Sending message...", ephemeral=True)
    
    # Wait a moment to ensure the message is sent
    await asyncio.sleep(1)
    
    # Send the message to the channel with proper newlines
    await channel.send(processed_message)