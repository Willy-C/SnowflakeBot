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
            color = 0x55dd55
            title ='Verified Member Join'

        elif member.bot:
            verified = '<:greenTick:602811779835494410>'
            color = 0x55dd55
            title ='Bot Join'

        else:
            verified = '<:redTick:602811779474522113>'
            color = 0xdda453
            title = 'Member Join'

        e = discord.Embed(title=title,
                          color=color,
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

        await self.bot.get_channel(JOIN_CHANNEL).send(embed=e)

    @commands.command(hidden=True)
    async def verify(self, ctx, *, member: CaseInsensitiveMember):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return
        if ctx.author.id not in self.verified:
            await ctx.send('Sorry, you do not have permission to do that!')
            return
        role = discord.Object(id=VERIFIED_ROLE)
        await member.add_roles(role, reason=f'Manual Verification by {ctx.author}')
        await ctx.guild.get_channel(GENERAL).send(f'<:member_join:602811779831037952> {ctx.author.mention} added {member.mention}')
        query = '''INSERT INTO gatekeep(id, by)
                   VALUES($1, $2);'''
        await self.bot.pool.execute(query, member.id, ctx.author.id)

    @commands.command(hidden=True)
    async def unverify(self, ctx, *, member: CaseInsensitiveMember):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return
        if ctx.author.id not in self.verified:
            await ctx.send('Sorry, you do not have permission to do that!')
            return
        if member.id not in self.verified:
            await ctx.send('Sorry, that person is not verified!')
            return

        perms_query = '''SELECT * FROM gatekeep WHERE id=$1'''
        record = self.bot.pool.fetchrow(perms_query, ctx.author.id)
        if record.get('level') is None or record.get('level') != 'admin':
            await ctx.send('Sorry, you do not have permission to unverify users.')
            return

        try:
            role = discord.Object(id=VERIFIED_ROLE)
            await member.remove_roles(role, reason=f'Manual Unverification by {ctx.author}')
        except discord.HTTPException:
            pass
        await ctx.guild.get_channel(GENERAL).send(f'{ctx.author.mention} removed {member.mention}')
        query = '''DELETE FROM gatekeep WHERE id=$1'''
        await self.bot.pool.execute(query, member.id)


def setup(bot):
    bot.add_cog(Gatekeep(bot))
