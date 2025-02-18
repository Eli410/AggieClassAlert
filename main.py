import discord
import os
from dotenv import load_dotenv
from Commands import COMMANDS
from MyDiscordClient import MyClient


intents = discord.Intents.default()
intents.members = True
intents.message_content=True

client = MyClient(intents=intents, 
                  allowed_mentions=discord.AllowedMentions(everyone=False, 
                                                           users=True, 
                                                           roles=True, 
                                                           replied_user=True),
                  )


for command in COMMANDS:
    client.tree.add_command(command)

load_dotenv()
client.run(os.getenv('DISCORD_TOKEN'))
