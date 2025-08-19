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
import time
import logging

# Load environment variables from the .env file
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Retrieve the Discord bot token from environment variables
TOKEN: Final = os.getenv('DISCORD_TOKEN')

# Initialize the custom response handler
response_handler = Response()

# Set up bot intents to allow message content access
intents = Intents.default()
intents.message_content = True  # Enable reading message content
client = commands.Bot(command_prefix="!", intents=intents)

song_queue = defaultdict(list)
bot_loop = None
connection_failures = defaultdict(int)

# Cooldown dictionary to track last command usage per user
command_cooldowns = defaultdict(dict)
COOLDOWN_DURATION = 5  # 5 seconds cooldown

def check_cooldown(user_id: int, command: str) -> bool:
    """Check if a user can use a command based on cooldown"""
    current_time = time.time()
    last_used = command_cooldowns[user_id].get(command, 0)
    
    if current_time - last_used < COOLDOWN_DURATION:
        return False
    
    command_cooldowns[user_id][command] = current_time
    return True

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
        if ctx.voice_client is None:
            await ctx.send("Bot is not connected to voice. Rejoining…")
            await join_and_play(ctx, url)
            return
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
                # Get video title and webpage URL for better display
                video_title = info.get('title', 'Unknown Title')
                webpage_url = info.get('webpage_url', url)
            source = await discord.FFmpegOpusAudio.from_probe(audio_url, method='fallback')
        except Exception as e:
            await ctx.send(f"Fehler beim Abspielen: {e}")
            await play_next(ctx)
            return
        if ctx.voice_client is None:
            await ctx.send("Bot is not connected to voice. Rejoining…")
            await join_and_play(ctx, url)
            return

        def after_playback(error):
            global bot_loop
            if bot_loop is not None:
                if error:
                    logging.error(f"Fehler beim Abspielen: {error}")
                    if '4006' in str(error):
                        connection_failures[ctx.guild.id] += 1
                        if connection_failures[ctx.guild.id] >= 3:
                            logging.info("Repeated 4006 errors. Reconnecting to voice channel.")
                            asyncio.run_coroutine_threadsafe(join_and_play(ctx, url), bot_loop)
                            connection_failures[ctx.guild.id] = 0
                            return
                    else:
                        connection_failures[ctx.guild.id] = 0
                else:
                    connection_failures[ctx.guild.id] = 0
                asyncio.run_coroutine_threadsafe(after_song(ctx), bot_loop)
            else:
                print("No event loop available for after_playback!")

        ctx.voice_client.play(source, after=after_playback)
        # Send YouTube link instead of just song name
        await ctx.send(f" Spielt jetzt: **{video_title}**\n {webpage_url}")
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
    # Check cooldown - silently ignore if on cooldown
    if not check_cooldown(ctx.author.id, 'play'):
        return
    
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Du musst in einem Sprachkanal sein!")
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
                    await ctx.send("Kein Song gefunden!")
                    return
                url = info['entries'][0]['webpage_url']
        except Exception as e:
            await ctx.send(f"Fehler bei der YouTube-Suche: {e}")
            return
    already_playing = ctx.voice_client and ctx.voice_client.is_playing()
    await join_and_play(ctx, url)
    if already_playing:
        await ctx.send(f"Ein Song läuft bereits. '{search}' wurde zur Warteschlange hinzugefügt.")
    
    # Queue anzeigen
    queue = song_queue[ctx.guild.id]
    if queue:
        await ctx.send(f"Aktuelle Warteschlange: {len(queue)} Song(s)")


@client.command()
async def skip(ctx):
    """Skips the current song."""
    # Check cooldown - silently ignore if on cooldown
    if not check_cooldown(ctx.author.id, 'skip'):
        return
    
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Song übersprungen.")
        # Queue anzeigen
        queue = song_queue[ctx.guild.id]
        if queue:
            await ctx.send(f"Aktuelle Warteschlange: {len(queue)} Song(s)")
        else:
            await ctx.send("Warteschlange ist leer.")
    else:
        await ctx.send("Aktuell wird kein Song abgespielt.")


@client.command()
async def stop(ctx):
    """Stops playback and leaves the voice channel."""
    # Check cooldown - silently ignore if on cooldown
    if not check_cooldown(ctx.author.id, 'stop'):
        return
    
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        song_queue[ctx.guild.id].clear()
        await ctx.send("Wiedergabe gestoppt und Sprachkanal verlassen.")
    else:
        await ctx.send("Ich bin nicht in einem Sprachkanal.")


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
    global bot_loop
    bot_loop = asyncio.get_event_loop()
    print(f'{client.user} has connected to Discord!')


# Event triggered when a new message is sent in a channel
@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Ignore bot's own messages
    
    # Check cooldown for non-music commands
    if not message.content.lower().startswith(('!play', '!skip', '!stop')):
        # Check cooldown for other commands - silently ignore if on cooldown
        if not check_cooldown(message.author.id, 'general'):
            return
        
        await send_message(message, message.content)  # Process user message
    
    await client.process_commands(message)


# Main function to run the bot using the provided token
def main():
    client.run(TOKEN)


if __name__ == '__main__':
    main()
