import discord
from discord.ext import commands

import datetime
import asyncio
from utils.time import human_timedelta

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
GENERAL_CHANNEL = 709264610200649741
BOT_CHANNEL = 709277913471647824

MOVIE_ROLE = 803011517028237332
LEAGUE_ROLE = 803009777830854677
VALORANT_ROLE = 803009851080310824
SPECIAL_ROLES = [MOVIE_ROLE, LEAGUE_ROLE, VALORANT_ROLE]


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verified = set()
        bot.loop.create_task(self.get_verified_ids())
        self.tasks = {}

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
            await member.add_roles(discord.Object(id=VERIFIED_ROLE), reason='Automatic verification')
            general = member.guild.get_channel(GENERAL_CHANNEL)
            await general.set_permissions(member, read_messages=True, read_message_history=True)

    async def temporary_visibility(self, obj, channel):
        await channel.set_permissions(obj, read_message_history=True, read_messages=True)
        await asyncio.sleep(900)
        await channel.set_permissions(obj, read_message_history=None, read_messages=None)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.guild.id != GUILD_ID:
            return
        if message.author.id == 477572797850189834 and message.content in {"<@542951902669963271>", "<@!542951902669963271>"}:
            return await message.channel.send('Assuming you meant: <@218845228612714499>')

        if message.channel.id != GENERAL_CHANNEL:
            return

        general = message.guild.get_channel(GENERAL_CHANNEL)
        for r in message.role_mentions:
            if r.id in SPECIAL_ROLES:
                task = self.bot.loop.create_task(self.temporary_visibility(r, general))
                if r.id in self.tasks:
                    try:
                        self.tasks.get(r.id).cancel()
                    except asyncio.CancelledError:
                        pass
                self.tasks[r.id] = task

        for u in message.mentions:
            if u.id not in self.verified:
                task = self.bot.loop.create_task(self.temporary_visibility(u, general))
                if u.id in self.tasks:
                    try:
                        self.tasks.get(u.id).cancel()
                    except asyncio.CancelledError:
                        pass
                self.tasks[u.id] = task


def setup(bot):
    bot.add_cog(Gatekeep(bot))
