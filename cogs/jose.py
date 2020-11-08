import discord
from discord.ext import commands

import asyncio

GUILD_ID = 749462495713820766
EMOJI = '\U0001f621'


class Jose(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """3 'strikes' on an attachment and it gets deleted"""
        if not message.guild or message.guild.id != GUILD_ID or message.author.bot:
            return
        if not message.attachments:
            return
        await message.add_reaction(EMOJI)

        def check(reaction, user):
            if reaction.message.id == message.id and str(reaction.emoji) == EMOJI:
                return reaction.count == 4 or user.id in (self.bot.owner_id, message.guild.owner_id)
            else:
                return False
        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=600)
        except asyncio.TimeoutError:
            try:
                await message.remove_reaction(EMOJI, message.guild.me)
            except discord.HTTPException:
                pass
        else:
            try:
                await message.delete()
            except discord.HTTPException:
                pass


def setup(bot):
    bot.add_cog(Jose(bot))
