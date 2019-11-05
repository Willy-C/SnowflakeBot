import discord
from discord.ext import commands

from datetime import datetime

GUILD_ID = 528403806984077312
CHANNEL_ID = 528405322168270849

HAD_ID = 299205173878849537

class WASHCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.last_msg = datetime.utcnow()
        self._timeout = 3600

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id != CHANNEL_ID or message.author.bot:
            return

        if (message.created_at - self.last_msg).seconds > self._timeout:
            await self.send_alert(message)
        self.last_msg = message.created_at

    async def send_alert(self, message):
        if message.author.id == HAD_ID:
            return
        HD = self.bot.get_user(HAD_ID)
        if HD is not None and HD.mentioned_in(message):
            return
        await message.channel.send(f'<@{HAD_ID}> A conversation just started!')

    # If a new conversation started, then ping
    # new conversation = new message where the previous message is over `self._timeout` seconds old

    @commands.command(name='setalert', hidden=True)
    async def set_timeout(self, ctx, time: int):
        if ctx.guild and ctx.guild.id != GUILD_ID:
            return
        if time < 0:
            return await ctx.send(f'Please enter a positive number.')
        self._timeout = time
        await ctx.send(f'I will now send a ping when there is a new message after {time}s of silence')

def setup(bot):
    bot.add_cog(WASHCog(bot))
