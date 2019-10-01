import discord
from discord.ext import commands, tasks


import asyncio
import itertools
import json
import traceback
import youtube_dl
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL, utils
from random import shuffle
from typing import Optional

youtube_dl.utils.bug_reports_message = lambda: ''

ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
    'before_options': '-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = YoutubeDL(ytdlopts)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()
        async with ctx.channel.typing():
            to_run = partial(ytdl.extract_info, url=search, download=download)
            data = await loop.run_in_executor(None, to_run)
        # data is a dict, but entries is a list of dicts
        print(data)
        if data is None:
            print('here1')
            return await ctx.send('A fatal error has occurred.')

        if 'entries' in data and len(data['entries']) == 1:
            print('134')
            data = data['entries'][0]
        elif 'entries' in data:
            print('2')

            out = []
            async with ctx.channel.typing():
                for vid in data['entries']:
                    if vid is not None:
                        out.append({'webpage_url': vid['webpage_url'], 'requester': ctx.author, 'title': vid['title']})
                await ctx.send(f'Adding {len(out)} songs to queue...')
            return out
        print('3')
        await ctx.send(f'```ini\n[Added {data["title"]} to the Queue.]\n```')
        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title']}

        return cls(discord.FFmpegPCMAudio(source), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpegopts), data=data, requester=requester)


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'loop', '_curr')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        self.loop = False
        self._curr = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(900):  # 15 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if self.loop:
                await self.queue.put(source) # If looping, put it back into the queue
            else:
                self._curr = source


            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    # await self._channel.send(f'There was an error processing your song.\n'
                    #                          f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            self.np = await self._channel.send(f'**Now Playing:** `{source.title}` requested by '
                                               f'`{source.requester}`')
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
            except discord.HTTPException:
                pass

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        with open('data/playlists.json') as f:
            self._playlists = json.load(f)
        self.save_playlists_to_json.start()

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Error connecting to Voice Channel. '
                           'Please make sure you are in a valid channel or provide me with one')

        print('Ignoring exception in command {}:'.format(ctx.command))
        traceback.print_exception(type(error), error, error.__traceback__)

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel = None):
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

        await ctx.send(f'Connected to: **{channel}**', delete_after=5)

    @commands.group(name='play', aliases=['sing'], invoke_without_command=True)
    async def play_(self, ctx, *, search: str):
        """Request a song and add it to the queue.
        This command attempts to join a valid voice channel if the bot is not already in one.
        Uses YTDL to automatically search and retrieve a song.
        Parameters
        ------------
        search: str [Required]
            The song to search and retrieve using YTDL. This could be a simple search, an ID or URL.
        """
        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)
        await ctx.send('Very long playlist may take a minute to ready', delete_after=3)
        # If download is False, source will be a dict which will be used later to regather the stream.
        # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

        if source is None:
            return

        if isinstance(source, dict):
            await player.queue.put(source)
        else:
            for src in source:
                await player.queue.put(src)

    @play_.command()
    async def playlist(self, ctx, *, name: str):
        """Plays special predefined playlist instead of youtube search"""
        await ctx.trigger_typing()

        vc = ctx.voice_client
        if not vc:
            await ctx.invoke(self.connect_)
        player = self.get_player(ctx)

        if name in self._playlists:
            url = self._playlists[name]
            await ctx.send(f'Playing playlist: `{name}`\n')
            await ctx.send('Very long playlist may take a minute to ready', delete_after=3)
            source = await YTDLSource.create_source(ctx, url, loop=self.bot.loop, download=False)
            if isinstance(source, dict):
                await player.queue.put(source)
            else:
                for src in source:
                    await player.queue.put(src)
        else:
            return await ctx.send(f'Unable to find that playlist. Please see `{ctx.prefix}playlist list`')

    @commands.command(name='pause', aliases=['ll', '||'])
    async def pause_(self, ctx):
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('I am not currently playing anything!')
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f'**`{ctx.author}`**: Paused the song!')

    @commands.command(name='resume', aliases=['>'])
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Resumed the song!')

    @commands.command(name='skip')
    async def skip_(self, ctx, amount: int = 1):
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        player = self.get_player(ctx)
        amount = max(amount, 1)
        for _ in range(amount-1):
            __ = await player.queue.get()

        vc.stop()
        await ctx.send(f'**`{ctx.author}`**: Skipped the song!')

    @commands.command(name='queue', aliases=['q'])
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send('There are currently no more queued songs.')

        # Grab up to 15 entries from the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, 15))
        numbered = [f'{i+1}. **`{_["title"]}`**' for i, _ in enumerate(upcoming)]
        # fmt = '\n'.join(f'**`{_["title"]}`**' for _ in upcoming)
        fmt = '\n'.join(numbered)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)} (out of {player.queue.qsize()} total)', description=fmt)
        if player.loop:
            embed.set_footer(text='Looping: ON')

        await ctx.send(embed=embed)

    @commands.command(name='np', aliases=['nowplaying', 'current', 'currentsong', 'playing'])
    async def now_playing_(self, ctx):
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('I am not currently playing anything!')

        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send(f'**Now Playing:** `{vc.source.title}` '
                                   f'requested by `{vc.source.requester}`')

    @commands.command(name='volume', aliases=['vol'])
    async def change_volume(self, ctx, *, vol: float = None):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')

        if (not 0 <= vol <= 200) and vol is not None :
            return await ctx.send('Please enter a value between 0 and 200.')

        player = self.get_player(ctx)

        if vol is None:
            return await ctx.send(f'The current volume is: **{vc.source.volume*100}%**')

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(f'**`{ctx.author}`**: Set the volume to **{vol}%**')

    @commands.command(name='stop')
    async def stop_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!')

        await self.cleanup(ctx.guild)

    @commands.command(name='shuffle')
    async def shuffle_(self, ctx):
        """Shuffles the queue"""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')
        try:
            shuffle(self.get_player(ctx).queue._queue)
            await ctx.message.add_reaction("\u2705")
        except:
            await ctx.send('An error occurred ')

    @commands.command(name='loop')
    async def toggle_loop(self, ctx, toggle:Optional[bool]):
        """Toggles looping"""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')

        player = self.get_player(ctx)
        if toggle:
            player.loop = toggle
        else:
            player.loop = not player.loop

        if player.loop and player.current:
            await player.queue.put(player._curr)

        await ctx.send(f'Looping is now {"on" if player.loop else "off"}!')
        await ctx.message.add_reaction("\u2705")

    @commands.command(name='clear')
    async def purge_queue(self, ctx, amount:int=0):
        """Removes everything after the first `amount` items in queue"""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!')
        amount = max(amount, 0)
        player = self.get_player(ctx)
        new = asyncio.Queue()
        for _ in range(amount):
            if player.queue.empty():
                break
            await new.put(await player.queue.get())
        player.queue = new
        await ctx.message.add_reaction("\u2705")

    @play_.error
    async def play_handler(self, ctx, error):
        if isinstance(error, utils.DownloadError):
            ctx.local_handled = True
            await ctx.send('Error: This video is unavailable. Please try again or use another video.', delete_after=10)

    @commands.group(name='playlist')
    async def _playlist(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_playlist.command()
    async def add(self, ctx, name, link):
        """Add a new playlist/song to save.
        Names with multiple words must be quoted ex. add 'cool playlist' youtube.com/..."""
        name = name.lower()
        if name in self._playlists:
            return await ctx.send('Sorry that name is already taken, please try again with a different name')
        else:
            try:
                self._playlists[name] = link
            except:
                return await ctx.send('An error has occurred.')
            else:
                await ctx.message.add_reaction('\U00002705')  # React with checkmark
                await ctx.send(f'Added playlist `{name}`, with link: `{link}`')

    @_playlist.command()
    async def remove(self, ctx, name):
        """Remove a saved playlist/song by name"""
        if name not in self._playlists:
            return await ctx.send('Sorry, I am unable to find the playlist with that name.')
        try:
            del self._playlists[name]
        except:
            await ctx.send('An error has occurred.')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            await ctx.send(f'Removed playlist `{name}`')

    @_playlist.command()
    async def list(self, ctx):
        """List all saved playlists/songs"""
        formatted = '\n'.join([f'[{k}]({v})' for k, v in self._playlists.items()])

        e = discord.Embed(title="Saved Playlists",
                          colour=discord.Color.red(),
                          description=formatted)

        await ctx.send(embed=e)

    @_playlist.command(name='play')
    async def _play(self, ctx, *, name: str):
        await ctx.invoke(self.bot.get_command('play playlist'), name=name)

    @_playlist.command()
    @commands.is_owner()
    async def save(self, ctx):
        try:
            self.save_playlists()
        except:
            await ctx.send('An error has occurred ')
        else:
            await ctx.message.add_reaction('\U00002705')

    def save_playlists(self):
        with open('data/playlists.json', 'w') as f:
            json.dump(self._playlists, f, indent=2)

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=6)
    async def save_playlists_to_json(self):
        self.save_playlists()

    def cog_unload(self):
        self.save_playlists_to_json.cancel()
        self.save_playlists()

def setup(bot):
    bot.add_cog(Music(bot))
