import discord
from discord.ext import commands

import copy
import colorsys
import random
import pytz
import traceback
from asyncio import TimeoutError
from aiohttp import ClientConnectionError, InvalidURL


async def copy_context(ctx: commands.Context, *, author=None, channel=None, **kwargs):
    """
    Makes a new :class:`Context` with changed message properties.
    """
    # copy the message and update the attributes
    alt_message: discord.Message = copy.copy(ctx.message)
    alt_message._update(kwargs)  # pylint: disable=protected-access

    if author is not None:
        alt_message.author = author
    if channel is not None:
        alt_message.channel = channel

    # obtain and return a context of the same type
    return await ctx.bot.get_context(alt_message, cls=type(ctx))


def bright_color():
    """
    Returns a random discord.Color that does not look ugly or dull
    """
    values = [int(x*255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
    color = discord.Color.from_rgb(*values)
    return color


async def confirm_prompt(ctx: commands.Context, msg):
    """Asks author for confirmation, returns True if confirmed, False if user typed abort or timed out"""
    cont = False

    def confirm(msg):
        nonlocal cont
        if ctx.author.id != msg.author.id or ctx.channel.id != msg.channel.id:
            return False
        if msg.content in ('**confirm**', '**Confirm**', 'confirm', 'Confirm'):
            cont = True
            return True
        elif msg.content in ('**abort**', '**Abort**', 'abort', 'Abort'):
            cont = False  # don't continue
            return True
        return False  # author typed something else in the same channel, keep waiting

    prompt = await ctx.send(f'{msg}\n'
                            f'Please type **confirm** within 1 minute to continue or type **abort** if you change your mind.')

    try:
        reply = await ctx.bot.wait_for('message', check=confirm, timeout=60)
        await reply.delete()
    except TimeoutError:
        await ctx.send('1 minute has passed. Aborting...', delete_after=5)
        return False
    except discord.HTTPException:
        pass
    finally:
        await prompt.delete()

    if not cont:  # Author typed abort, don't continue
        await ctx.send('Aborting...', delete_after=5)

    return cont


def cleanup_code(content):
    """Automatically removes code blocks from the code."""
    # remove ```py\n```
    if content.startswith('```') and content.endswith('```'):
        return '\n'.join(content.split('\n')[1:-1])
    return content.strip('` \n')


async def last_image(ctx):
    """Tries to find the last image in chat and return its url."""
    async for message in ctx.channel.history(limit=50):
        for embed in message.embeds:
            if embed.thumbnail and embed.thumbnail.proxy_url:
                return embed.thumbnail.proxy_url
        for attachment in message.attachments:
            if attachment.proxy_url:
                return attachment.proxy_url


async def is_image(ctx, url, gif=False):
    image_formats = ('image/png', 'image/jpeg', 'image/jpg')
    if gif:
        image_formats += ('image/gif',)
    try:
        async with ctx.bot.session.head(url) as resp:
            return resp.headers['Content-Type'] in image_formats
    except (InvalidURL, KeyError):
        return False


async def upload_hastebin(ctx_or_bot, content, url='https://mystb.in'):
    """Uploads content to hastebin"""
    bot = ctx_or_bot if isinstance(ctx_or_bot, commands.Bot) else ctx_or_bot.bot
    try:
        async with bot.session.post(f'{url}/documents', data=content.encode('utf-8')) as post:
            return f'{url}/{(await post.json())["key"]}'
    except:
        try:
            url = 'https://hastebin.com'
            async with bot.session.post(f'{url}/documents', data=content.encode('utf-8')) as post:
                return f'{url}/{(await post.json())["key"]}'
        except:
            traceback.print_exc()


async def send_or_hastebin(ctx, content, code=None, url='https://mystb.in'):
    """Sends to ctx.channel if possible, upload to hastebin if too long"""
    if code is not None:
        cb = f'```{code}\n{content}\n```'
    else:
        cb = content
    if len(cb) <= 2000:
        await ctx.send(cb)
    else:
        hastebin_url = await upload_hastebin(ctx, content, url)
        await ctx.send(f'Output too long to send to discord, uploaded here instead: {hastebin_url}')


async def get_user_timezone(ctx, user):
    """Returns a pytz.timezone for a user if set, returns None otherwise"""
    query = '''SELECT tz
               FROM timezones
               WHERE "user" = $1;'''
    record = await ctx.bot.pool.fetchrow(query, user.id)
    if record is None:
        return None
    else:
        return pytz.timezone(record.get('tz'))
