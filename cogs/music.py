import re
import enum
import asyncio
import collections
import itertools
import random
import datetime
from typing import Optional, Union


import discord
import wavelink
from discord.ext import commands
from wavelink.ext import spotify
from async_timeout import timeout
from asyncpg import UniqueViolationError

from utils.converters import CaseInsensitiveVoiceChannel
from utils.context import Context
from utils.errors import NoVoiceChannel
from utils.views import AskChoice, MusicPlayerView
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, LAVALINK_PASSWORD


class QueryType(enum.Enum):
    YOUTUBETRACK = 1
    YOUTUBEPLAYLIST = 2
    SOUNDCLOUD = 3
    SPOTIFYTRACK = 4
    SPOTIFYPLAYLIST = 5
    CANCELLED = 6


class Player(wavelink.Player):
    def __init__(self, *, ctx: Context, view: MusicPlayerView):
        super().__init__()
        self.ctx = ctx
        self.view = view
        self.text_channel: discord.TextChannel = ctx.channel
        self.looping: bool = False
        self.volume = 25
        self._queue: asyncio.Queue = asyncio.Queue()
        # self._looping_queue: asyncio.Queue = asyncio.Queue()
        self._played: collections.deque = collections.deque(maxlen=10)
        self.next_event: asyncio.Event = asyncio.Event()
        self._controller: Optional[discord.Message] = None
        self.updating: bool = False
        self._player_loop = ctx.bot.loop.create_task(self._player_loop())
        self._controller_lock: asyncio.Lock = asyncio.Lock()
        ctx.bot.loop.create_task(self.invoke_controller())

    @property
    def entries(self):
        return list(self._queue._queue)

    @property
    def size(self):
        return self._queue.qsize()

    @property
    def is_empty(self):
        return self._queue.empty()

    async def add_track(self, track):
        await self._queue.put(track)

    async def track_end(self, track: wavelink.Track):
        self.next_event.set()
        self._played.appendleft(track)

    async def _player_loop(self):
        await self.ctx.bot.wait_until_ready()
        await self.set_volume(self.volume)

        while True:
            self.next_event.clear()
            try:
                with timeout(300):
                    song = await self._queue.get()
            except asyncio.TimeoutError:
                if self.is_empty:
                    await self.stop()
                    await self.disconnect(force=False)
                    return
                continue
            if not song:
                continue

            if self.looping:
                self._queue.put_nowait(song)
            await self.play(song)
            await self.next_event.wait()

    async def invoke_controller(self, track: wavelink.Track=None, force_delete: bool = False):
        async with self._controller_lock:
            if not track:
                track = self.track
            if track is None:
                return
            if self.updating:
                return

            self.updating = True
            embed = discord.Embed(title='Music Controller',
                                  description=f'{"<a:eq:628825184941637652> Now Playing:" if self.is_playing() and not self.is_paused() else "⏸ PAUSED"}```ini\n{track.title}\n```',
                                  colour=0x16D1EF)
            if thumbnail := getattr(track, 'thumbnail', None):
                embed.set_thumbnail(url=thumbnail)
            if track.is_stream():
                embed.add_field(name='Duration', value='🔴`Streaming`')
            else:
                embed.add_field(name='Duration(approx.)', value=datetime.timedelta(seconds=int(self.position)))

            embed.add_field(name='Video URL', value=f'[Click Here!]({track.uri})')
            embed.add_field(name='Queue Length', value=str(len(self.entries)))
            embed.add_field(name='Volume', value=f'**`{self.volume}%`**')
            embed.add_field(name='Looping', value='ON' if self.looping else 'OFF')

            if self.size > 0:
                data = '\n'.join(f'**-** `{t.title[0:45]}{"..." if len(t.title) > 45 else ""}`\n{"-"*10}'
                                 for t in itertools.islice([e for e in self.entries], 0, 3, None))
                embed.add_field(name='Coming Up:', value=data, inline=False)

            if self._controller and ((force_delete and not self.is_last()) or not await self.is_current_fresh()):
                try:
                    await self._controller.delete()
                except discord.HTTPException:
                    pass

                self._controller = await self.text_channel.send(embed=embed, view=self.view)
            elif not self._controller:
                self._controller = await self.text_channel.send(embed=embed, view=self.view)
            else:
                self._controller = await self._controller.edit(embed=embed, view=self.view)
            self.updating = False

    def is_last(self):
        return self._controller and self.text_channel.last_message_id == self._controller.id

    async def is_current_fresh(self):
        """Check whether our controller is fresh in message history."""
        try:
            async for m in self.text_channel.history(limit=5):
                if m.id == self._controller.id:
                    return True
        except (discord.HTTPException, AttributeError):
            return False
        return False

    async def stop(self) -> None:
        if self._controller:
            try:
                await self._controller.delete()
            except discord.HTTPException:
                pass
        await super().stop()

    def cleanup(self) -> None:
        try:
            self._player_loop.cancel()
        except (asyncio.CancelledError, AttributeError):
            pass
        super().cleanup()


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._node: Optional[wavelink.Node] = None
        self.URL_REGEX = re.compile(r'https?://(?:www\.)?.+')
        self.SPOTIFY_REGEX = re.compile(r'https://open\.spotify\.com/(?P<entity>.+)/(?P<identifier>.+)')
        self.SOUNDCLOUD_REGEX = re.compile(r'https://soundcloud\.com/.+')
        bot.loop.create_task(self.create_node(bot))

    async def create_node(self, bot):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)
        try:
            self._node = wavelink.NodePool.get_node()
            if self._node:
                return
        except wavelink.ZeroConnectedNodes:
            pass
        self._node = await wavelink.NodePool.create_node(bot=bot,
                                                         host='127.0.0.1',
                                                         port=2333,
                                                         password=LAVALINK_PASSWORD,
                                                         identifier='MAIN',
                                                         spotify_client=spotify.SpotifyClient(
                                                             client_id=SPOTIFY_CLIENT_ID,
                                                             client_secret=SPOTIFY_CLIENT_SECRET)
                                                         )

    def cog_unload(self):
        if not any(p.is_playing() for p in self._node.players):
            self.bot.loop.create_task(self._node.disconnect(force=True))
        else:
            for player in self._node.players:
                if not player.is_connected():
                    self.bot.loop.create_task(player.disconnect(force=True))

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: Player, track: wavelink.Track, reason: str):
        await player.track_end(track)
        await player.invoke_controller()

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, player: Player, track: wavelink.Track, error: Exception):
        await player.text_channel.send(f'An error occurred while trying to play track `{track.title}`. Skipping...')
        player.next_event.set()

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, player: Player, track: wavelink.Track, threshold: int):
        await player.text_channel.send(f'It appears track `{track.title}` got stuck. Skipping...')
        player.next_event.set()

    async def is_in_vc(self, ctx: Context, member: discord.Member):
        if not ctx.voice_client:
            return
        if not ctx.voice_client.is_connected():
            return
        if await ctx.bot.is_owner(member):
            return True

        return member in ctx.voice_client.channel.members

    async def get_guild_player(self, ctx: Context, channel: Optional[discord.VoiceChannel]=None) -> Player:
        try:
            channel = channel or ctx.author.voice.channel
        except AttributeError:
            raise NoVoiceChannel()

        if (vc := ctx.voice_client) is not None:
            if vc.channel != channel:
                await vc.move_to(channel)
            return vc

        else:
            view = MusicPlayerView(context=ctx)
            _player = Player(ctx=ctx, view=view)
            player = await channel.connect(cls=_player)
            view.player = player
            return player

    @commands.command(name='connect', aliases=['join'])
    async def join_voice_channel(self, ctx: Context, channel: CaseInsensitiveVoiceChannel = None):
        await self.get_guild_player(ctx, channel)
        await ctx.tick()

    async def _run_query(self, coro):
        try:
            tracks = await coro
        except (wavelink.LoadTrackError, wavelink.LavalinkException, spotify.SpotifyRequestError):
            return
        else:
            if tracks:
                return tracks

    async def _query_music(self, query: str):
        query = query.strip('<>')

        match = self.SPOTIFY_REGEX.match(query)
        if match:
            # The library's internal regex requires a "?"
            if '?' not in query:
                query += '?'
            search = spotify.SpotifyTrack.search(query=query)
            search_type = QueryType.SPOTIFYTRACK if match.group('entity') == 'track' else QueryType.SPOTIFYPLAYLIST
            return await self._run_query(search), search_type

        elif self.SOUNDCLOUD_REGEX.match(query):
            query = f'scsearch:{query}'
            search = self._node.get_tracks(wavelink.SoundCloudTrack, query)
            return await self._run_query(search), QueryType.SOUNDCLOUD

        else:
            if not self.URL_REGEX.match(query):
                query = f'ytsearch:{query}'
            playlist_search = self._node.get_playlist(wavelink.YouTubePlaylist, query)
            tracks = await self._run_query(playlist_search)
            if tracks:
                return tracks, QueryType.YOUTUBEPLAYLIST
            track_search = self._node.get_tracks(wavelink.YouTubeTrack, query)
            return await self._run_query(track_search), QueryType.YOUTUBETRACK

    async def get_tracks(self, ctx: Context, query: str):
        tracks, query_type = await self._query_music(query)
        if query_type is QueryType.SPOTIFYTRACK and isinstance(tracks, list):
            tracks = tracks[0]

        elif query_type is QueryType.YOUTUBETRACK and isinstance(tracks, list):
            if len(tracks) == 1:
                tracks = tracks[0]
            else:
                track_choices = []
                for index, track in enumerate(tracks[:5]):
                    length = str(datetime.timedelta(seconds=int(track.length)))
                    title = f'`{track.title[0:90]}{"..." if len(track.title) > 90 else ""}`'
                    author = f'`{track.author[0:40]}{"..." if len(track.author) > 40 else ""}`'
                    track_choices.append(f'{index + 1}\U000020e3 {title} - {author} [{length}] \n{"-" * 15}')
                data = '\n'.join(track_choices)
                e = discord.Embed(title='Youtube search',
                                  description=data,
                                  color=0xFF2133)
                view = AskChoice(track_choices, context=ctx, timeout=60, delete_after=True)
                message = await ctx.reply(embed=e, view=view)
                view.message = message
                await view.wait()
                if view.chosen_index is not None:
                    tracks = tracks[view.chosen_index]
                elif view.cancelled:
                    query_type = QueryType.CANCELLED
                else:
                    tracks = None

        elif query_type is QueryType.SOUNDCLOUD and isinstance(tracks, list):
            tracks = tracks[0]

        elif isinstance(tracks, list):
            if len(tracks) == 1:
                tracks = tracks[0]
        return tracks, query_type

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx: Context, *, query):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            player = await self.get_guild_player(ctx)

        async with ctx.typing():
            tracks, query_type = await self.get_tracks(ctx, query)

        if query_type is QueryType.CANCELLED:
            return await ctx.reply('Cancelled', mention_author=False)

        if not tracks:
            msg = 'Sorry no tracks found with that query.'
            if query_type is QueryType.SOUNDCLOUD:
                msg += '\nNote: SoundCloud can sometimes be unreliable and just not work. Consider using Youtube or Spotify'
            elif query_type is QueryType.YOUTUBETRACK:
                msg += '\nNote: If this is happening consistently, blame YouTube and try again later.'

            return await ctx.reply(msg)

        if isinstance(tracks, wavelink.YouTubePlaylist):
            for track in tracks.tracks:
                await player.add_track(track)
            await ctx.reply(f'Added {len(tracks.tracks)} songs from `{tracks.name}` to the queue')
        elif isinstance(tracks, list):
            for track in tracks:
                await player.add_track(track)
            await ctx.reply(f'Added {len(tracks)} songs to the queue')
        else:
            await player.add_track(tracks)
            if player.is_empty:
                await ctx.reply(f'Playing `{tracks.title}`')
            else:
                await ctx.reply(f'Added `{tracks.title}` to the queue')

        await player.invoke_controller(force_delete=True)

    @commands.command(name='pause')
    async def pause(self, ctx: Context):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return

        if not await self.is_in_vc(ctx, ctx.author):
            return

        await player.pause()
        await ctx.send(f'{ctx.author.mention} has paused the music', allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='resume')
    async def resume(self, ctx: Context):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return

        if not await self.is_in_vc(ctx, ctx.author):
            return

        await player.resume()
        await ctx.send(f'{ctx.author.mention} has resumed the music', allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='current', aliases=['np', 'nowplaying'])
    async def now_playing(self, ctx: Context):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return

        await ctx.send(f'Currently playing: {player.track}')
        await player.invoke_controller(force_delete=True)

    @commands.command(name='skip')
    async def skip_songs(self, ctx: Context):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author):
            return

        await player.stop()
        await ctx.send(f'{ctx.author.mention} has skipped the song', allowed_mentions=discord.AllowedMentions.none())
        await player.invoke_controller(force_delete=True)

    @commands.command(name='stop', aliases=['leave'])
    async def stop(self, ctx: Context):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author) and not ctx.author.guild_permissions.move_members:
            return

        if not player.is_empty and not await ctx.confirm_prompt(
                'Are you sure you want to stop the music? This will delete the current queue.\n'
                'This cannot be undone.'):
            return
        await player.stop()
        await player.disconnect(force=True)
        await ctx.send(f'{ctx.author.mention} has stopped the music', allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='volume', aliases=['vol'])
    async def volume(self, ctx, *, value: float):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author) and not ctx.author.guild_permissions.move_members:
            return

        if not ctx.channel.permissions_for(ctx.author).move_members and (len(ctx.voice_client.channel.members) - 1) > 1 and ctx.author.id != self.bot.owner_id:
            if not 0 <= value <= 100:
                return await ctx.send('Please enter a value between 0 and 100.')

        if value < 0:
            return await ctx.send('Please enter a value that is at least 0!')

        if value > 100:
            if not await ctx.confirm_prompt(f'Set the volume to **{value}**%? High volumes can damage people\'s hearing!'):
                return

        await player.set_volume(value)
        await ctx.reply(f'{ctx.author.mention}: set volume to **{value}**%',
                        allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return

        upcoming = list(itertools.islice(player.entries, 0, 15))
        # Paginator maybe

        if not upcoming:
            return await ctx.send('```\nNo more songs in the Queue!\n```',
                                  allowed_mentions=discord.AllowedMentions.none())
        numbered = [f'`{i+1}. [{str(datetime.timedelta(seconds=int(song.length)))}] {song.title[0:45]}{"..." if len(song.title) > 45 else ""}`' for i, song in enumerate(upcoming)]
        fmt = '\n'.join(numbered)
        # fmt = '\n'.join(f'**`{str(song)}`**' for song in upcoming)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='shuffle')
    async def shuffle(self, ctx):
        """Shuffle the current queue.
        Examples
        ----------
        %shuffle
        """
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author):
            return

        random.shuffle(player._queue._queue)
        await ctx.send(f'{ctx.author.mention} has shuffled the queue', allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='repeat')
    async def repeat_(self, ctx):
        """Repeat the currently playing song.
        Examples
        ----------
        %repeat
        """
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author):
            return

        player._queue._queue.appendleft(player.track)

        await ctx.send(f'{ctx.author.mention} has repeated the current song',
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='loop')
    async def loop_(self, ctx, toggle: bool=None):
        """Toggles repeat for whole queue
        Examples
        ---------
        %loop (will toggle)
        %loop on/off
        """
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author):
            return

        _prev = player.looping

        if toggle:
            player.looping = toggle
        else:
            player.looping = not player.looping

        if not _prev and player.looping and player.is_playing():
            await player.add_track(player.track)

        await ctx.send(f'{ctx.author.mention} Looping is now {"on" if player.looping else "off"}!',
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='clear')
    async def clear_queue(self, ctx):
        player: Player = ctx.voice_client
        if not player or not player.is_connected():
            return
        if not await self.is_in_vc(ctx, ctx.author) and not ctx.author.guild_permissions.move_members:
            return

        if not await ctx.confirm_prompt('Are you sure you want to clear the current queue? This cannot be undone.'):
            return
        new = asyncio.Queue()
        player._queue = new

        await ctx.reply(f'{ctx.author.mention} cleared the queue', allowed_mentions=discord.AllowedMentions.none())

    # Custom playlist stuff:

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def playlist(self, ctx, *, name=None):
        """Play/Add/Remove custom playlists"""
        if name is None:
            return await ctx.invoke(self.list)
        name = name.lower()
        query = '''SELECT url
                  FROM playlists
                  WHERE (private = FALSE OR "user" = $1) AND name = $2
                  ORDER BY CASE WHEN "user" = $1 THEN 0 ELSE 1 END
                  LIMIT 1;
                  '''
        record = await self.bot.pool.fetchrow(query, ctx.author.id, name)
        if record is None:
            await ctx.send(f'Unable to find a saved playlist/song with that name. All available playlists are listed here:')
            await ctx.invoke(self.list)
        else:
            await ctx.invoke(self.play, query=record['url'])

    @playlist.command()
    async def add(self, ctx, name, link, private=False):
        """Add a new playlist/song to save.
        Names with multiple words must be quoted ex. add "cool playlist" youtube.com/...
        Example
        ------------
        %playlist add star youtube.com/..."""
        name = name.lower()
        query = '''INSERT INTO playlists("user", name, url, private)
                   VALUES($1, $2, $3, $4);'''
        try:
            await self.bot.pool.execute(query, ctx.author.id, name, link, private)
        except UniqueViolationError:
            return await ctx.send('Error: You already have a playlist saved with that name!')
        else:
            await ctx.reply(f'Added playlist `{name}`, with link: `{link}`')
            await ctx.tick()

    @playlist.command()
    async def remove(self, ctx, *, name):
        """Remove a saved playlist/song by name
        Example
        ------------
        %playlist remove star"""
        name = name.lower()
        query = '''DELETE FROM playlists
                   WHERE "user" = $1 
                   AND name = $2;'''

        result = await self.bot.pool.execute(query, ctx.author.id, name)
        if result == 'DELETE 0':
            return await ctx.send('Sorry, I am unable to find your playlist with that name.')
        else:
            await ctx.reply(f'Removed playlist `{name}`')
            await ctx.tick()

    @playlist.command()
    async def list(self, ctx):
        """List all saved playlists/songs"""
        query = '''SELECT "user", name, url
                  FROM playlists
                  WHERE private = FALSE OR "user" = $1
                  ORDER BY CASE WHEN "user" = $1 THEN 0 ELSE 1 END;
                  '''
        records = await self.bot.pool.fetch(query, ctx.author.id)
        if not records:
            return await ctx.send('No playlists found')

        playlists = {}
        for record in records:
            if record['name'] not in playlists:
                playlists[record['name']] = record['url']

        formatted = '\n'.join([f'[{k}]({v})' for k, v in playlists.items()])

        e = discord.Embed(title="Saved Playlists",
                          colour=discord.Color.red(),
                          description=formatted)

        await ctx.reply(embed=e, allowed_mentions=discord.AllowedMentions.none())


def setup(bot):
    bot.add_cog(Music(bot))
