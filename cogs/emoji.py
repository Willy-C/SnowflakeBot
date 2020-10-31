import discord
from discord.ext import commands

import io
import random
import zipfile
from typing import Union

from utils.global_utils import is_image


class NoGuildEmojis(commands.CommandError):
    def __init__(self, message=None):
        self.message = message or 'This server does not have any emojis. <:k3llySad:771583555193143326>'


def guild_has_emojis():
    async def predicate(ctx):
        if ctx.guild.emojis:
            return True
        raise NoGuildEmojis
    return commands.check(predicate)


class EmojiCog(commands.Cog, name='Emojis'):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def emoji(self, ctx):
        await ctx.send_help(ctx.command)

    @emoji.command(name='find', aliases=['get', 'search'])
    async def get_emoji(self, ctx, *, name):
        """Find all emojis with the given name
        Also gives its ID and guild"""
        if len(name) < 3 and not await self.bot.is_owner(ctx.author):
            return await ctx.send('Name too short! Please enter at least 3 characters to search')
        name = name.lower()
        found = [emoji for guild in self.bot.guilds for emoji in guild.emojis
                 if name in emoji.name.lower() and emoji.require_colons]
        if found:
            paginator = commands.Paginator(suffix='', prefix='')
            for emoji in found:
                paginator.add_line(f'{emoji} -- {emoji.name} -- `{emoji}` | `{emoji.guild}` ({emoji.guild_id})')
            for page in paginator.pages:
                await ctx.send(page)
        else:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')

    @emoji.command(name='create', aliases=['new'])
    @commands.bot_has_permissions(manage_emojis=True)
    @commands.has_permissions(manage_emojis=True)
    @commands.guild_only()
    async def create_emoji(self, ctx, name, url):
        """Create new emoji from url
        The url must point to a png/jpeg/jpg/gif file
        Example:
        %emoji create arrow https://i.imgur.com/0cptOAb.jpg"""
        url = url.split('?')[0]
        if not await is_image(ctx, url, gif=True):
            return await ctx.send('Invalid file type! Must be one of the following: `.png .jpeg .jpg .gif`')

        if url.endswith('.gif'):
            animated_count = sum([e.animated for e in ctx.guild.emojis])
            if animated_count >= ctx.guild.emoji_limit:
                return await ctx.send('There are no more animated emoji slots!')
        else:
            emoji_count = sum([not e.animated for e in ctx.guild.emojis])
            if emoji_count >= ctx.guild.emoji_limit:
                return await ctx.send('There are no more emoji slots!')

        async with self.bot.session.get(url) as resp:
            if resp.status >= 400:
                return await ctx.send('Could not fetch the image.')
            if int(resp.headers['Content-Length']) >= (256 * 1024):
                return await ctx.send('Image is too big!')
            data = await resp.read()
            try:
                await ctx.guild.create_custom_emoji(name=name, image=data, reason=f'Emoji created by {ctx.author} ({ctx.author.id})')
            except discord.HTTPException as e:
                await ctx.send(f'An error has occurred:\n```{e}```')
            else:
                await ctx.message.add_reaction('\U00002705')

    @emoji.group(name='list', invoke_without_command=True, case_insensitive=True)
    @guild_has_emojis()
    async def guild_emojis(self, ctx, codepoint: bool = False):
        """Returns all usable emojis in the guild sorted by name
        Pass in True as a parameter to get codepoints"""
        if ctx.guild is None:
            await ctx.invoke(self.all_guild_emojis, codepoint)
            return
        emojis = sorted([emoji for emoji in ctx.guild.emojis if emoji.require_colons], key=lambda e: e.name)
        paginator = commands.Paginator(suffix='', prefix='')
        paginator.add_line(f'Emojis of {ctx.guild.name}:')
        if codepoint:
            for emoji in emojis:
                paginator.add_line(f'{emoji} -- {emoji.name} -- `{emoji}`')
        else:
            for emoji in emojis:
                paginator.add_line(f'{emoji} -- {emoji.name}')

        for page in paginator.pages:
            await ctx.send(page)

    @guild_emojis.command(name='big')
    @guild_has_emojis()
    async def guild_emojis_big(self, ctx):
        """Lists all guild emojis without name so they are bigger"""
        emojis = sorted([emoji for emoji in ctx.guild.emojis if emoji.require_colons], key=lambda e: e.name)
        formatted = [str(e) for e in emojis]
        for i in range(0, len(formatted), 27):
            await ctx.send(''.join(formatted[i:i+27]))

    @emoji.command(aliases=['download'])
    @guild_has_emojis()
    async def zip(self, ctx):
        """Download all the emojis in the server into a zip file"""
        await ctx.message.add_reaction('<a:downloading:771280303498985482>')
        zip_buffer = io.BytesIO()
        emojis = sorted([emoji for emoji in ctx.guild.emojis if emoji.require_colons], key=lambda e: e.name)
        with zipfile.ZipFile(zip_buffer, mode='w') as zf:
            for e in emojis:
                emoji_buffer = io.BytesIO(await e.url.read())
                zf.writestr(f'{e.name}.{"png" if not e.animated else "gif"}', emoji_buffer.getvalue())
        zip_buffer.seek(0)
        await ctx.send(f'{ctx.author.mention} Emojis successfully zipped',
                       file=discord.File(zip_buffer, f'emojis-{ctx.guild.id}.zip'))
        await ctx.message.remove_reaction('<a:downloading:771280303498985482>', ctx.me)

    @commands.command(name='bigemoji')
    async def get_emoji_url(self, ctx, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        """Sends a big version of an emoji and it's URL of available"""
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            await ctx.send(str(emoji.url))
        else:
            await ctx.send(emoji)

    @commands.command(name='allemojis', aliases=['allemotes'], hidden=True)
    async def all_guild_emojis(self, ctx, codepoint: bool = False):
        """
        Returns all usable emojis from every guild the bot can see
        Pass in True as a parameter to get codepoints"""
        paginator = commands.Paginator(suffix='', prefix='')

        for guild in sorted(self.bot.guilds, key=lambda g: g.name):
            emojis = sorted([emoji for emoji in guild.emojis if emoji.require_colons], key=lambda e: e.name)

            if not emojis:
                continue
            paginator.add_line(f'__**{guild.name}**__')

            if codepoint:
                for emoji in emojis:
                    paginator.add_line(f'{emoji} -- {emoji.name} -- `{emoji}`')
                paginator.add_line('')
            else:
                for emoji in emojis:
                    paginator.add_line(f'{emoji} -- {emoji.name}')
                paginator.add_line('')

        for page in paginator.pages:
            await ctx.send(page)

    @commands.command()
    async def nitro(self, ctx, *, name):
        """Returns a random emoji with the given name
        Only works with emojis the bot can see/use"""
        name = name.lower()
        found = [emoji for guild in self.bot.guilds for emoji in guild.emojis
                 if emoji.name.lower() == name and emoji.require_colons]

        if found:
            await ctx.send(random.choice(found))
        else:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')

    async def cog_command_error(self, ctx, error):
        if isinstance(error, NoGuildEmojis):
            return await ctx.send(error.message)


def setup(bot):
    bot.add_cog(EmojiCog(bot))
