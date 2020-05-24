import discord
from discord.ext import commands, tasks

import datetime
import asyncio
from utils.time import human_timedelta

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
GENERAL = 709264610200649741
BF_ROLE = 713953248226050058


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.get_verified_ids())
        self.twom_bf_notify_loop.start()

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

    def cog_unload(self):
        self.twom_bf_notify_loop.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return

        if member.id in self.verified:
            role = discord.Object(id=VERIFIED_ROLE)
            try:
                await member.add_roles(role, reason='Automatic verification')
            except (discord.HTTPException, AttributeError) as err:
                pass

    @commands.command(name='battlefield', aliases=['bf'])
    async def twom_bf_notify_toggle(self, ctx, toggle:bool=None):
        """Toggles TWOM battlefield notifications
        Example usage: `%bf ON/OFF`

        If neither ON or OFF is specified then defaults to ON"""
        if toggle is None:
            toggle = True

        if toggle:
            try:
                self.twom_bf_notify_loop.start()
            except RuntimeError:
                pass
            await ctx.send(f'Next battlefield notification is in **{human_timedelta(self.calculate_next_interval())}**')
        else:
            self.twom_bf_notify_loop.cancel()
        await ctx.send(f'Battlefield notifications are now: {"ON" if toggle else "OFF"}')

    @tasks.loop(hours=2)
    async def twom_bf_notify_loop(self):
        channel = self.bot.get_channel(GENERAL)
        await channel.send(f'<@&{BF_ROLE}> Its time for battlefield!', delete_after=600)

    @twom_bf_notify_loop.before_loop
    async def before_bf_loop(self):
        await self.bot.wait_until_ready()
        bf_time = self.calculate_next_interval()
        seconds = (bf_time - datetime.datetime.utcnow()).total_seconds()
        await asyncio.sleep(seconds)

    def calculate_next_interval(self):
        top_hour = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        if top_hour.hour % 2 == 0:
            td = datetime.timedelta(minutes=55)
        else:
            td = datetime.timedelta(hours=1, minutes=55)
        return top_hour + td


def setup(bot):
    bot.add_cog(Gatekeep(bot))
