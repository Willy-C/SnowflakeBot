import discord
from discord.ext import commands

import datetime
from typing import Union

from utils.global_utils import bright_color
from utils.time import human_timedelta
from utils.converters import CaseInsensitiveMember, CachedUserID


class InfoCog(commands.Cog, name='Info'):
    def __init__(self, bot):
        self.bot = bot

    async def get_join_date(self, member: discord.Member):
        query = '''SELECT time
                   FROM first_join
                   WHERE guild = $1
                   AND "user" = $2;'''
        record = await self.bot.pool.fetchrow(query, member.guild.id, member.id)
        if record is None:
            return member.joined_at
        return record['time']

    async def get_usernames(self, user: discord.User):
        query = '''SELECT name, discrim
                   FROM name_changes
                   WHERE id = $1
                   AND changed_at < (CURRENT_DATE + $2::interval) ORDER BY changed_at;'''
        records = await self.bot.pool.fetch(query, user.id, datetime.timedelta(days=90))
        fullnames = {f"{record['name']}#{record['discrim']}" for record in records}
        return ', '.join(fullnames)

    async def get_nicknames(self, member: discord.Member):
        query = '''SELECT name
                   FROM nick_changes
                   WHERE id = $1
                   AND guild = $2
                   AND changed_at < (CURRENT_DATE + $3::interval) ORDER BY changed_at;'''
        records = await self.bot.pool.fetch(query, member.id, member.guild.id, datetime.timedelta(days=90))
        names = {record['name'] for record in records}
        return ', '.join(names)

    @commands.command(name='serverinfo', aliases=['guildinfo'])
    @commands.guild_only()
    async def guild_info(self, ctx):
        guild = ctx.guild
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        roles = ['@everyone']
        roles.extend([role.mention for role in guild.roles[1:]])
        roles = ", ".join(roles)

        e = discord.Embed(title='Server Info', color=bright_color())
        e.set_author(icon_url=guild.icon_url, name=guild.name)

        e.add_field(name='ID', value=guild.id)
        e.add_field(name='Owner', value=guild.owner)
        e.add_field(name='Region', value=guild.region)
        e.add_field(name='Members', value=guild.member_count)
        e.add_field(name='Channels', value=f'{text_channels} Text | {voice_channels} Voice')
        e.add_field(name='Created', value=human_timedelta(guild.created_at))
        e.add_field(name='Roles', value=roles)

        await ctx.send(embed=e)

    @commands.command()
    async def userinfo(self, ctx, *, user: Union[CaseInsensitiveMember, CachedUserID] = None):
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
        e.add_field(name='Severs Shared', value=sum(g.get_member(user.id) is not None for g in self.bot.guilds))
        e.add_field(name='Created', value=human_timedelta(user.created_at))
        if isinstance(user, discord.Member):
            e.add_field(name='First Joined**', value=human_timedelta(await self.get_join_date(user)))
            e.add_field(name='Last Joined', value=human_timedelta(user.joined_at))
            roles = ['@everyone']
            roles.extend(r.mention for r in user.roles[1:])
            e.add_field(name='Roles', value=', '.join(roles))
            e.set_footer(text='**I can only get the earliest join date since I was added to the server')
            nicks = await self.get_nicknames(user)
            if nicks:
                e.add_field(name='Previous Nicknames(within 90days)', value=nicks)
        e.add_field(name='Previous names (within 90days)', value=(await self.get_usernames(user) or str(user)))

        await ctx.send(embed=e)

    @commands.command()
    async def device(self, ctx, member: CaseInsensitiveMember = None):
        member = member or ctx.author
        statuses = {
            discord.Status.online: '<:status_online:602811779948740627> Online',
            discord.Status.offline: '<:status_offline:602811780053336069> Offline',
            discord.Status.idle: '<:status_idle:602811780129095701> Idle',
            discord.Status.dnd: '<:status_dnd:602811779931701259> DND'
        }
        e = discord.Embed(title=f'{member}\'s Status',
                          colour=member.colour)
        e.add_field(name='Desktop Status', value=statuses[member.desktop_status])
        e.add_field(name='Mobile Status', value=statuses[member.mobile_status])
        e.add_field(name='Web Status', value=statuses[member.web_status])

        await ctx.send(embed=e)

    @commands.command()
    async def names(self, ctx, member: Union[CaseInsensitiveMember, CachedUserID] = None):
        member = member or ctx.author
        query = '''SELECT name, discrim
                   FROM name_changes
                   WHERE id = $1
                   ORDER BY changed_at'''
        records = await self.bot.pool.fetch(query, member.id)
        names = {f"{record['name']}#{record['discrim']}" for record in records}
        await ctx.send(f'Names of {member}:\n'
                       f'{", ".join(names)}')

    @commands.command()
    @commands.guild_only()
    async def nicks(self, ctx, member: CaseInsensitiveMember = None):
        member = member or ctx.author
        query = '''SELECT name
                   FROM nick_changes
                   WHERE id = $1
                   AND guild = $2;'''
        records = await self.bot.pool.fetch(query, member.id, ctx.guild.id)
        names = {record['name'] for record in records}
        if not names:
            return await ctx.send(f'Unable to find nicknames for {member} in this server')
        await ctx.send(f'Names of {member}:\n'
                       f'{", ".join(names)}')

    @userinfo.error
    @names.error
    async def userinfo_error(self, ctx, error):
        if isinstance(error, commands.errors.BadUnionArgument):
            ctx.local_handled = True
            return await ctx.send('Unable to find that person')


def setup(bot):
    bot.add_cog(InfoCog(bot))
