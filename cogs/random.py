import discord
from discord.ext import commands

import re
import random
import operator

from utils.global_utils import upload_hastebin

DICE_NOTATION_REGEX = re.compile(r'(\d+)d(\d+)\s?(([+-])(\d+|l|h))?')

operators = {'+': operator.add,
             '-': operator.sub}


class DiceRoll(commands.Converter):
    async def convert(self, ctx, argument):
        match = DICE_NOTATION_REGEX.fullmatch(argument)
        if not match:
            raise commands.BadArgument(f'Invalid dice notation. See {ctx.prefix}help dice for more info')
        dice, faces, _, operator, modifier = match.groups() # 1d2-3 -> (1, 2, -3, -, 3 ) (num_dice, faces, _, operator, modifier)
        if modifier.isnumeric():
            modifier = int(modifier)
        else:
            if operator != '-':
                raise commands.BadArgument(f'Invalid dice notation. Modifier must be `-` when using H/L.')
        return int(dice), int(faces), operator, modifier


class RNGCog(commands.Cog, name='Rng'):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True, case_insensitive=True, aliases=['rand'])
    async def random(self, ctx):
        await ctx.send_help(ctx.command)

    @random.command(name='number', aliases=['num'])
    async def random_number(self, ctx, min: int = 0, max: int = 10):
        """Chooses a random number within a given range.
        Defaults to 0 to 10"""
        if max <= min:
            max, min = min, max
        await ctx.send(f'Random number between {min}-{max}: {random.randint(min, max)}')

    @random.command(name='choice')
    async def random_choice_group(self, ctx, *choices: commands.clean_content):
        await self.random_choice(ctx, choices=choices)

    @commands.command(name='dice', aliases=['roll'])
    async def dice_roll(self, ctx, diceroll: DiceRoll, sorted: bool=False):
        """Rolls a dice with standard dice notation
        AdX (±B L/H)
        A = number of dice
        X = number of faces on each die
        B = number to add/subtract to the sum of the dice
        -L/H = drop the lowest or highest result
        Example usage:
        `1d20` = Roll a 20-sided die
        `2d6+4` = Roll 2 6-sided dice and then subtract 4 from the result
        `4d12-L` = Roll 4 12-sided dice and then drop the lowest number
        """
        dice, faces, operator, modifier = diceroll

        if not (1 <= dice <= 999):
            return await ctx.send('Number of Dice must be between 1 and 999')
        if not (1 <= faces <= 999):
            return await ctx.send('Number of Faces must be between 1 and 999')

        rolls = []
        for _ in range(dice):
            rolls.append(random.randint(1, faces))
        dsum = sum(rolls)

        if operator:
            if isinstance(modifier, int):
                final = operators[operator](dsum, modifier)
                output = f'{dsum} {operator} {modifier} = **{final}**'
            elif modifier.lower() == 'l':
                removed = min(rolls)
                output = f'{dsum} - {removed} (dropped lowest) = {dsum-removed}'
            elif modifier.lower() == 'h':
                removed = max(rolls)
                output = f'{dsum} - {removed} (dropped highest) = {dsum-removed}'
            else:
                raise commands.CommandError('Something went terribly wrong. Sorry')
        else:
            output = dsum

        all_rolls = ' '.join(rolls)
        if len(all_rolls) >= 1000:
            url = await upload_hastebin(ctx, all_rolls)
            all_rolls = f'Too many rolls to display here. Uploaded to here instead: {url}'

        sort = 'Sorted ' if sorted else ''
        die = 'dice' if dice > 1 else 'die'
        embed = discord.Embed(colour=discord.Color.dark_teal(),
                              title=f'{sort}Results for rolling {dice} {faces}-sided {die}:')
        embed.add_field(name='Rolls', value=all_rolls)
        embed.add_field(name='Sum', value=output, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='choice')
    async def random_choice(self, ctx, *choices: commands.clean_content):
        """Chooses a random element from a list.
        Separate each element by " " or spaces"""
        if len(choices) < 2:
            return await ctx.send('Need more choices to choose from!')

        await ctx.send(random.choice(choices))


def setup(bot):
    bot.add_cog(RNGCog(bot))
