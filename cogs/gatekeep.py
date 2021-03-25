import discord
from discord.ext import commands

import asyncio
from utils.global_utils import bright_color

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
GENERAL_CHANNEL = 709264610200649741
BOT_CHANNEL = 709277913471647824
PINS_CHANNEL = 824496525144096768

MOVIE_ROLE = 803011517028237332
LEAGUE_ROLE = 803009777830854677
VALORANT_ROLE = 803009851080310824
SPECIAL_ROLES = [MOVIE_ROLE, LEAGUE_ROLE, VALORANT_ROLE]

PIN_EMOJI = '\U0001f4cc'


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verified = set()
        bot.loop.create_task(self.get_verified_ids())
        self.tasks = {}
        self.pinned = set()

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
        await channel.set_permissions(obj, read_message_history=True, read_messages=True, reason='Pinged')
        await asyncio.sleep(1200)
        await channel.set_permissions(obj, overwrite=None)

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

    def build_embed(self, message: discord.Message):
        e = discord.Embed(description=message.content,
                          color=bright_color(),
                          timestamp=message.created_at)
        if message.embeds:
            msg_embed = message.embeds[0]
            if msg_embed.type == 'image':
                e.set_image(url=msg_embed.url)

        if message.attachments:
            file = message.attachments[0]
            spoiler = file.is_spoiler()
            if not spoiler and file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                e.set_image(url=file.url)
            elif spoiler:
                e.add_field(name='Attachment', value=f'||[{file.filename}]({file.url})||', inline=False)
            else:
                e.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

        e.add_field(name='Original Message', value=f'[Jump!]({message.jump_url})', inline=False)
        e.set_author(name=message.author.display_name, icon_url=message.author.avatar_url_as(format='png'))
        return e

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id != GUILD_ID or payload.channel_id == PINS_CHANNEL:
            return
        if str(payload.emoji) == PIN_EMOJI:
            try:
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            except discord.NotFound:
                return
            for r in message.reactions:
                if str(r) == PIN_EMOJI:
                    count = r.count
                    if count == 1 and message.id not in self.pinned:
                        embed = self.build_embed(message)
                        await self.bot.get_channel(PINS_CHANNEL).send(embed=embed)
                        self.pinned.add(message.id)
                    return


def setup(bot):
    bot.add_cog(Gatekeep(bot))
