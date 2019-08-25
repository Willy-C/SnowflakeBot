import discord
from discord.ext import commands

from typing import Optional
from datetime import datetime

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

    @commands.command(name='membercount', aliases=['memcount'])
    async def member_count(self, ctx):
        """Returns the member count of the guild"""
        members = ctx.guild.members
        statuses = f'<:status_online:602811779948740627> {sum([1 for m in members if m.status is discord.Status.online])}\n' \
                    f'<:status_offline:602811780053336069> {sum([1 for m in members if m.status is discord.Status.offline])}\n' \
                    f'<:status_idle:602811780129095701> {sum([1 for m in members if m.status is discord.Status.idle])}\n' \
                    f'<:status_dnd:602811779931701259> {sum([1 for m in members if m.status is discord.Status.dnd])}'

        e = discord.Embed(color=bright_color(), timestamp=datetime.utcnow())
        e.set_author(name=f'{ctx.guild}\'s member count',  icon_url=ctx.guild.icon_url)
        e.add_field(name='Total', value=ctx.guild.member_count)
        e.add_field(name='Humans', value=str(sum([1 for m in members if not m.bot])))
        e.add_field(name='Bots', value=str(sum([1 for m in members if m.bot])))
        e.add_field(name='Status', value=statuses)

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
        # \uFEFF = Zero-Width Space
        e.add_field(name='\uFEFF', value=perms)

        await ctx.send(embed=e)

    @commands.command(name='perms')
    async def all_permissions(self, ctx, *, member: discord.Member = None):
        """Lists all permissions of a member.
        If a member is not provided, the author will be checked."""
        if not member:
            member = ctx.author
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

        _vc = [vc for vc in ctx.guild.voice_channels]
        guild_id = ctx.guild.id
        template = f'https://discordapp.com/channels/{guild_id}/'
        links = [f'[{vc.name}]({template}{vc.id})' for vc in _vc]
        combined = '\n'.join(links)
        formatted = discord.utils.escape_markdown(combined)  # because some ppl like to have ||name|| for some reason

        e = discord.Embed(title="Video Links for all Voice Channels",
                          colour=6430916,
                          description=formatted)

        await ctx.send(embed=e)
        await ctx.send(f'You can use {ctx.prefix}share to get the link for a single voice channel or your current voice channel', delete_after=5)

    @commands.command(name='emojis')
    async def guild_emojis(self, ctx, codepoint: bool = False):
        """Returns all emojis in the guild sorted by name
        Pass in True as a parameter to get codepoints"""
        emojis = sorted(ctx.guild.emojis, key=lambda e: e.name)
        paginator = commands.Paginator(suffix='', prefix='')
        paginator.add_line(f'Emojis of {ctx.guild.name}:')
        if codepoint:
            for emoji in emojis:
                paginator.add_line(f'{emoji} -- {emoji.name} -- `{emoji}`')
        else:
            for emoji in emojis:
                paginator.add_line(f'{emoji} -- {emoji.name}')

        for page in paginator.pages:
            await ctx.send(page)


def setup(bot):
    bot.add_cog(GuildCog(bot))
