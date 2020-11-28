import discord
from discord.ext import commands

import json
import datetime
from typing import Union

from utils.global_utils import bright_color, upload_hastebin
from utils.time import human_timedelta
from utils.converters import CaseInsensitiveMember, CachedUserID, MessageConverter, CaseInsensitiveTextChannel, CaseInsensitiveRole


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

        if len(guild.roles) > 30:
            roles = [role.mention for role in reversed(guild.roles[-30:])]
            roles = ", ".join(roles)
            show_roles = f'Top 30/{len(guild.roles)} roles: {roles}, `...`'
        else:
            roles = [role.mention for role in reversed(guild.roles[1:])]
            roles = ", ".join(roles)
            show_roles = f'{len(guild.roles)} roles: {roles}, @everyone'

        e = discord.Embed(title='Server Info', color=bright_color())
        e.set_author(icon_url=guild.icon_url, name=guild.name)

        e.add_field(name='ID', value=guild.id)
        e.add_field(name='Owner', value=guild.owner)
        e.add_field(name='Region', value=guild.region)
        e.add_field(name='Members', value=guild.member_count)
        e.add_field(name='Channels', value=f'{text_channels} Text | {voice_channels} Voice')
        e.add_field(name='Created', value=human_timedelta(guild.created_at))
        e.add_field(name='Roles', value=show_roles)

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
        await ctx.send(f'Nicknames of {member} on `{ctx.guild}`:\n'
                       f'{", ".join(names)}')

    @userinfo.error
    @names.error
    async def userinfo_error(self, ctx, error):
        if isinstance(error, commands.errors.BadUnionArgument):
            ctx.local_handled = True
            return await ctx.send('Unable to find that person')

    @commands.command()
    async def msginfo(self, ctx, message: MessageConverter):
        """Get raw JSON of a message
        Can pass ID, channel-ID or jump url"""
        try:
            msg = await self.bot.http.get_message(message.channel.id, message.id)
        except discord.NotFound:
            return await ctx.send('Unable to find message in that channel')

        raw = json.dumps(msg, indent=2, ensure_ascii=False, sort_keys=True)
        if len(raw) < 1900:
            out = raw.replace("```", "'''")
            await ctx.send(f'```json\n{out}\n```')
        else:
            url = await upload_hastebin(ctx, raw)
            await ctx.send(f'Output too long, uploaded to: {url}.json')

    @commands.command()
    async def topic(self, ctx, *, channel: CaseInsensitiveTextChannel=None):
        """Displays channel topic in chat.
        If no channel is given, defaults to current channel"""
        if channel is None:
            channel = ctx.channel
            add = ''
        else:
            add = f' for {channel.mention}'
        await ctx.send(f'Channel Topic{add}: {channel.topic}' if channel.topic else "No channel topic.",
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.command()
    async def roleinfo(self, ctx, *, role: CaseInsensitiveRole):
        e = discord.Embed(title='Role Info',
                          color=role.color)
        emoji = {True: '<:greenTick:602811779835494410>',
                 False: '<:redTick:602811779474522113>'}
        e.add_field(name='Name', value=role.name)
        e.add_field(name='ID', value=role.id)
        e.add_field(name='Created at', value=f'{role.created_at}\n({human_timedelta(role.created_at)})')
        e.add_field(name='Members', value=len(role.members))
        e.add_field(name='Permissions', value=role.permissions.value)
        e.add_field(name='Position', value=role.position)
        e.add_field(name='Hoisted', value=emoji[role.hoist])
        e.add_field(name='Mentionable', value=emoji[role.mentionable])
        e.add_field(name='Managed', value=emoji[role.managed])
        e.add_field(name='Color', value=role.color)

        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(InfoCog(bot))
