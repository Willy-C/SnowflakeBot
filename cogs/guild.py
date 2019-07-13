import discord
from discord.ext import commands

from typing import Optional


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

    @commands.command(name='shortperms', hidden=True)
    async def check_permissions(self, ctx, *, member: discord.Member = None):
        """Lists all permissions of a member.
        If a member is not provided, the author will be checked."""

        if not member:
            member = ctx.author
        # Check if the value of each permission is True.
        perms = '\n'.join(perm for perm, value in member.guild_permissions if value)

        # Embeds look nicer
        e = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        e.set_author(icon_url=member.avatar_url, name=str(member))
        # \uFEFF is a Zero-Width Space, which allows us to have an empty field name.
        e.add_field(name='\uFEFF', value=perms)

        await ctx.send(content=None, embed=e)

    @commands.command(name='perms')
    async def check_permissions_long(self, ctx, *, member: discord.Member = None):
        """Lists permissions of a member.
        If a member is not provided, the author will be checked."""
        if not member:
            member = ctx.author
        perms = '\n'.join(f'\U00002705 {perm}' if value else f'<:white_X:555196323574579200> {perm}' for perm, value in
                          member.guild_permissions)

        e = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        e.set_author(icon_url=member.avatar_url, name=str(member))
        e.add_field(name='\uFEFF', value=perms)

        await ctx.send(content=None, embed=e)

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
        # await ctx.message.delete()  # Delete command invocation message

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


    @commands.command()
    async def move(self, ctx, user: discord.Member, *, channel: discord.VoiceChannel = None):
        """Move a user to another voice channel.
        Disconnects user if channel is None.
        Requires Move Members permission to use."""
        if ctx.author.permissions_in(ctx.guild.voice_channels[0]).move_members:
            await user.move_to(channel)
        else:
            return await ctx.send('Sorry, you are missing the Move Members permission.')

def setup(bot):
    bot.add_cog(GuildCog(bot))
