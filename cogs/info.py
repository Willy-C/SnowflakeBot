import discord
from discord.ext import commands

import humanize
from datetime import datetime
from typing import Union

from utils.global_utils import bright_color

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='serverinfo', aliases=['guildinfo'])
    @commands.guild_only()
    async def guild_info(self, ctx):
        guild = ctx.guild
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        roles = ", ".join([role.mention for role in guild.roles])

        e = discord.Embed(title='Server Info', color=bright_color())
        e.set_author(icon_url=guild.icon_url, name=guild.name)

        e.add_field(name='ID', value=guild.id)
        e.add_field(name='Owner', value=guild.owner)
        e.add_field(name='Region', value=guild.region)
        e.add_field(name='Members', value=guild.member_count)
        e.add_field(name='Channels', value=f'{text_channels} Text | {voice_channels} Voice')
        e.add_field(name='Created', value=f'{humanize.naturaldelta((datetime.utcnow() - guild.created_at))} ago')
        e.add_field(name='Roles', value=roles)

        await ctx.send(embed=e)

    @commands.command()
    async def userinfo(self, ctx, *, user: Union[discord.Member, discord.User] = None):
        user = user or ctx.author
        if user.color is discord.Color.default():
            color = bright_color()
        else:
            color = user.color
        e = discord.Embed(title='User Info', color=color)
        e.set_author(icon_url=user.avatar_url, name=user)

        e.add_field(name='ID', value=user.id)
        if isinstance(user, discord.Member) and user.nick:
            e.add_field(name='Nick', value=user.nick)
        e.add_field(name='Shared', value=sum(g.get_member(user.id) is not None for g in self.bot.guilds))
        e.add_field(name='Created', value=f'{humanize.naturaldelta((datetime.utcnow() - user.created_at))} ago')
        if isinstance(user, discord.Member):
            e.add_field(name='Joined', value=f'{humanize.naturaldelta((datetime.utcnow() - user.joined_at))} ago')
            e.add_field(name='Roles', value=', '.join(r.mention for r in user.roles))

        await ctx.send(embed=e)

def setup(bot):
    bot.add_cog(InfoCog(bot))
