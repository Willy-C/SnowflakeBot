import discord
from discord.ext import commands
from jishaku.codeblocks import Codeblock, CodeblockConverter


class GeneralCog(commands.Cog, name='General Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='eval', enabled=False)
    async def _eval(self, ctx, *, args: CodeblockConverter):
        """Evaluates python code in a single line or code block"""
        await ctx.invoke(self.bot.get_command("jsk py"), argument=args)

    @commands.command(brief='Gets the ping')
    async def ping(self, ctx):
        ping = round(self.bot.latency * 1000)
        await ctx.send(f"Ping: `{ping}ms`")

    @commands.command(name='avatar', aliases=['ava', 'pfp'], brief='Returns the avatar of a user')
    async def get_avatar(self, ctx, *, user: discord.Member = None):
        if user is None:
            user = ctx.author  # Defaults to invoker if no user is specified
        avatar_url = user.avatar_url_as(static_format='png')

        embed = discord.Embed(colour=discord.Colour.blurple())
        embed.set_image(url=avatar_url)
        embed.set_author(name=f"{user.display_name}", url=avatar_url)

        await ctx.send(embed=embed)
        # await ctx.send(user.avatar_url_as(static_format='png'))

    @get_avatar.error
    async def get_avatar_handler(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            return await ctx.send("```No user found on this server matching that name.\n"
                                  "I will search in this order: \n"
                                  "1. By ID                     (ex. 5429519026699)\n"
                                  "2. By Mention                (ex. @Snowflake)\n"
                                  "3. By Name#Discrim           (ex. Snowflake#7321)\n"
                                  "4. By Name                   (ex. Snowflake)\n"
                                  "5. By Nickname               (ex. BeepBoop)\n"
                                  "Note: Names are Case-sensitive!```")
        else:
            await ctx.send(
                "Some unknown error occurred. Please try again, if this error persists, please contact @Willy#7692")


def setup(bot):
    bot.add_cog(GeneralCog(bot))
