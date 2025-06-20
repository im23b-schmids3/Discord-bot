from discord import Intents
from typing import Final
import os
from dotenv import load_dotenv
from responses import Response
from discord.ext import commands
import asyncio
import yt_dlp
import discord
from collections import defaultdict

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

song_queue = defaultdict(list)

async def join_and_play(ctx, url):
    voice_channel = ctx.author.voice.channel
    # Verbinde mit Sprachkanal, falls nicht schon verbunden
    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    # Song zur Warteschlange hinzufügen
    song_queue[ctx.guild.id].append(url)
    if not ctx.voice_client.is_playing():
        await play_next(ctx)

async def play_next(ctx):
    if song_queue[ctx.guild.id]:
        url = song_queue[ctx.guild.id].pop(0)
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'extract_flat': 'in_playlist',
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                audio_url = info['url'] if 'url' in info else info['formats'][0]['url']
            source = await discord.FFmpegOpusAudio.from_probe(audio_url, method='fallback')
        except Exception as e:
            await ctx.send(f"Fehler beim Abspielen: {e}")
            await play_next(ctx)
            return
        def after_playback(error):
            fut = asyncio.run_coroutine_threadsafe(after_song(ctx), asyncio.get_event_loop())
            if error:
                print(f"Fehler beim Abspielen: {error}")
        ctx.voice_client.play(source, after=after_playback)
    else:
        # Keine weiteren Songs, nach 10 Sekunden disconnecten
        await asyncio.sleep(10)
        if not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()
            song_queue[ctx.guild.id].clear()

async def after_song(ctx):
    await play_next(ctx)

@client.command()
async def play(ctx, *, search: str):
    """Plays a song from YouTube. Use !play <song name or YouTube link>"""
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("You must be in a voice channel!")
        return
    # Check if it's a YouTube link
    if 'youtube.com/watch' in search or 'youtu.be/' in search:
        url = search
    else:
        # Search on YouTube
        ydl_opts = {'format': 'bestaudio', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch1'}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search, download=False)
                if not info['entries']:
                    await ctx.send("No song found!")
                    return
                url = info['entries'][0]['webpage_url']
        except Exception as e:
            await ctx.send(f"Error during YouTube search: {e}")
            return
    await join_and_play(ctx, url)
    await ctx.send(f"Now playing: {search}")

@client.command()
async def skip(ctx):
    """Skips the current song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Song skipped.")
    else:
        await ctx.send("No song is currently playing.")

@client.command()
async def stop(ctx):
    """Stops playback and leaves the voice channel."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        song_queue[ctx.guild.id].clear()
        await ctx.send("Playback stopped and left the voice channel.")
    else:
        await ctx.send("I'm not in a voice channel.")

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
    await client.process_commands(message)

# Main function to run the bot using the provided token
def main():
    client.run(TOKEN)


if __name__ == '__main__':
    main()
