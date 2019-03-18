import discord
from discord.ext import commands

command_attrs = {'hidden': True}


class OwnerCog(commands.Cog, name='Owner Commands', command_attrs=command_attrs):
    def __init__(self, bot):
        self.bot = bot

    # Applies commands.is_owner() check for all methods in this cog
    async def cog_check(self, ctx):
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner('You do not own this bot.')
        return True

    @commands.command(name='load')
    async def load_cog(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** loaded {cog}')

    @commands.command(name='unload')
    async def unload_cog(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** unloaded {cog}')

    @commands.command(name='reload')
    async def reload_cog(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS`** reloaded {cog}')


def setup(bot):
    bot.add_cog(OwnerCog(bot))
