import discord
from discord.ext import commands

import io
import random
from typing import Optional


class RNGCog(commands.Cog, name='RNG'):
    def __init__(self, bot):
        self.bot = bot

    # @commands.group()
    # async def random(self, ctx):
    #     if ctx.invoked_subcommand is None:
    #         raise commands.MissingRequiredArgument

    @commands.command(name='randnum', aliases=['randnumber'])
    async def random_num(self, ctx, min: int = 0, max: int = 10):
        """Chooses a random number within a given range.
        Defaults to 0 to 10"""
        if max <= min:
            max, min = min, max
        await ctx.send(random.randint(min, max))

    @commands.command(name='roll')
    async def roll_die(self, ctx, num_rolls: Optional[int] = 1, faces: Optional[int] = 6, sorted: bool = False):
        """Roll a die with Y faces X times.
        Defaults to 1 roll of a 6-side die
        Ex. "%roll 2 20" will roll a 20-sided die twice"""
        if not (1 <= num_rolls <= 999):
            return await ctx.send('Number of Rolls must be between 1 and 999')
        if not (1 <= faces <= 999):
            return await ctx.send('Number of Faces must be between 1 and 999')
        rolls = []
        for _ in range(num_rolls):
            rolls.append(random.randint(1, faces))
        sort = ''
        multi = ''
        if sorted:
            rolls.sort()
            sort = 'Sorted '  # Empty string if unsorted
        if num_rolls != 1:
            multi = 's'
        separator = ' '  # Space between each element in list when outputting

        embed = discord.Embed(colour=discord.Color.dark_teal(),
                              description=f'{sort}Results for rolling a {faces} sided die {num_rolls} time{multi}:')
        embed.add_field(name='Rolls', value=separator.join(str(roll) for roll in rolls))
        embed.add_field(name='Total', value=sum(rolls), inline=False)
        try:
            await ctx.send(embed=embed)
        except discord.errors.HTTPException:
            await ctx.send('Due to discord\'s message character limit, I cannot finish this request.\n'
                           'Please try again with smaller numbers')

    @commands.command(name='choice')
    async def random_choice(self, ctx, *choices: commands.clean_content):
        """Chooses a random element from a list.
        Separate each element by " " or spaces"""
        if len(choices) < 2:
            return await ctx.send('Need more choices to choose from!')

        await ctx.send(random.choice(choices))

    @commands.command()  # Stolen from Danny, just want catto
    async def cat(self, ctx):
        """Sends a random cat."""
        async with self.bot.session.get('https://aws.random.cat/meow') as resp:
            if resp.status != 200:
                return await ctx.send('No cat found :(')
            js = await resp.json()
            await ctx.send(embed=discord.Embed(title='Random Cat').set_image(url=js['file']))

    @commands.command()  # Also stolen from Danno
    async def dog(self, ctx):
        """Gives you a random dog."""
        async with self.bot.session.get('https://random.dog/woof') as resp:
            if resp.status != 200:
                return await ctx.send('No dog found :(')

            filename = await resp.text()
            url = f'https://random.dog/{filename}'
            filesize = ctx.guild.filesize_limit if ctx.guild else 8388608
            if filename.endswith(('.mp4', '.webm')):
                async with ctx.typing():
                    async with self.bot.session.get(url) as other:
                        if other.status != 200:
                            return await ctx.send('Could not download dog video :(')

                        if int(other.headers['Content-Length']) >= filesize:
                            return await ctx.send(f'Video was too big to upload... See it here: {url} instead.')

                        fp = io.BytesIO(await other.read())
                        await ctx.send(file=discord.File(fp, filename=filename))
            else:
                await ctx.send(embed=discord.Embed(title='Random Dog').set_image(url=url))


def setup(bot):
    bot.add_cog(RNGCog(bot))
