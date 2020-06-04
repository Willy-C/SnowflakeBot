import discord
from discord.ext import commands

import datetime
import asyncio
from utils.time import human_timedelta

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
GENERAL = 709264610200649741
BOT_CHANNEL = 709277913471647824
BF_ROLE = 713953248226050058


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.get_verified_ids())
        self.twom_task = bot.loop.create_task(self.twom_bf_notification_loop())

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
        self.twom_task.cancel()

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

    @commands.command(name='bf')
    async def twom_bf_notify_toggle(self, ctx, toggle:bool=None):
        """Toggles TWOM battlefield notifications
        Example usage: `%bf ON/OFF`

        If neither ON or OFF is specified then defaults to ON"""
        if toggle is None:
            toggle = True

        if toggle:
            if self.twom_task.done():
                self.twom_task = self.bot.loop.create_task(self.twom_bf_notification_loop())
            await ctx.send(f'Next battlefield notification is in **{human_timedelta(self.calculate_next_interval())}**')
        else:
            self.twom_task.cancel()
        await ctx.send(f'Battlefield notifications are now: {"ON" if toggle else "OFF"}')

    async def twom_bf_notification_loop(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(BOT_CHANNEL)
        while not self.bot.is_closed():
            bf_time = self.calculate_next_interval()
            seconds = (bf_time - datetime.datetime.utcnow()).total_seconds()
            await asyncio.sleep(seconds)
            await channel.send(f'<@&{BF_ROLE}> Its time for battlefield!', delete_after=300)
            await discord.utils.sleep_until(datetime.datetime.utcnow().replace(minute=59, second=0, microsecond=0))
            await channel.send(f'<@&{BF_ROLE}> 1 minute left you weebtards', delete_after=60)

    def calculate_next_interval(self):
        now = datetime.datetime.utcnow()
        if now.hour % 2 == 0 and now >= now.replace(minute=55, second=0, microsecond=0):
            now += datetime.timedelta(minutes=5)
        top_hour = now.replace(minute=0, second=0, microsecond=0)
        if top_hour.hour % 2 == 0:
            td = datetime.timedelta(minutes=55)
        else:
            td = datetime.timedelta(hours=1, minutes=55)
        return top_hour + td


def setup(bot):
    bot.add_cog(Gatekeep(bot))
