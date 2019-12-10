import discord
from discord.ext import commands

import json
import humanize
from datetime import datetime

GUILD_ID = 645121189815255058
VERIFIED_ROLE = 645122149023219712
JOIN_CHANNEL = 645121189815255062


class GatekeepCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('data/verified.json') as f:
            self.verified = set(json.load(f))

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
        e.add_field(name='Created', value=f'{humanize.naturaldelta((datetime.utcnow() - member.created_at))} ago')

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
        e.add_field(name='Created', value=f'{humanize.naturaldelta((datetime.utcnow() - member.created_at))} ago')

        await self.bot.get_channel(JOIN_CHANNEL).send(embed=e)

    @commands.command(hidden=True)
    async def verify(self, ctx, member: discord.Member):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return
        if ctx.author.id not in self.verified:
            await ctx.send('Sorry, you do not have permission to do that!')
            return
        role = discord.Object(id=VERIFIED_ROLE)
        await member.add_roles(role, reason=f'Manual Verification by {ctx.author}')

    @verify.error
    async def verify_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            ctx.local_handled = True
            return await ctx.send('```No user found on this server matching that name.\n'
                                  'I will search in this order: \n'
                                  '1. By ID                     (ex. 5429519026699)\n'
                                  '2. By Mention                (ex. @Snowflake)\n'
                                  '3. By Name#Discrim           (ex. Snowflake#7321)\n'
                                  '4. By Name                   (ex. Snowflake)\n'
                                  '5. By Nickname               (ex. BeepBoop)\n'
                                  'Note: Names are Case-sensitive!```')


def setup(bot):
    bot.add_cog(GatekeepCog(bot))
