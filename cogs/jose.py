import discord
from discord.ext import commands

import asyncio

GUILD_ID = 749462495713820766


class Jose(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.guild.id != GUILD_ID or message.author.bot:
            return
        if not message.attachments:
            return
        await message.add_reaction('\U0001f621')

        def check(reaction, user):
            if reaction.message.id == message.id and str(reaction.emoji) == '\U0001f621':
                return reaction.count == 4 or user.id in (self.bot.owner_id, message.guild.owner_id)
            else:
                return False
        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=900)
        except asyncio.TimeoutError:
            await message.remove_reaction('\U0001f621', message.guild.me)
        else:
            try:
                await message.delete()
            except discord.HTTPException:
                pass


def setup(bot):
    bot.add_cog(Jose(bot))
