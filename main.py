import argparse
import os

import discord
from dotenv import load_dotenv

from Commands import COMMANDS
from MyDiscordClient import MyClient


def create_client(dev: bool) -> MyClient:
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    client = MyClient(
        intents=intents,
        allowed_mentions=discord.AllowedMentions(
            everyone=False,
            users=True,
            roles=True,
            replied_user=True,
        ),
        dev_mode=dev,
    )

    for command in COMMANDS:
        client.tree.add_command(command)

    return client


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AggieClassAlert Discord bot.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode (background tasks disabled).",
    )
    args = parser.parse_args()

    client = create_client(dev=args.dev)

    load_dotenv()
    client.run(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
