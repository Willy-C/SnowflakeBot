from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from main import SnowflakeBot

GUILD_ID = 528403806984077312
CHANNEL_ID = 528405322168270849
NOTIFY_ROLE = 715623011616555669


class WASHCog(commands.Cog):

    def __init__(self, bot):
        self.bot: SnowflakeBot = bot
        self._timeout: int = 7200
        bot.loop.create_task(self.set_last_msg())

    async def set_last_msg(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID)
        try:
            last_msg = await channel.fetch_message(channel.last_message_id)
        except discord.NotFound:
            last_msg = await channel.history(limit=1).__anext__()
            self.last_msg = last_msg.created_at  # couldn't get last message with ID, use .history
        else:
            self.last_msg = last_msg.created_at

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != CHANNEL_ID or message.author.bot:
            return

        if abs(message.created_at - self.last_msg).seconds > self._timeout:
            await self.send_alert(message)
        self.last_msg = message.created_at

    async def send_alert(self, message: discord.Message) -> None:
        if message.mentions or message.flags.silent:
            return
        await message.channel.send(f'<@&{NOTIFY_ROLE}> A conversation just started!',
                                   delete_after=30,
                                   allowed_mentions=discord.AllowedMentions(roles=True)
                                   )

    # If a new conversation started, then ping
    # new conversation = new message where the previous message is over `self._timeout` seconds old


async def setup(bot: SnowflakeBot) -> None:
    await bot.add_cog(WASHCog(bot))
