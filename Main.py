from discord import Intents
from typing import Final
import os
from dotenv import load_dotenv
from responses import Response
from discord.ext import commands

# Load environment variables from the .env file
load_dotenv()

# Retrieve the Discord bot token from environment variables
TOKEN: Final = os.getenv('DISCORD_TOKEN')

# Initialize the custom response handler
response_handler = Response()

# Set up bot intents to allow message content access
intents = Intents.default()
intents.message_content = True  # Enable reading message content
client = commands.Bot(command_prefix="!", intents=intents)


# Function to handle sending messages based on user input
async def send_message(message, user_message):
    if not user_message:
        return
    try:
        response = response_handler.get_response(user_message)  # Generate a response
        await message.channel.send(response)  # Send the response to the channel
    except Exception as e:
        print(f'Error: {e}')  # Log any errors


# Event triggered when the bot is ready and connected to Discord
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')


# Event triggered when a new message is sent in a channel
@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Ignore bot's own messages
    await send_message(message, message.content)  # Process user message


# Main function to run the bot using the provided token
def main():
    client.run(TOKEN)


if __name__ == '__main__':
    main()
