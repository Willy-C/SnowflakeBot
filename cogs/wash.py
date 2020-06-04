import discord
from discord.ext import commands

GUILD_ID = 528403806984077312
CHANNEL_ID = 528405322168270849
HAD_ID = 299205173878849537
NOTIFY_ROLE = 715623011616555669


class WASHCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._timeout = 7200
        bot.loop.create_task(self.set_last_msg())

    async def set_last_msg(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID)
        try:
            last_msg = await channel.fetch_message(channel.last_message_id)
        except discord.NotFound:
            last_msg = await channel.history(limit=1).flatten()
            self.last_msg = last_msg[0].created_at  # couldn't get last message with ID, use .history
        else:
            self.last_msg = last_msg.created_at

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id != CHANNEL_ID or message.author.bot:
            return

        if abs(message.created_at - self.last_msg).seconds > self._timeout:
            await self.send_alert(message)
        self.last_msg = message.created_at

    async def send_alert(self, message):
        if message.mentions:
            return
        await message.channel.send(f'<@&{NOTIFY_ROLE}> A conversation just started!', delete_after=60)

    # If a new conversation started, then ping
    # new conversation = new message where the previous message is over `self._timeout` seconds old

    @commands.command(name='setalert', hidden=True)
    async def set_timeout(self, ctx, time: int):
        """Send a notification if a new conversation started.
        New conversation = new message where the previous message is over `time` seconds old
        If the new message contains a mention, then notification will not be sent

        Example usage `%setalert 300` - sets the time to be 5 minutes
        """
        if ctx.guild and ctx.guild.id != GUILD_ID:
            return
        if time < 0:
            return await ctx.send(f'Please enter a positive number.')
        self._timeout = time
        await ctx.send(f'I will now send a ping when there is a new message after {time}s of silence')


def setup(bot):
    bot.add_cog(WASHCog(bot))
