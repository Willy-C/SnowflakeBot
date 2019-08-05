import discord
from discord.ext import commands


class AvatarCog(commands.Cog, name='General'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='avatar', aliases=['ava', 'pfp'])
    async def get_avatar(self, ctx, *, user: discord.Member = None):
        """Retrieves the avatar of a user.
        Defaults to author if no user is provided."""

        user = ctx.author if user is None else user  # Defaults to invoker if no user is specified

        avatar_url = user.avatar_url_as(static_format='png')

        embed = discord.Embed(colour=user.colour)
        embed.set_image(url=avatar_url)
        embed.set_author(name=user.display_name, url=avatar_url)

        await ctx.send(embed=embed)
        # await ctx.send(user.avatar_url_as(static_format='png'))

    @get_avatar.error
    async def get_avatar_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            return await ctx.send('```No user found on this server matching that name.\n'
                                  'I will search in this order: \n'
                                  '1. By ID                     (ex. 5429519026699)\n'
                                  '2. By Mention                (ex. @Snowflake)\n'
                                  '3. By Name#Discrim           (ex. Snowflake#7321)\n'
                                  '4. By Name                   (ex. Snowflake)\n'
                                  '5. By Nickname               (ex. BeepBoop)\n'
                                  'Note: Names are Case-sensitive!```')
        else:
            await ctx.send(
                'Some unknown error occurred. Please try again, if this error persists, please contact @Willy#7692')


def setup(bot):
    bot.add_cog(AvatarCog(bot))
