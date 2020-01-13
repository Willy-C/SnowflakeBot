import discord
from discord.ext import commands

import random
from typing import Union


class EmojiCog(commands.Cog, name='Emoji'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='bigemoji')
    async def get_emoji_url(self, ctx, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        """Returns a given emoji's URL"""
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

    @commands.command(name='getemoji', aliases=['findemoji'])
    async def get_emoji(self, ctx, *, name):
        """Find all emojis with the given name along with its ID and guild"""
        if len(name) < 3 and not self.bot.is_owner(ctx.author):
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


def setup(bot):
    bot.add_cog(EmojiCog(bot))
