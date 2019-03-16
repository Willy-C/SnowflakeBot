import discord
from discord.ext import commands
import time


class UtililtyCog(commands.Cog, name='utilities'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='avatar', aliases=['ava', 'pfp'], brief='Returns the avatar of a user')
    async def get_avatar(self, ctx, *, user: discord.Member = None):
        if user is None:
            user = ctx.author
        await ctx.send(user.avatar_url_as(static_format='png'))

    @get_avatar.error
    async def get_avatar_handler(self, ctx, error):
        if isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("No user found on this server matching that name.\n"
                                  "I will search in this order: \n"
                                  "1.  By ID                          (ex. 5429519026699)\n"
                                  "2. By Mention               (ex. @Snowflake)\n"
                                  "3. By Name#Discrim  (ex. Snowflake#7321)\n"
                                  "4. By Name                   (ex. Snowflake)\n"
                                  "5. By Nickname            (ex. BeepBoop)\n"
                                  "Note: Names are Case-sensitive!")
        else:
            ctx.send(
                "Some unknown error occurred. Please try again, if this error persists, please contact @Willy#7692")

    @commands.command(brief='Gets the ping')
    async def ping(self, ctx):
        start = time.perf_counter()
        message = await ctx.send('Beep...')
        end = time.perf_counter()
        duration = (end - start) * 1000

        await message.edit(content=f'Boop\n'
                                   f'Ping:{duration:.2f}ms')


def setup(bot):
    bot.add_cog(UtililtyCog(bot))
