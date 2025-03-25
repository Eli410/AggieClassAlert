from discord import app_commands
import discord


description = """
Syncs the command tree for current server. Must be me to use.
"""

@app_commands.command(name='sync', description=description)
async def sync(interaction: discord.Interaction):
    if interaction.user.id != interaction.client.application.owner.id:
        await interaction.response.send_message("You are not the owner of this bot!", ephemeral=True)
        return
    guild = interaction.client.get_guild(interaction.guild_id)
    await interaction.response.send_message("Syncing...", ephemeral=True)
    commands = await interaction.client.tree.sync(guild=guild)
    await interaction.edit_original_response(content=f"Synced {guild.name}")

