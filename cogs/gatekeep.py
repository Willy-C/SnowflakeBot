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
            role = member.guild.get_role(VERIFIED_ROLE)
            try:
                await member.add_roles(role)
            except (discord.HTTPException, AttributeError) as err:
                await join_channel.send(f'Unable to verify {member}\n```{err}```')

            verified = '<:greenTick:602811779835494410>'
            color = 0x55dd55
        else:
            verified = '<:redTick:602811779474522113>'
            color = 0xdda453

        e = discord.Embed(title='Member Join',
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

        e = discord.Embed(title=f'Member leave',
                          color=discord.Color(0xff0000),
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


def setup(bot):
    bot.add_cog(GatekeepCog(bot))
