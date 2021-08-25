import traceback
import discord
from discord.ext import commands


def get_mention(ctx, record, obj):
    if record.get(obj) is None:
        return
    id = record.get(obj)
    channel = ctx.guild.get_channel(id)
    role = ctx.guild.get_role(id)
    if channel is not None:
        return channel.mention
    elif role is not None:
        return role.mention


class GuildConfig(commands.Cog, name='Settings'):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return ctx.author.guild_permissions.manage_guild or await ctx.bot.is_owner(ctx.author)

    @commands.group(name='config', invoke_without_command=True, case_insensitive=True)
    async def guild_config(self, ctx):
        """Set server config"""
        query = '''SELECT * FROM
                   guild_config g FULL OUTER JOIN guild_mod_config m ON g.id = m.id
                   WHERE g.id=$1 OR m.id=$1'''
        record = await self.bot.pool.fetchrow(query, ctx.guild.id)
        if record is None:
            record = {}
        e = discord.Embed(title='Server Config',
                          colour=discord.Colour.blue())

        roles = f'Human: {get_mention(ctx, record, "human_join_role")}\n' \
                f'Bots: {get_mention(ctx, record, "bot_join_role")}\n' \
                f'Mute: {get_mention(ctx, record, "mute_role")}'

        channels = f'Welcome: {get_mention(ctx, record, "join_ch")}\n' \
                   f'Leave: {get_mention(ctx, record, "leave_ch")}\n' \
                   f'Invites: {get_mention(ctx, record, "invite_ch")}'

        e.add_field(name='Roles', value=roles)
        e.add_field(name='Channels', value=channels)
        e.set_footer(text=f'see "{ctx.prefix}help config" for more info')
        await ctx.send(embed=e)

    # Roles

    @guild_config.group(name='role', case_insensitive=True)
    async def set_role(self, ctx):
        """Set join role for human or bots or set a mute role

        NOTE: To remove a setting, don't provide a role (Ex. `%config role human`)"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @set_role.command(name='human')
    async def set_human_role(self, ctx, *, role: discord.Role = None):
        """Set human join role
        Ex. `%config role human @plebs`"""
        if role is not None:
            role_id = role.id
        else:
            role_id = None
        query = '''INSERT INTO guild_config(id, human_join_role)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE 
                   SET human_join_role = $2; 
                   '''
        try:
            await self.bot.pool.execute(query, ctx.guild.id, role_id)
        except:
            await ctx.send('An error occurred')
            traceback.print_exc()
        else:
            if role is None:
                await ctx.send()
            await ctx.send(f'Human Join Role is now set to: {role}')

    @set_role.command(name='bot', aliases=['bots'])
    async def set_bot_role(self, ctx, *, role: discord.Role = None):
        """Set bot join role
        Ex. `%config role bot @botto`"""
        if role is not None:
            role_id = role.id
        else:
            role_id = None
        query = '''INSERT INTO guild_config(id, bot_join_role)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE 
                   SET bot_join_role = $2; 
                   '''
        try:
            await self.bot.pool.execute(query, ctx.guild.id, role_id)
        except:
            await ctx.send('An error occurred')
            traceback.print_exc()
        else:
            await ctx.send(f'Bot Join Role is now set to: {role}')

    @set_role.command(name='mute')
    async def set_mute_role(self, ctx, *, role: discord.Role = None):
        """Set mute role for moderation"""
        if role is not None:
            role_id = role.id
        else:
            role_id = None
        query = '''INSERT INTO guild_mod_config(id, mute_role)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE 
                   SET mute_role = $2; 
                   '''
        try:
            await self.bot.pool.execute(query, ctx.guild.id, role_id)
        except:
            await ctx.send('An error occurred')
            traceback.print_exc()
        else:
            await ctx.send(f'Mute role is now set to: {role}')

    # Channels

    @guild_config.group(name='channel', case_insensitive=True)
    async def set_channel(self, ctx):
        """Set channel for join and leave logs or invite tracker

        NOTE: To remove a setting, don't provide a channel (Ex. `%config channel join`)"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @set_channel.command(name='join', aliases=['welcome'])
    async def set_join_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set channel for join logs"""
        if channel is not None:
            channel_id = channel.id
            mention = channel.mention
        else:
            channel_id = None
            mention = None
        query = '''INSERT INTO guild_mod_config(id, join_ch)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE 
                   SET join_ch = $2; 
                   '''
        try:
            await self.bot.pool.execute(query, ctx.guild.id, channel_id)
        except:
            await ctx.send('An error occurred')
            traceback.print_exc()
        else:
            await ctx.send(f'Join logs will now go to: {mention}')

    @set_channel.command(name='leave')
    async def set_leave_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set channel for leave logs"""
        if channel is not None:
            channel_id = channel.id
            mention = channel.mention
        else:
            channel_id = None
            mention = None
        query = '''INSERT INTO guild_mod_config(id, leave_ch)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE 
                   SET leave_ch = $2; 
                   '''
        try:
            await self.bot.pool.execute(query, ctx.guild.id, channel_id)
        except:
            await ctx.send('An error occurred')
            traceback.print_exc()
        else:
            await ctx.send(f'Leave logs will now go to: {mention}')

    @set_channel.command(name='invite', aliases=['invites'])
    async def set_invite_tracker_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set channel for invite tracker"""
        if channel is not None:
            channel_id = channel.id
            mention = channel.mention
        else:
            channel_id = None
            mention = None
        query = '''INSERT INTO guild_mod_config(id, join_ch)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE 
                   SET invite_ch = $2; 
                   '''
        try:
            await self.bot.pool.execute(query, ctx.guild.id, channel_id)
        except:
            await ctx.send('An error occurred')
            traceback.print_exc()
        else:
            await ctx.send(f'Invite tracker will now output to: {mention}')


def setup(bot):
    bot.add_cog(GuildConfig(bot))
