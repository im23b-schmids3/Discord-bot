from discord import Intents, Client
from typing import Final
import os
from dotenv import load_dotenv
from responses import get_response

load_dotenv()

TOKEN: Final = os.getenv('DISCORD_TOKEN')

intents = Intents.default()
intents.message_content = True
client = Client(intents=intents)


async def send_message(message, user_message):
    if not user_message:
        return
    try:
        response = get_response(user_message)
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
    client.run(token=TOKEN)


if __name__ == '__main__':
    main()
