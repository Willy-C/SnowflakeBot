"""
Myst Open License - Version 0.1.
=====================================
Copyright (c) 2019 EvieePy(MysterialPy)
 This Source Code Form is subject to the terms of the Myst Open License, v. 0.1.
 If a copy of the MOL was not distributed with this file, You can obtain one at
 https://gist.github.com/EvieePy/bfe0332ad7bff98691f51686ded083ea.
"""
import asyncio
import datetime
import discord
import humanize
import itertools
import math
import random
import re
import json
import wavelink
from collections import deque
from async_timeout import timeout
from discord.ext import commands, tasks

from utils.global_utils import confirm_prompt

RURL = re.compile(r'https?:\/\/(?:www\.)?.+')


class SongTime(commands.Converter):
    async def convert(self, ctx, argument):
        *_, h, m, s = f"::{argument}".split(':')
        if all([not t.isdigit() for t in [h, m, s]]):
            return

        h = 0 if not h.isdigit() else int(h)
        m = 0 if not m.isdigit() else int(m)
        s = 0 if not s.isdigit() else int(s)

        td = datetime.timedelta(hours=h, minutes=m, seconds=s)
        return td


class Track(wavelink.Track):
    __slots__ = ('requester', 'channel', 'message')

    def __init__(self, id_, info, *, ctx=None):
        super(Track, self).__init__(id_, info)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.message = ctx.message

    @property
    def is_dead(self):
        return self.dead


class Player(wavelink.Player):

    def __init__(self, bot: commands.Bot, guild_id: int, node: wavelink.Node):
        super(Player, self).__init__(bot, guild_id, node)

        self.queue = asyncio.Queue()
        self.next_event = asyncio.Event()

        self.volume = 50
        self.controller_message = None
        self.reaction_task = None
        self.update = False
        self.updating = False
        self.inactive = False
        self.looping = False

        self.controls = {'⏯': 'rp',
                         '⏹': 'stop',
                         '⏭': 'skip',
                         '🔀': 'shuffle',
                         '🔂': 'repeat',
                         '🔁': 'loop',
                         '➖': 'vol_down',
                         '➕': 'vol_up',
                         'ℹ': 'queue'}

        self.pauses = set()
        self.resumes = set()
        self.stops = set()
        self.shuffles = set()
        self.skips = set()
        self.repeats = set()

        self.eq = 'Flat'

        bot.loop.create_task(self.player_loop())
        bot.loop.create_task(self.updater())

    @property
    def entries(self):
        return list(self.queue._queue)

    async def updater(self):
        _second = False
        while not self.bot.is_closed():
            if not _second:
                self.update = True
            _second = not _second
            if self.update and not self.updating:
                self.update = False
                await self.invoke_controller()

            await asyncio.sleep(10)

    async def player_loop(self):
        await self.bot.wait_until_ready()

        await self.set_preq('Flat')
        # We can do any pre loop prep here...
        await self.set_volume(self.volume)

        while True:
            self.next_event.clear()

            self.inactive = False

            try:
                async with timeout(300):
                    song = await self.queue.get()
            except asyncio.TimeoutError:
                await self.destroy_controller()
                try:
                    await self.destroy()
                except  KeyError:
                    pass
                return

            if not song:
                await self.destroy_controller()
                continue

            self.current = song
            self.paused = False

            if self.looping:
                await self.queue.put(song)

            await self.play(song)

            # Invoke our controller if we aren't already...
            if not self.update:
                await self.invoke_controller()

            # Wait for TrackEnd event to set our event...
            await self.next_event.wait()

            # Clear votes...
            self.pauses.clear()
            self.resumes.clear()
            self.stops.clear()
            self.shuffles.clear()
            self.skips.clear()
            self.repeats.clear()

    async def invoke_controller(self, track: wavelink.Track = None):
        """Invoke our controller message, and spawn a reaction controller if one isn't alive."""
        if not track:
            track = self.current
        if track is None:
            return
        self.updating = True

        embed = discord.Embed(title='Music Controller',
                              description=f'{"<a:eq:628825184941637652> Now Playing:" if self.is_playing and not self.paused else "⏸ PAUSED"}```ini\n{track.title}\n\n'
                                          f'[EQ]: {self.eq}```',
                              colour=0xffb347)
        embed.set_thumbnail(url=track.thumb)

        if track.is_stream:
            embed.add_field(name='Duration', value='🔴`Streaming`')
        else:
            embed.add_field(name='Duration(approx.)', value=f'{str(datetime.timedelta(milliseconds=int(self.position))).split(".")[0]}/{str(datetime.timedelta(milliseconds=int(track.length)))}')
        embed.add_field(name='Video URL', value=f'[Click Here!]({track.uri})')
        embed.add_field(name='Requested By', value=track.requester.mention)
        embed.add_field(name='Queue Length', value=str(len(self.entries)))
        embed.add_field(name='Volume', value=f'**`{self.volume}%`**')
        embed.add_field(name='Looping', value='ON' if self.looping else 'OFF')

        if len(self.entries) > 0:
            data = '\n'.join(f'**-** `{t.title[0:45]}{"..." if len(t.title) > 45 else ""}`\n{"-"*10}'
                             for t in itertools.islice([e for e in self.entries if not e.is_dead], 0, 3, None))
            embed.add_field(name='Coming Up:', value=data, inline=False)

        if not await self.is_current_fresh(track.channel) and self.controller_message:
            try:
                await self.controller_message.delete()
            except discord.HTTPException:
                pass

            self.controller_message = await track.channel.send(embed=embed)
        elif not self.controller_message:
            self.controller_message = await track.channel.send(embed=embed)
        else:
            self.updating = False
            return await self.controller_message.edit(embed=embed, content=None)

        try:
            self.reaction_task.cancel()
        except Exception:
            pass

        self.reaction_task = self.bot.loop.create_task(self.reaction_controller())
        self.updating = False

    async def add_reactions(self):
        """Add reactions to our controller."""
        for reaction in self.controls:
            try:
                await self.controller_message.add_reaction(str(reaction))
            except discord.HTTPException:
                return

    async def reaction_controller(self):
        """Our reaction controller, attached to our controller.
        This handles the reaction buttons and it's controls.
        """
        self.bot.loop.create_task(self.add_reactions())

        def check(r, u):
            if not self.controller_message:
                return False
            elif str(r) not in self.controls.keys():
                return False
            elif u.id == self.bot.user.id or r.message.id != self.controller_message.id:
                return False
            elif u not in self.bot.get_channel(int(self.channel_id)).members:
                return False
            return True

        while self.controller_message:
            if self.channel_id is None:
                return self.reaction_task.cancel()

            react, user = await self.bot.wait_for('reaction_add', check=check)
            control = self.controls.get(str(react))

            if control == 'rp':
                if self.paused:
                    control = 'resume'
                else:
                    control = 'pause'

            try:
                await self.controller_message.remove_reaction(react, user)
            except discord.HTTPException:
                pass
            cmd = self.bot.get_command(control)

            ctx = await self.bot.get_context(react.message)
            ctx.author = user

            try:
                if cmd.is_on_cooldown(ctx):
                    pass
                if not await self.invoke_react(cmd, ctx):
                    pass
                else:
                    self.bot.loop.create_task(ctx.invoke(cmd))
            except Exception as e:
                ctx.command = self.bot.get_command('reactcontrol')
                await cmd.dispatch_error(ctx=ctx, error=e)

        await self.destroy_controller()

    async def destroy_controller(self):
        """Destroy both the main controller and it's reaction controller."""
        try:
            await self.controller_message.delete()
            self.controller_message = None
        except (AttributeError, discord.HTTPException):
            pass

        try:
            self.reaction_task.cancel()
        except Exception:
            pass

    async def invoke_react(self, cmd, ctx):
        if not cmd._buckets.valid:
            return True

        if not (await cmd.can_run(ctx)):
            return False

        bucket = cmd._buckets.get_bucket(ctx)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return False
        return True

    async def is_current_fresh(self, chan):
        """Check whether our controller is fresh in message history."""
        try:
            async for m in chan.history(limit=7):
                if m.id == self.controller_message.id:
                    return True
        except (discord.HTTPException, AttributeError):
            return False
        return False


class Music(commands.Cog):
    """Our main Music Cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {}
        with open('data/playlists.json') as f:
            self._playlists = json.load(f)

        with open('data/noafks.json') as f:
            self.noafks = set(json.load(f))

        self.save_playlists_to_json.start()

        if not hasattr(bot, 'wavelink'):
            self.bot.wavelink = wavelink.Client(bot)

        bot.loop.create_task(self.initiate_nodes())

    def cog_unload(self):
        if not any([player.is_playing for player in self.bot.wavelink.players.values()]):
            for player in self.bot.wavelink.players.values():
                self.bot.loop.create_task(player.destroy())
            self.bot.loop.create_task(self.bot.wavelink.destroy_node(identifier='MAIN'))
        else:
            for player in self.bot.wavelink.players.values():
                if not player.is_connected:
                    self.bot.loop.create_task(player.destroy())

        self.save_playlists_to_json.cancel()
        self.save_playlists()
        self.save_noafks()

    async def initiate_nodes(self):
        _main = self.bot.wavelink.get_node('MAIN')
        if _main:
            return _main.set_hook(self.event_hook)

        nodes = {'MAIN': {'host': '127.0.0.1',
                          'port': 2333,
                          'rest_url': 'http://127.0.0.1:2333',
                          'password': "testpassword",
                          'identifier': 'MAIN',
                          'region': 'us_central'}}

        for n in nodes.values():
            node = await self.bot.wavelink.initiate_node(host=n['host'],
                                                         port=n['port'],
                                                         rest_uri=n['rest_url'],
                                                         password=n['password'],
                                                         identifier=n['identifier'],
                                                         region=n['region'],
                                                         secure=False)

            node.set_hook(self.event_hook)

    def event_hook(self, event):
        """Our event hook. Dispatched when an event occurs on our Node."""
        if isinstance(event, wavelink.TrackEnd):
            event.player.next_event.set()
        elif isinstance(event, wavelink.TrackException):
            print(event.error)

    def required(self, player, invoked_with):
        """Calculate required votes."""
        channel = self.bot.get_channel(int(player.channel_id))
        if invoked_with == 'stop':
            if len(channel.members) - 1 == 2:
                return 2

        return math.ceil((len(channel.members) - 1) / 2.5)

    async def has_perms(self, ctx, **perms):
        """Check whether a member has the given permissions."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = ctx.channel
        permissions = ch.permissions_for(ctx.author)

        missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]

        if not missing:
            return True

        return False

    async def vote_check(self, ctx, command: str):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        vcc = len(self.bot.get_channel(int(player.channel_id)).members) - 1
        votes = getattr(player, command + 's', None)

        if vcc < 3 and not ctx.invoked_with == 'stop':
            votes.clear()
            return True
        else:
            votes.add(ctx.author.id)

            if len(votes) >= self.required(player, ctx.invoked_with):
                votes.clear()
                return True
        return False

    async def do_vote(self, ctx, player, command: str):
        attr = getattr(player, command + 's', None)
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if ctx.author.id in attr:
            await ctx.send(f'{ctx.author.mention}, you have already voted to {command}!', delete_after=5)
        elif await self.vote_check(ctx, command):
            await ctx.send(f'Vote request for {command} passed!', delete_after=10)
            to_do = getattr(self, f'do_{command}')
            await to_do(ctx)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to {command} the song!'
                           f' **{self.required(player, ctx.invoked_with) - len(attr)}** more votes needed!',
                           delete_after=5)

    @commands.command(name='reactcontrol', hidden=True)
    async def react_control(self, ctx):
        """Dummy command for error handling in our player."""
        pass

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel = None):
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        Examples
        ------------
        %join   (joins your current voice channel if you are in one)
        %join cool vc
        """
        # try:
        #     await ctx.message.delete()
        # except discord.HTTPException:
        #     pass

        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                return await ctx.send('No channel to join. Please either specify a valid channel or join one.')

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if player.is_connected:
            if ctx.author.voice.channel == ctx.guild.me.voice.channel:
                return

        await player.connect(channel.id)

    async def _ask_for_selection(self, ctx, tracks):
        if len(tracks) == 1:
            return tracks[0]

        songs = []
        for index, track in enumerate(tracks[:5]):
            length = str(datetime.timedelta(milliseconds=int(track.length)))
            title = f'`{track.title[0:90]}{"..." if len(track.title) > 90 else ""}`'
            author = f'`{track.author[0:40]}{"..." if len(track.author) > 40 else ""}`'
            songs.append(f'{index+1}\U000020e3 {title} - {author} [{length}] \n{"-"*15}')
        data = '\n'.join(songs)
        e = discord.Embed(title='Youtube search',
                          description=data,
                          color=0xFF2133)
        selector = await ctx.send('Please choose your song with a reaction', embed=e)

        _reactions = ['\U0000274c']
        for i in range(len(songs)):
            _reactions.append(f'{i+1}\U000020e3')
            await selector.add_reaction(f'{i+1}\U000020e3')

        await selector.add_reaction('\U0000274c') # X for cancel

        def check(reaction, user):
            return reaction.message.id == selector.id and str(reaction.emoji) in _reactions and user == ctx.author

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=check)
        except asyncio.TimeoutError:
            await ctx.send('Took too long... aborting', delete_after=8)
            return
        else:
            if reaction.emoji == '❌':
                await ctx.send('Aborting...', delete_after=5)
                return
            player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
            if player.is_connected:
                return tracks[int(reaction.emoji[0])-1]
        finally:
            await selector.delete()

    @commands.command(name='play', aliases=['p'])
    async def play_(self, ctx, *, query: str = None):
        """Queue a song or playlist for playback.
        Aliases
        ---------
            sing
        Parameters
        ------------
        query: simple, URL [Required]
            The query to search for a song. This could be a simple search term or a valid URL.
            e.g Youtube URL or Song Name
        Examples
        ----------
        %play What is love?
        %play https://www.youtube.com/watch?v=XfR9iY5y94s
        """
        await ctx.trigger_typing()

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected or (player.is_connected and ctx.author.voice and ctx.author.voice.channel != ctx.guild.me.voice.channel):
            await ctx.invoke(self.connect_)

        if not player.is_connected:
            return

        if query is None:
            return

        query = query.strip('<>')

        if not RURL.match(query):
            query = f'ytsearch:{query}'

        tracks = await self.bot.wavelink.get_tracks(query)
        if not tracks:
            return await ctx.send('No songs were found with that query. Please try again.')

        if isinstance(tracks, wavelink.TrackPlaylist):
            for t in tracks.tracks:
                await player.queue.put(Track(t.id, t.info, ctx=ctx))

            await ctx.send(f'```ini\nAdded the playlist {tracks.data["playlistInfo"]["name"]}'
                           f' with {len(tracks.tracks)} songs to the queue.\n```', delete_after=15)
        else:
            track = await self._ask_for_selection(ctx, tracks)
            if track is None:
                return
            await ctx.send(f'```ini\nAdded {track.title} to the Queue\n```', delete_after=10)
            await player.queue.put(Track(track.id, track.info, ctx=ctx))

        if player.controller_message and player.is_playing:
            await player.invoke_controller()

        # await asyncio.sleep(10)
        # try:
        #     if ctx.message.id != player.controller_message.id:
        #         await ctx.message.delete()
        # except (discord.HTTPException, AttributeError):
        #     pass

    @commands.command(name='np', aliases=['current'])
    async def now_playing(self, ctx):
        """Invoke the player controller.
        Aliases
        ---------
            np
            current
            currentsong
        Examples
        ----------
        %now_playing
        %np
        The player controller contains various information about the current and upcoming songs.
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        if not player:
            return

        if not player.is_connected:
            return

        if player.updating or player.update:
            return

        try:
            await player.destroy_controller()
        except:
            pass

        await player.invoke_controller()

    @commands.command(name='pause')
    async def pause_(self, ctx):
        """Pause the currently playing song.
        Examples
        ----------
        %pause
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        if not player:
            return

        if not player.is_connected:
            await ctx.send('I am not currently connected to voice!')

        if player.paused:
            return

        await ctx.send(f'{ctx.author.mention} has paused the music!', delete_after=7)

        return await self.do_pause(ctx)

    async def do_pause(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        player.paused = True
        await player.set_pause(True)

        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command(name='resume')
    async def resume_(self, ctx):
        """Resume a currently paused song.
        Examples
        ----------
        %resume
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            await ctx.send('I am not currently connected to voice!')

        if not player.paused:
            return

        await ctx.send(f'{ctx.author.mention} has resumed the music!', delete_after=7)

        return await self.do_resume(ctx)

    async def do_resume(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.set_pause(False)

        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command(name='skip')
    async def skip_(self, ctx, amount = 1):
        """Skip the current song.
        Examples
        ----------
        %skip
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        amount = max(amount, 1)
        for _ in range(amount-1):
            __ = await player.queue.get()

        if amount == 1:
            await ctx.send(f'{ctx.author.mention} has skipped the song!', delete_after=8)
        else:
            await ctx.send(f'{ctx.author.mention} has skipped {amount} songs!', delete_after=10)

        return await self.do_skip(ctx)

    async def do_skip(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await player.stop()

    @commands.command(name='stop')
    async def stop_(self, ctx):
        """Stop the player, disconnect and clear the queue.
        Example
        ----------
        %stop
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        await ctx.send(f'{ctx.author.mention} has stopped the music!')

        return await self.do_stop(ctx)

    async def do_stop(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await player.destroy()
        await player.destroy_controller()

    @commands.command(name='volume', aliases=['vol'])
    async def volume_(self, ctx, *, value: float):
        """Change the player volume.
        Aliases
        ---------
            vol
        Parameters
        ------------
        value:
            The volume level you would like to set. This can be a number between 1 and 100.
            Members with manage guild can override it to be value over 100
        Example
        ----------
        %volume 50
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        current_channel_members = self.bot.get_channel(int(player.channel_id)).members
        if ctx.author not in current_channel_members and not ctx.channel.permissions_for(ctx.author).manage_guild and ctx.author.id != self.bot.owner_id:
            return await ctx.send('You are not in my voice channel!')
        if not ctx.channel.permissions_for(ctx.author).manage_guild and (len(current_channel_members) - 1) > 1 and ctx.author.id != self.bot.owner_id:
                if not 0 <= value <= 100:
                    return await ctx.send('Please enter a value between 0 and 100.')

        if value < 0:
            return await ctx.send('Please enter a value that is at least 0!')

        if value > 100:
            if not await confirm_prompt(ctx, f'Set the volume to **{value}**%? High volumes can damage people\'s hearing!'):
                return

        await player.set_volume(value)
        await ctx.send(f'{ctx.author.mention}: Set the volume to **{value}**%', delete_after=10)

        if not player.updating and not player.update:
            await player.invoke_controller()

        await asyncio.sleep(20)
        try:
            if ctx.message.id != player.controller_message.id:
                await ctx.message.delete()
        except (discord.HTTPException, AttributeError):
            pass

    @commands.command(name='queue', aliases=['q', 'que'])
    async def queue_(self, ctx):
        """Retrieve a list of currently queued songs.
        Aliases
        ---------
            que
            q
        Examples
        ----------
        %queue
        %q
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        upcoming = list(itertools.islice(player.entries, 0, 15))

        if not upcoming:
            return await ctx.send('```\nNo more songs in the Queue!\n```')
        numbered = [f'`{i+1}. [{str(datetime.timedelta(milliseconds=int(song.length)))}] {song.title[0:45]}{"..." if len(song.title) > 45 else ""}`' for i, song in enumerate(upcoming)]
        fmt = '\n'.join(numbered)
        # fmt = '\n'.join(f'**`{str(song)}`**' for song in upcoming)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle_(self, ctx):
        """Shuffle the current queue.
        Examples
        ----------
        %shuffle
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        await ctx.send(f'{ctx.author.mention} has shuffled the queue!', delete_after=10)

        return await self.do_shuffle(ctx)

    async def do_shuffle(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        random.shuffle(player.queue._queue)

        await ctx.send('Shuffling..', delete_after=5)
        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command(name='repeat')
    async def repeat_(self, ctx):
        """Repeat the currently playing song.
        Examples
        ----------
        %repeat
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return

        await ctx.send(f'{ctx.author.mention} repeated the current song!', delete_after=7)

        return await self.do_repeat(ctx)

    async def do_repeat(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.entries:
            await player.queue.put(player.current)
        else:
            player.queue._queue.appendleft(player.current)

        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command(name='loop')
    async def loop_(self, ctx, toggle: bool=None):
        """Toggles repeat for whole queue
        Examples
        ---------
        %loop (will toggle)
        %loop on/off
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if toggle:
            player.looping = toggle
        else:
            player.looping = not player.looping

        if player.looping and player.is_playing:
            await player.queue.put(player.current)

        await ctx.send(f'{ctx.author.mention} Looping is now {"on" if player.looping else "off"}!', delete_after=10)
        if not player.updating and not player.update:
            await player.invoke_controller()
        await asyncio.sleep(10)
        try:
            if ctx.message.id != player.controller_message.id:
                await ctx.message.delete()
        except (discord.HTTPException, AttributeError):
            pass

    @commands.command(name='vol_up', hidden=True)
    async def volume_up(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return

        vol = int(math.ceil((player.volume + 10) / 10)) * 10

        if vol > 100:
            vol = 100
            await ctx.send('Maximum volume reached', delete_after=7)

        await ctx.send(f'{ctx.author.mention} has raised the volume!', delete_after=7)

        await player.set_volume(vol)
        if not player.updating and not player.update:
            await player.invoke_controller()
        await asyncio.sleep(10)
        try:
            if ctx.message.id != player.controller_message.id:
                await ctx.message.delete()
        except (discord.HTTPException, AttributeError):
            pass

    @commands.command(name='vol_down', hidden=True)
    async def volume_down(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return

        vol = int(math.ceil((player.volume - 10) / 10)) * 10

        if vol < 0:
            vol = 0
            await ctx.send('Player is currently muted', delete_after=10)

        await ctx.send(f'{ctx.author.mention} has lowered the volume!', delete_after=7)

        await player.set_volume(vol)
        if not player.updating and not player.update:
            await player.invoke_controller()
        await asyncio.sleep(10)
        try:
            if ctx.message.id != player.controller_message.id:
                await ctx.message.delete()
        except (discord.HTTPException, AttributeError):
            pass

    @commands.command(name='clear')
    async def clear_queue(self, ctx, amount = 0):
        """Removes everything after the first `amount` items in queue"""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')
        new = asyncio.Queue()
        for _ in range(amount):
            if player.queue.empty():
                break
            await new.put(await player.queue.get())
        player.queue = new
        await ctx.message.add_reaction("\u2705")
        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command(name='playnext', aliases=['pnext', 'pn'])
    async def _playnext(self, ctx, *, query: str = None):
        """Add a song or playlist to the front of the queue"""
        await ctx.trigger_typing()

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected or (player.is_connected and ctx.author.voice and ctx.author.voice.channel != ctx.guild.me.voice.channel):
            await ctx.invoke(self.connect_)

        if not player.is_connected:
            return

        if query is None:
            return

        query = query.strip('<>')

        if not RURL.match(query):
            query = f'ytsearch:{query}'

        tracks = await self.bot.wavelink.get_tracks(query)
        if not tracks:
            return await ctx.send('No songs were found with that query. Please try again.')

        if isinstance(tracks, wavelink.TrackPlaylist):
            for t in tracks.tracks[::-1]:
                if not player.entries:
                    await player.queue.put(Track(t.id, t.info, ctx=ctx))
                else:
                    player.queue._queue.appendleft(Track(t.id, t.info, ctx=ctx))

            await ctx.send(f'```ini\nAdded the playlist {tracks.data["playlistInfo"]["name"]}'
                           f' with {len(tracks.tracks)} songs to the Front of the Queue.\n```', delete_after=15)
        else:
            track = await self._ask_for_selection(ctx, tracks)
            if track is None:
                return
            await ctx.send(f'```ini\nAdded {track.title} to the Front of the Queue\n```', delete_after=10)

            if not player.entries:
                await player.queue.put(Track(track.id, track.info, ctx=ctx))
            else:
                player.queue._queue.appendleft(Track(track.id, track.info, ctx=ctx))

        if player.controller_message and player.is_playing:
            await player.invoke_controller()

    @commands.command(name='eq')
    async def set_eq(self, ctx, *, eq: str):
        """Set the eq of the player.
        Can be [Flat, Boost, Metal, Piano]"""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if eq.upper() not in player.equalizers:
            return await ctx.send(f'`{eq}` - Is not a valid equalizer!\nTry Flat, Boost, Metal, Piano.')

        await player.set_preq(eq)
        player.eq = eq.capitalize()
        await ctx.send(f'The player Equalizer was set to - {eq.capitalize()} - {ctx.author.mention}')
        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command()
    async def wlinfo(self, ctx):
        """Retrieve various Node/Server/Player information."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = f'**WaveLink:** `{wavelink.__version__}`\n\n' \
              f'Connected to `{len(self.bot.wavelink.nodes)}` nodes.\n' \
              f'Best available Node `{self.bot.wavelink.get_best_node().__repr__()}`\n' \
              f'`{len(self.bot.wavelink.players)}` players are distributed on nodes.\n' \
              f'`{node.stats.players}` players are distributed on server.\n' \
              f'`{node.stats.playing_players}` players are playing on server.\n\n' \
              f'Server Memory: `{used}/{total}` | `({free} free)`\n' \
              f'Server CPU: `{cpu}`\n\n' \
              f'Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`'
        await ctx.send(fmt)

    @commands.command()
    async def seek(self, ctx, time: SongTime):
        """Jump to a certain time of the song
        ex. seek 0       (jump to 0s - beginning)
            seek 4:30    (jump to 4m30s)
            seek 1:15:10 (jump to 1h15m10s)"""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')
        if not player.is_playing:
            return await ctx.send('I am currently not playing anything!')
        if time is None:
            return await ctx.send('Invalid time inputted!\n'
                                  '```Try:\n'
                                  'seek 0       (jump to 0s - beginning)\n'
                                  'seek 4:30    (jump to 4m30s)\n'
                                  'seek 1:15:10 (jump to 1h15m10s)```')

        ms = time.seconds*1000

        if ms == 0:
            await ctx.send(f'{ctx.author.mention} restarted the song from the beginning', delete_after=10)
        elif ms > player.current.length:
            return await ctx.send('The inputted time is longer than the song!')
        else:
            await ctx.send(f'{ctx.author.mention} skipped the song to `{time}`', delete_after=10)

        await player.seek(ms)
        if not player.updating and not player.update:
            await player.invoke_controller()
        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name='ff', aliases=['fastforward'])
    async def fast_forward(self, ctx, time: SongTime):
        """Fast forward a certain amount of time
        ex. ff 10      (fast forwards 10s)
            ff 4:30    (fast forwards 4m30s)
            ff 1:15:10 (fast forwards 1h15m10s)"""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')
        if not player.is_playing:
            return await ctx.send('I am currently not playing anything!')
        if time is None:
            return await ctx.send('Invalid time inputted!\n'
                                  '```Try:\n'
                                  'ff 10      (fast forwards 10s)\n'
                                  'ff 4:30    (fast forwards 4m30s)\n'
                                  'ff 1:15:10 (fast forwards 1h15m10s)```')

        ms = time.seconds*1000
        curr = player.position

        if ms == 0:
            return await ctx.send(f'Please enter a time that is at least 1 second', delete_after=10)
        elif ms + curr > player.current.length:
            remaining = str(datetime.timedelta(milliseconds=player.current.length - curr)).split('.')[0]
            return await ctx.send(f'{ctx.author.mention} Not enough of the song is left to fast forward to! ({remaining} remaining)', delete_after=10)
        else:
            current = str(datetime.timedelta(milliseconds=curr + ms)).split('.')[0]
            await ctx.send(f'{ctx.author} fast forwarded the song by: `{time}` (now at: `{current}`)', delete_after=10)

        await player.seek(curr+ms)
        if not player.updating and not player.update:
            await player.invoke_controller()
        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name='rewind', aliases=['rwd'])
    async def rewind(self, ctx, time: SongTime):
        """Fast forward a certain amount of time
        ex. rwd 10      (rewinds 10s)
            rwd 4:30    (rewinds 4m30s)
            rwd 1:15:10 (rewinds 1h15m10s)"""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')
        if not player.is_playing:
            return await ctx.send('I am currently not playing anything!')
        if time is None:
            return await ctx.send('Invalid time inputted!\n'
                                  '```Try:\n'
                                  'rwd 10      (rewinds 10s)\n'
                                  'rwd 4:30    (rewinds 4m30s)\n'
                                  'rwd 1:15:10 (rewinds 1h15m10s)```')

        ms = time.seconds*1000
        curr = player.position

        if ms == 0:
            return await ctx.send(f'Please enter a time that is at least 1 second', delete_after=10)
        elif curr-ms <= 0:
            await ctx.send(f'{ctx.author.mention} restarted the song from the beginning', delete_after=10)
            new_position = 0
        else:
            new_position = curr - ms
            current = str(datetime.timedelta(milliseconds=new_position))
            await ctx.send(f'{ctx.author} rewinded the song by: `{time}` (now at: `{current}`)', delete_after=10)

        await player.seek(new_position)
        if not player.updating and not player.update:
            await player.invoke_controller()
        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    # Custom playlist stuff:

    @commands.group(invoke_without_command=True)
    async def playlist(self, ctx, *, name=None):
        """Play/Add/Remove custom playlists"""
        if name is None:
            return await ctx.invoke(self.list)
        url = self._playlists.get(name)
        if url:
            await ctx.invoke(self.play_, query=url)
        else:
            await ctx.send(f'Unable to find a saved playlist/song with that name. All saved playlists are listed here:')
            await ctx.invoke(self.list)

    @playlist.command()
    async def add(self, ctx, name, link):
        """Add a new playlist/song to save.
        Names with multiple words must be quoted ex. add "cool playlist" youtube.com/...
        Example
        ------------
        %playlist add star youtube.com/..."""
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

    @playlist.command()
    async def remove(self, ctx, *, name):
        """Remove a saved playlist/song by name
        Example
        ------------
        %playlist remove star"""
        if name not in self._playlists:
            return await ctx.send('Sorry, I am unable to find the playlist with that name.')
        try:
            del self._playlists[name]
        except:
            await ctx.send('An error has occurred.')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            await ctx.send(f'Removed playlist `{name}`')

    @playlist.command()
    async def list(self, ctx):
        """List all saved playlists/songs"""
        formatted = '\n'.join([f'[{k}]({v})' for k, v in self._playlists.items()])

        e = discord.Embed(title="Saved Playlists",
                          colour=discord.Color.red(),
                          description=formatted)

        await ctx.send(embed=e)

    @playlist.command()
    @commands.is_owner()
    async def save(self, ctx):
        try:
            self.save_playlists()
        except Exception as e:
            await ctx.send(f'An error has occurred: `{e}` ')
        else:
            await ctx.message.add_reaction('\U00002705')

    def save_playlists(self):
        with open('data/playlists.json', 'w') as f:
            json.dump(self._playlists, f, indent=2)

    def save_noafks(self):
        with open('data/noafks.json', 'w') as f:
            json.dump(list(self.noafks), f, indent=2)

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=24)
    async def save_playlists_to_json(self):
        self.save_playlists()
        self.save_noafks()

    # Anti-afk

    @commands.command(name='noafk', hidden=True)
    async def no_afk_toggle(self, ctx):
        """Toggles anti-afk"""
        if ctx.author.id in self.noafks:
            self.noafks.remove(ctx.author.id)
            await ctx.send('You will no longer be moved back when you AFK')
            await ctx.message.add_reaction('\U00002796')  # React with minus sign
        else:
            self.noafks.add(ctx.author.id)
            await ctx.send('You be moved back when you AFK')
            await ctx.message.add_reaction('\U00002795')  # React with plus sign

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        :param member: Member
        :param before: VoiceState
        :param after:  VoiceState
        """
        if member.id not in self.noafks:
            return

        if member.guild.id not in self.bot.wavelink.players:
            return

        if before.channel is None or after.channel is None:
            return

        afk_channel = member.guild.afk_channel
        if afk_channel is None:
            return

        player = self.bot.wavelink.get_player(member.guild.id, cls=Player)

        if not player.is_connected:
            await player.destroy()
            return

        if before.channel.id == int(player.channel_id) and after.channel.id == afk_channel.id:
            try:
                current_channel = member.guild.get_channel(int(player.channel_id))
                if current_channel is not None:
                    await member.move_to(current_channel)
            except discord.HTTPException:
                pass


def setup(bot):
    bot.add_cog(Music(bot))
