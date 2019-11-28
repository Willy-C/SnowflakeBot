import discord
from discord.ext import commands

import re
import aiohttp

class RedditCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.subreddit = re.compile(r'(^|\s)/?r/(?P<sub>\w{2,21})($|\s)')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        match = self.subreddit.search(message.content)
        if match is not None:
            url = f'https://www.reddit.com/r/{match.group("sub")}'
            async with self.bot.session.get(f'{url}.json') as r:
                results = await r.json()
            try:
                if results['data']['children']:
                    await message.channel.send(url)
            except KeyError:
                return


def setup(bot):
    bot.add_cog(RedditCog(bot))
