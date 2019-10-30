import discord
from discord.ext import commands

import datetime
from datetime import datetime

GUILD_ID = 528403806984077312
CHANNEL_ID = 528405322168270849

HAD_ID = 299205173878849537

class WASHCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.last_msg = datetime.utcnow()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.guild.id != GUILD_ID or message.channel.id != CHANNEL_ID or message.author.bot:
            return

        if (message.created_at - self.last_msg).seconds > 7200:
            await self.send_alert(message.channel)
        self.last_msg = message.created_at

    async def send_alert(self, target):
        await target.send(f'<@{HAD_ID}> A conversation just started!')

    # If a new conversation started, then ping
    # new conversation = new message where the previous message is over 2 hours old


def setup(bot):
    bot.add_cog(WASHCog(bot))
