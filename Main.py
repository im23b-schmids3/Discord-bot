from discord import Intents
from typing import Final
import os
from dotenv import load_dotenv
from responses import Response
from discord.ext import commands


load_dotenv()

TOKEN: Final = os.getenv('DISCORD_TOKEN')

response_handler = Response()
intents = Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)


async def send_message(message, user_message):
    if not user_message:
        return
    try:
        response = response_handler.get_response(user_message)
        await message.channel.send(response)
    except Exception as e:
        print(f'Error: {e}')


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    await send_message(message, message.content)


def main():
    client.run(TOKEN)


if __name__ == '__main__':
    main()
