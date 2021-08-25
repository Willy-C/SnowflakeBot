import discord
from discord.ext import commands

from typing import Optional
from datetime import datetime
from collections import Counter

from utils.global_utils import bright_color
from utils.converters import CaseInsensitiveMember, CaseInsensitiveChannel


class GuildCog(commands.Cog, name='Server'):
    def __init__(self, bot):
        self.bot = bot

    # Applies commands.guild_only() check for all methods in this cog
    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return True

    @commands.command()
    async def joined(self, ctx, *, member: CaseInsensitiveMember = None):
        """Looks up when a member joined the server."""
        if not member:
            member = ctx.author
        await ctx.send(f'{member.display_name} joined on {member.joined_at.isoformat(" ", "seconds")}')

    @commands.command(name='members', aliases=['memcount', 'membercount'])
    async def member_count(self, ctx):
        """Returns the member count of the guild"""
        statuses = Counter(m.status for m in ctx.guild.members)
        bots = Counter(m.bot for m in ctx.guild.members)
        formatted_statuses = f'<:status_online:602811779948740627> {statuses.get(discord.Status.online, 0)}\n' \
                             f'<:status_offline:602811780053336069> {statuses.get(discord.Status.offline, 0)}\n' \
                             f'<:status_idle:602811780129095701> {statuses.get(discord.Status.idle, 0)}\n' \
                             f'<:status_dnd:602811779931701259> {statuses.get(discord.Status.dnd, 0)}'

        e = discord.Embed(color=bright_color(), timestamp=datetime.utcnow())
        e.set_author(name=f'{ctx.guild}\'s member count',  icon_url=ctx.guild.icon)
        e.add_field(name='Total', value=ctx.guild.member_count)
        e.add_field(name='Humans', value=bots.get(False, 0))
        e.add_field(name='Bots', value=bots.get(True, 0))
        e.add_field(name='Status', value=formatted_statuses)

        await ctx.send(embed=e)

    @commands.command(name='channelperms', aliases=['cperms'])
    async def channel_permissions(self, ctx, channel: Optional[CaseInsensitiveChannel],  *, member: CaseInsensitiveMember = None):
        """Lists permissions of a member in a particular channel.
        If no channel is provided, the current channel will be checked.
        If a member is not provided, the author will be checked."""

        member = member or ctx.author
        channel = channel or ctx.channel

        if channel.type is discord.ChannelType.text:
            voice_perms = ('priority_speaker', 'stream', 'connect', 'speak', 'mute_members', 'deafen_members',
                           'move_members', 'use_voice_activation')
            perms = '\n'.join(f'<:greenTick:602811779835494410> {perm}' if value else f'<:redTick:602811779474522113> {perm}'
                              for perm, value in channel.permissions_for(member) if perm not in voice_perms)
            # Voice permissions are always False in text channels, we will just not show them

        else:
            perms = '\n'.join(f'<:greenTick:602811779835494410> {perm}' if value else f'<:redTick:602811779474522113> {perm}'
                              for perm, value in channel.permissions_for(member))

        e = discord.Embed(title=f'Channel permissions in #{channel}:',
                          description=perms,
                          colour=member.colour)
        e.set_author(icon_url=member.display_avatar.url, name=str(member))
        e.set_footer(text=f'Channel Type: {str(channel.type).capitalize()}')

        await ctx.send(embed=e)

    @commands.command(name='perms')
    async def get_all_permissions(self, ctx, *, member: CaseInsensitiveMember = None):
        """Lists all permissions of a member.
        If a member is not provided, the author will be checked."""
        member = member or ctx.author

        perms = '\n'.join(f'<:greenTick:602811779835494410> {perm}' if value else f'<:redTick:602811779474522113> {perm}'
                          for perm, value in member.guild_permissions)

        e = discord.Embed(title='Server Permissions', description=perms, colour=member.colour)
        e.set_author(icon_url=member.display_avatar.url, name=member)
        await ctx.send(embed=e)

    @commands.command(name='sharescreen', aliases=['share', 'ss', 'video'], hidden=True)
    async def video_in_VC(self, ctx, *, channel: Optional[discord.VoiceChannel] = None):
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

    @commands.command(name='shareall', hidden=True)
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

    @commands.Cog.listener()
    async def on_member_join(self, member):
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
                except (discord.Forbidden, discord.HTTPException):
                    pass
        else:
            if config.get('bot_join_role') is not None:
                try:
                    await member.add_roles(discord.Object(id=config.get('bot_join_role')),
                                           reason='Auto bot join role')
                except (discord.Forbidden, discord.HTTPException):
                    pass


def setup(bot):
    bot.add_cog(GuildCog(bot))
