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
COOLDOWN_DURATION = 1  # 1 seconds cooldown

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
    
    # Check bot permissions
    permissions = voice_channel.permissions_for(ctx.guild.me)
    if not permissions.connect or not permissions.speak:
        await ctx.send("Ich habe keine Berechtigung, diesem Sprachkanal beizutreten oder zu sprechen!")
        return
    
    # Disconnect from any existing connection to avoid session conflicts
    if ctx.voice_client:
        await ctx.voice_client.disconnect(force=True)
        await asyncio.sleep(1)  # Wait for clean disconnect
    
    # Verbinde mit Sprachkanal, falls nicht schon verbunden
    try:
        voice_client = await voice_channel.connect(timeout=10.0, reconnect=True)
        await asyncio.sleep(0.5)  # Small delay for connection stability
    except discord.ClientException as e:
        if "already connected" in str(e).lower():
            await ctx.send("Bot ist bereits mit einem Sprachkanal verbunden.")
            return
        logging.error(f"Client error during voice connection: {e}")
        await ctx.send(f"Fehler beim Verbinden: {e}")
        return
    except asyncio.TimeoutError:
        await ctx.send("Verbindung zum Sprachkanal ist fehlgeschlagen (Timeout).")
        return
    except Exception as e:
        logging.error(f"Voice connection failed: {e}")
        await ctx.send(f"Fehler beim Verbinden mit Sprachkanal: {e}")
        return

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
        
        # Updated yt-dlp options to handle nsig extraction issues
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'extract_flat': 'in_playlist',
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'opus',
            'logtostderr': False,
            'ignoreerrors': True,
            'source_address': '0.0.0.0',  # Bind to ipv4 since ipv6 addresses cause issues sometimes
            'prefer_ffmpeg': True,
            'cachedir': False,
            'youtube_include_dash_manifest': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                
                # Try multiple audio URL extraction methods
                audio_url = None
                if 'url' in info:
                    audio_url = info['url']
                elif 'formats' in info:
                    # Filter for audio-only formats first
                    audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                    if audio_formats:
                        audio_url = audio_formats[0]['url']
                    else:
                        # Fallback to any format with audio
                        audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                        if audio_formats:
                            audio_url = audio_formats[0]['url']
                
                if not audio_url:
                    raise Exception("No suitable audio format found")
                
                # Get video title and webpage URL for better display
                video_title = info.get('title', 'Unknown Title')
                webpage_url = info.get('webpage_url', url)
                
            # Use FFMPEG with better options for stability
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn -filter:a "volume=0.5"'
            }
            source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
            
        except Exception as e:
            logging.error(f"Error extracting audio: {e}")
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
                    if '4006' in str(error) or 'voice connection' in str(error).lower():
                        connection_failures[ctx.guild.id] += 1
                        if connection_failures[ctx.guild.id] >= 3:
                            logging.info("Repeated connection errors. Reconnecting to voice channel.")
                            asyncio.run_coroutine_threadsafe(reconnect_and_retry(ctx, url), bot_loop)
                            connection_failures[ctx.guild.id] = 0
                            return
                    else:
                        connection_failures[ctx.guild.id] = 0
                else:
                    connection_failures[ctx.guild.id] = 0
                asyncio.run_coroutine_threadsafe(after_song(ctx), bot_loop)
            else:
                print("No event loop available for after_playback!")

        try:
            ctx.voice_client.play(source, after=after_playback)
            # Send YouTube link instead of just song name
            await ctx.send(f" Spielt jetzt: **{video_title}**\n {webpage_url}")
        except Exception as e:
            logging.error(f"Error starting playback: {e}")
            await ctx.send(f"Fehler beim Starten der Wiedergabe: {e}")
            await play_next(ctx)
    else:
        # Keine weiteren Songs, nach 10 Sekunden disconnecten
        await asyncio.sleep(10)
        if ctx.voice_client and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()
            song_queue[ctx.guild.id].clear()


async def reconnect_and_retry(ctx, url):
    """Reconnect to voice channel and retry playing"""
    try:
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await asyncio.sleep(2)  # Wait before reconnecting
        await join_and_play(ctx, url)
    except Exception as e:
        logging.error(f"Reconnection failed: {e}")
        await ctx.send("Verbindung fehlgeschlagen. Bitte versuche es erneut.")


async def after_song(ctx):
    await play_next(ctx)


@client.command()
async def play(ctx, *, search: str):
    """Plays a song from YouTube. Use !play <song name or YouTube link>"""
    # Check cooldown - silently ignore if on cooldown
    if not check_cooldown(ctx.author.id, 'play'):
        return
    
    # Enhanced user validation
    if not ctx.author.voice:
        await ctx.send("Du musst in einem Sprachkanal sein!")
        return
    
    if not ctx.author.voice.channel:
        await ctx.send("Du bist nicht in einem gültigen Sprachkanal!")
        return
    
    # Check if bot can join the channel
    voice_channel = ctx.author.voice.channel
    permissions = voice_channel.permissions_for(ctx.guild.me)
    if not permissions.connect:
        await ctx.send("Ich habe keine Berechtigung, diesem Sprachkanal beizutreten!")
        return
    if not permissions.speak:
        await ctx.send("Ich habe keine Berechtigung, in diesem Sprachkanal zu sprechen!")
        return
    
    # Check if it's a YouTube link
    if 'youtube.com/watch' in search or 'youtu.be/' in search:
        url = search
    else:
        # Search on YouTube with updated options
        ydl_opts = {
            'format': 'bestaudio', 
            'noplaylist': True, 
            'quiet': True, 
            'default_search': 'ytsearch1',
            'no_warnings': True,
            'source_address': '0.0.0.0',
            'youtube_include_dash_manifest': False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search, download=False)
                if not info['entries']:
                    await ctx.send("Kein Song gefunden!")
                    return
                url = info['entries'][0]['webpage_url']
        except Exception as e:
            logging.error(f"YouTube search error: {e}")
            await ctx.send(f"Fehler bei der YouTube-Suche: {e}")
            return
    
    already_playing = ctx.voice_client and ctx.voice_client.is_playing()
    
    try:
        await join_and_play(ctx, url)
        if already_playing:
            await ctx.send(f"Ein Song läuft bereits. '{search}' wurde zur Warteschlange hinzugefügt.")
        
        # Queue anzeigen
        queue = song_queue[ctx.guild.id]
        if queue:
            await ctx.send(f"Aktuelle Warteschlange: {len(queue)} Song(s)")
    except Exception as e:
        logging.error(f"Error in play command: {e}")
        await ctx.send("Ein Fehler ist aufgetreten. Bitte versuche es erneut.")


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
        await ctx.voice_client.disconnect(force=True)
        song_queue[ctx.guild.id].clear()
        connection_failures[ctx.guild.id] = 0  # Reset connection failures
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
    
    # Disconnect from any voice channels on startup to avoid session conflicts
    for guild in client.guilds:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
    
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
