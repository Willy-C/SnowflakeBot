import discord
from discord.ext import commands

from asyncio import TimeoutError
from typing import Optional
from datetime import datetime
from collections import Counter

from utils.global_utils import bright_color


class GuildCog(commands.Cog, name='Guild'):
    def __init__(self, bot):
        self.bot = bot

    # Applies commands.guild_only() check for all methods in this cog
    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return True

    @commands.command()
    async def joined(self, ctx, *, member: discord.Member = None):
        """Looks up when a member joined the server."""
        if not member:
            member = ctx.author
        await ctx.send(f'{member.display_name} joined on {member.joined_at.isoformat(" ", "seconds")}')

    @commands.command(name='memcount', aliases=['membercount'])
    async def member_count(self, ctx):
        """Returns the member count of the guild"""
        statuses = Counter(m.status for m in ctx.guild.members)
        bots = Counter(m.bot for m in ctx.guild.members)
        formatted_statuses = f'<:status_online:602811779948740627> {statuses.get(discord.Status.online, 0)}\n' \
                             f'<:status_offline:602811780053336069> {statuses.get(discord.Status.offline, 0)}\n' \
                             f'<:status_idle:602811780129095701> {statuses.get(discord.Status.idle, 0)}\n' \
                             f'<:status_dnd:602811779931701259> {statuses.get(discord.Status.dnd, 0)}'

        e = discord.Embed(color=bright_color(), timestamp=datetime.utcnow())
        e.set_author(name=f'{ctx.guild}\'s member count',  icon_url=ctx.guild.icon_url)
        e.add_field(name='Total', value=ctx.guild.member_count)
        e.add_field(name='Humans', value=bots.get(False, 0))
        e.add_field(name='Bots', value=bots.get(True, 0))
        e.add_field(name='Status', value=formatted_statuses)

        await ctx.send(embed=e)

    @commands.command(name='shortperms', hidden=True)
    async def get_permissions(self, ctx, *, member: discord.Member = None):
        """Lists permissions of a member.
        If a member is not provided, the author will be checked."""

        if not member:
            member = ctx.author
        # Check if the value of each permission is True.
        perms = '\n'.join(perm for perm, value in member.guild_permissions if value)

        # Embeds look nicer
        e = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        e.set_author(icon_url=member.avatar_url, name=str(member))

        e.add_field(name='\uFEFF', value=perms)  # zero-width space

        await ctx.send(embed=e)

    @commands.command(name='perms')
    async def get_all_permissions(self, ctx, *, member: discord.Member = None):
        """Lists all permissions of a member.
        If a member is not provided, the author will be checked."""
        member = member or ctx.author

        perms = '\n'.join(f'<:greenTick:602811779835494410> {perm}' if value else f'<:redTick:602811779474522113> {perm}' for perm, value in member.guild_permissions)

        e = discord.Embed(description=perms, colour=member.colour)
        e.set_author(icon_url=member.avatar_url, name=member)
        await ctx.send(embed=e)

    @commands.command(name='sharescreen', aliases=['share', 'ss', 'video'])
    async def video_inVC(self, ctx, *, channel: Optional[discord.VoiceChannel] = None):
        """Enables video call in a voice channel.
        Defaults to your current voice channel or you can specify a voice channel"""
        author = ctx.message.author

        if author.voice is None and channel is None:
            return await ctx.send('Either you did not enter a valid channel or you are not in a voice channel! <:beemad:545443640323997717>')

        if channel is None:
            channel = author.voice.channel

        link = discord.utils.escape_markdown(f'https://discordapp.com/channels/{ctx.message.guild.id}/{channel.id}/')
        name = discord.utils.escape_markdown(channel.name)
        e = discord.Embed(colour=author.color,
                          description=f"[Click here to join video session for __**{name}**__]({link})\n"
                                      f"You must be in the voice channel to use this link")

        await ctx.send(embed=e)

    @commands.command(name='shareall')
    async def sharescreen_all(self, ctx):
        """Returns all voice channel's video links"""

        template = f'https://discordapp.com/channels/{ctx.guild.id}/'
        links = [f'[{vc.name}]({template}{vc.id})' for vc in ctx.guild.voice_channels]
        formatted = discord.utils.escape_markdown('\n'.join(links))  # because some ppl like to have ||name|| for some reason

        e = discord.Embed(title="Video Links for all Voice Channels",
                          colour=6430916,
                          description=formatted)

        await ctx.send(embed=e)
        await ctx.send(f'You can use {ctx.prefix}share to get the link for a single voice channel or your current voice channel', delete_after=5)

    @commands.command(name='emojis', aliases=['emotes'])
    async def guild_emojis(self, ctx, codepoint: bool = False):
        """Returns all usable emojis in the guild sorted by name
        Pass in True as a parameter to get codepoints"""
        emojis = sorted([emoji for emoji in ctx.guild.emojis if emoji.require_colons], key=lambda e: e.name)
        paginator = commands.Paginator(suffix='', prefix='')
        paginator.add_line(f'{ctx.invoked_with.capitalize()} of {ctx.guild.name}:')
        if codepoint:
            for emoji in emojis:
                paginator.add_line(f'{emoji} -- {emoji.name} -- `{emoji}`')
        else:
            for emoji in emojis:
                paginator.add_line(f'{emoji} -- {emoji.name}')

        for page in paginator.pages:
            await ctx.send(page)

    @commands.command()
    async def waitfor(self, ctx, channel: Optional[discord.TextChannel], user: discord.Member = None):
        """Wait for a reply to your channel
        Will send you a DM when I see a reply

        - Will not trigger on messages by you or bots
        - Only waits for a max of 24 hours
        - You can specify a channel to wait for in, if none is given, defaults to this channel
        - You can specify a user to only wait for their message, if none is given, defaults to anyone

        `Ex. %waitfor` will wait for a message from anyone in the current channel
        `Ex. %waitfor Bob` will wait for a message from Bob in the current channel
        `Ex. %waitfor #general Bob` will wait for a message from Bob in #general"""
        await ctx.send(f'Waiting for reply from `{user if user is not None else "anyone"}` in {f"`{channel}`" if channel else "this channel"} for up to 24 hours', delete_after=5)
        await ctx.message.add_reaction('<a:typing:559157048919457801>')
        channel = channel or ctx.channel
        try:
            msg = await self.bot.wait_for('message',
                                          check=lambda m: m.channel == channel
                                                          and m.author != ctx.author
                                                          and not m.author.bot
                                                          and (not user or m.author == user),
                                          timeout=86400)
        except TimeoutError:
            try:
                await ctx.message.add_reaction('<:redTick:602811779474522113>')
            except discord.HTTPException:
                pass
        else:
            try:
                await ctx.message.add_reaction('\U00002705')
            except discord.HTTPException:
                pass
            try:
                e = discord.Embed(title=f'You got a reply at: {ctx.guild} | #{channel}',
                                  description=f'{msg.author}: {msg.content}\n'
                                              f'[Jump to message]({msg.jump_url})',
                                  colour=0x0DF33E,
                                  timestamp=datetime.utcnow())
                await ctx.author.send(embed=e)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        query = '''SELECT *
                   FROM guild_config
                   WHERE id = $1'''
        config = await self.bot.pool.fetchrow(query, member.guild.id)
        if config is None:
            return
        if not member.bot:
            if config.get('human_join_role') is not None:
                try:
                    await member.add_roles(discord.Object(id=config.get('human_join_role')),
                                           reason='Auto human join role')
                except discord.Forbidden:
                    pass
        else:
            if config.get('bot_join_role') is not None:
                try:
                    await member.add_roles(discord.Object(id=config.get('bot_join_role')),
                                           reason='Auto bot join role')
                except discord.Forbidden:
                    pass


def setup(bot):
    bot.add_cog(GuildCog(bot))
