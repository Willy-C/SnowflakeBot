import discord
from discord.ext import commands

from datetime import datetime
from utils.time import human_timedelta
from utils.converters import CaseInsensitiveMember

GUILD_ID = 561073510127108096
VERIFIED_ROLE = 708140426951131186
JOIN_CHANNEL = 708165506972123168
GENERAL = 708144311711039549


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.get_verified_ids())

    async def get_verified_ids(self):
        query = '''SELECT id FROM gatekeep;'''
        records = await self.bot.pool.fetch(query)
        self.verified = {record.get('id') for record in records}

    def cog_check(self, ctx):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return False
        return True

    # We will just silently ignore commands not used in the guild
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            ctx.local_handled = True

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return

        join_channel = self.bot.get_channel(JOIN_CHANNEL)
        if member.id in self.verified:
            role = discord.Object(id=VERIFIED_ROLE)
            try:
                await member.add_roles(role, reason='Automatic verification')
            except (discord.HTTPException, AttributeError) as err:
                await join_channel.send(f'Unable to verify {member}\n```{err}```')

            verified = '<:greenTick:602811779835494410>'
            title ='Verified Member Join'

        elif member.bot:
            verified = '<:greyTick:602811779810328596>'
            title ='Bot Join'

        else:
            verified = '<:redTick:602811779474522113>'
            title = 'Member Join'

        e = discord.Embed(title=title,
                          color=0x55dd55,
                          timestamp=datetime.utcnow())
        e.set_author(icon_url=member.avatar_url, name=member)

        e.add_field(name='Verified', value=verified)
        e.add_field(name='ID', value=member.id)
        e.add_field(name='Created', value=human_timedelta(member.created_at))

        await join_channel.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id != GUILD_ID:
            return

        e = discord.Embed(title='Member leave',
                          color=0xff0000,
                          timestamp=datetime.utcnow())
        e.set_author(icon_url=member.avatar_url, name=member)

        if member.id in self.verified:
            verified = '<:greenTick:602811779835494410>'
        else:
            verified = '<:redTick:602811779474522113>'

        e.add_field(name='Verified', value=verified)
        e.add_field(name='ID', value=member.id)
        e.add_field(name='Created', value=human_timedelta(member.created_at))
        e.add_field(name='Last Joined', value=human_timedelta(member.joined_at))

        await self.bot.get_channel(JOIN_CHANNEL).send(embed=e)

    @commands.group(invoke_without_command=True, case_insensitive=True, hidden=True)
    async def verify(self, ctx):
        await ctx.send_help(ctx.command)

    @verify.command(name='add')
    async def add(self, ctx, *, member: CaseInsensitiveMember):
        """`Verify a user. This means they will be able to access private channels.`"""
        if ctx.author.id not in self.verified:
            return
        if member.id in self.verified:
            await ctx.send('That person is already verified!')
            return
        role = discord.Object(id=VERIFIED_ROLE)
        await member.add_roles(role, reason=f'Manual Verification by {ctx.author}')
        await ctx.guild.get_channel(GENERAL).send(f'<:member_join:602811779831037952> {ctx.author.mention} added {member.mention}')
        self.verified.add(member.id)
        query = '''INSERT INTO gatekeep(id, by)
                   VALUES($1, $2);'''
        await self.bot.pool.execute(query, member.id, ctx.author.id)

    @verify.command(name='remove', aliases=['kick'])
    async def remove(self, ctx, *, member: CaseInsensitiveMember):
        """`Unverify a user. This means they will lose access to private channels.`"""
        if ctx.author.id not in self.verified:
            return
        if member.id not in self.verified:
            await ctx.send('Sorry, that person is not verified!')
            return
        perms_query = '''SELECT * FROM gatekeep WHERE id=$1'''
        record = await self.bot.pool.fetchrow(perms_query, ctx.author.id)
        if record.get('level') != 'admin':
            await ctx.send('Sorry, you do not have permission to remove users.')
            return
        role = discord.Object(id=VERIFIED_ROLE)
        await member.remove_roles(role, reason=f'Manual Unverification by {ctx.author}')
        await ctx.guild.get_channel(GENERAL).send(f'{ctx.author.mention} removed {member.mention}')
        self.verified.remove(member.id)
        query = '''DELETE FROM gatekeep WHERE id=$1'''
        await self.bot.pool.execute(query, member.id)

    @verify.command(name='list')
    async def _list(self, ctx):
        """`List all currently verified users`"""
        if ctx.author.id not in self.verified:
            return
        query = '''SELECT id FROM gatekeep;'''
        records = await self.bot.pool.fetch(query)
        ids = [record.get('id') for record in records]
        users = [self.bot.get_user(id) for id in ids if self.bot.get_user(id)]
        names = '\n'.join([str(user) for user in users])

        e = discord.Embed(color=45300, title='Verified Users', description=f'```\n{names}\n```')
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Gatekeep(bot))
