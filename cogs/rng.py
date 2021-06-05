import discord
from discord.ext import commands

import re
import random
import operator

from utils.global_utils import upload_hastebin

DICE_NOTATION_REGEX = re.compile(r'(\d+)d(\d+)(([+-])(\d+|l|h))?', re.IGNORECASE)

operators = {'+': operator.add,
             '-': operator.sub}


class DiceRoll(commands.Converter):
    async def convert(self, ctx, argument):
        match = DICE_NOTATION_REGEX.fullmatch(argument)
        if not match:
            raise commands.BadArgument(f'Invalid dice notation. See {ctx.prefix}help dice for more info')

        dice, faces, _, operator, modifier = match.groups()  # 1d2-3 -> (1, 2, -3, -, 3) (num_dice, faces, _, operator, modifier)
        if modifier and modifier.isnumeric():
            modifier = int(modifier)
        elif modifier is not None:
            if operator != '-':
                raise commands.BadArgument(f'Invalid dice notation. Modifier must be `-` when using H/L.')
        return int(dice), int(faces), operator, modifier


class RNG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True, case_insensitive=True, aliases=['rand'])
    async def random(self, ctx):
        """RNG"""
        await ctx.send_help(ctx.command)

    @random.command(name='number', aliases=['num'])
    async def random_number(self, ctx, min: int = 0, max: int = 10):
        """Chooses a random number within a given range (inclusive).
        Defaults to 0 to 10"""
        if max < min:
            max, min = min, max
        await ctx.send(f'Random number between {min}-{max} (inclusive): {random.randint(min, max)}')

    @random.command(name='choice')
    async def random_choice_group(self, ctx, *choices: commands.clean_content):
        """Chooses a random element from a list.
        Separate each element by " " or spaces"""
        await self.random_choice(ctx, choices=choices)

    @commands.command(name='coin')
    async def coin_flip(self, ctx):
        """Flip a coin"""
        await ctx.send(random.choice(('Heads', 'Tails')))

    @commands.command(name='dice', aliases=['roll'])
    async def dice_roll(self, ctx, diceroll: DiceRoll = '1d6', sorted: bool=False):
        """Rolls a dice with [**standard dice notation**](https://en.wikipedia.org/wiki/Dice_notation)
        Add True at the end to sort rolls

        Example usage:
        `1d20` = Roll a 20-sided die
        `10d20 true` = Roll 10 20-sided dice and sort the results
        `2d6+4` = Roll 2 6-sided dice and then subtract 4 from the result
        `4d12-L` = Roll 4 12-sided dice and then drop the lowest number

        AdX (±B)/(-L/H)
        A = number of dice
        X = number of faces on each die
        B = number to add/subtract to the sum of the dice
        -L/H = drop the lowest or highest result
        """
        # Converter not automatically called when arg is not provided, we will just shortcut it instead
        if diceroll == '1d6':
            dice, faces, operator, modifier = (1, 6, None, None)
        else:
            dice, faces, operator, modifier = diceroll

        if not (1 <= dice <= 9999):
            return await ctx.send('Number of Dice must be between 1 and 9999')
        if not (1 <= faces <= 9999):
            return await ctx.send('Number of Faces must be between 1 and 9999')

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

        if sorted:
            rolls.sort()

        all_rolls = ' '.join([str(r) for r in rolls])
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
    bot.add_cog(RNG(bot))
