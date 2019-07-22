import copy

import discord
from discord.ext import commands

import colorsys
import random


async def copy_context(ctx: commands.Context, *, author=None, channel=None, **kwargs):
    """
    Makes a new :class:`Context` with changed message properties.
    """
    # copy the message and update the attributes
    alt_message: discord.Message = copy.copy(ctx.message)
    alt_message._update(channel or alt_message.channel, kwargs)  # pylint: disable=protected-access

    if author is not None:
        alt_message.author = author

    # obtain and return a context of the same type
    return await ctx.bot.get_context(alt_message, cls=type(ctx))


def bright_color():
    """
    Returns a random discord.Color that does not look ugly or dull
    """
    values = [int(x*255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
    color = discord.Color.from_rgb(*values)
    return color
