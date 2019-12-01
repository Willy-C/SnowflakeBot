import discord
from discord.ext import commands, tasks

import json
import re


class PrefixCog(commands.Cog, name='Prefix'):
    def __init__(self, bot):
        self.bot = bot
        self.save_prefixes_to_json.start()
        bot.loop.create_task(self.set_mention_regex())

    async def set_mention_regex(self):
        await self.bot.wait_until_ready()
        self.mention = re.compile(r'<@!?' + str(self.bot.user.id) + r'>')

    def save_prefixes(self):
        with open('data/prefixes.json', 'w') as f:
            json.dump(self.bot.prefixes, f, indent=2)

    @commands.group(invoke_without_command=True)
    async def prefix(self, ctx):
        await ctx.send_help(ctx.command)

    @prefix.command()
    @commands.guild_only()
    async def set(self, ctx, *new_prefixes):
        """Set my prefix(es) for this guild.
        Separate multiple prefixes with spaces."""
        self.bot.prefixes[ctx.guild.id] = list(new_prefixes)
        await ctx.send(f'This guild\'s prefix is set to {", ".join(new_prefixes)}\n')
        await ctx.send(f'Note: Mentioning the bot will always be a valid prefix. Ex: {self.bot.user.mention} ping', delete_after=10)

    @prefix.command(aliases=['clear'])
    @commands.guild_only()
    async def reset(self, ctx):
        """Reset my prefix for this guild to the default"""
        try:
            del self.bot.prefixes[ctx.guild.id]
            await ctx.send('Prefix for this guild has been reset. Default: %')
            await ctx.send(f'Note: Mentioning the bot will always be a valid prefix. Ex: {self.bot.user.mention} ping', delete_after=10)

        except KeyError:
            await ctx.send('This guild is already using the default prefix: %')

    @prefix.command()
    @commands.guild_only()
    async def add(self, ctx, *new_prefixes):
        """Add new prefix(es) for this guild.
        Separate multiple prefixes with spaces."""
        # self.bot.prefixes.setdefault(ctx.guild.id, ['%']).extend(new_prefixes)

        current = self.bot.prefixes.setdefault(ctx.guild.id, ['%'])
        added = []
        for prefix in new_prefixes:
            if prefix not in current:
                current.append(prefix)
                added.append(prefix)
        if added:
            await ctx.send(f'Added {", ".join(added)} to this guild\'s prefixes')
        else:
            await ctx.send('No new prefix has been added')

    @prefix.command(aliases=['rem'])
    @commands.guild_only()
    async def remove(self, ctx, prefix_to_remove):
        """Remove a prefix for this guild. """
        if ctx.guild.id not in self.bot.prefixes:
            return await ctx.send('This guild does not have any custom prefix configured')
        if prefix_to_remove in self.bot.prefixes[ctx.guild.id]:
            self.bot.prefixes[ctx.guild.id].remove(prefix_to_remove)
            if not self.bot.prefixes[ctx.guild.id]:
                del self.bot.prefixes[ctx.guild.id]
        else:
            return await ctx.send('This is not an existing prefix!')

    @prefix.command()
    async def list(self, ctx):
        """Lists my prefixes here"""
        await self._list_prefixes(ctx.message)
        await ctx.send(f'\u200b\nYou can always use my mention as a prefix!\n'
                       f'For example: {self.bot.user.mention} ping\n\n'
                       f'Or just mention me and I will tell you my prefix', delete_after=15)

    @prefix.command()
    @commands.is_owner()
    async def save(self, ctx):
        try:
            self.save_prefixes()
        except:
            await ctx.send('An error has occurred ')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        match = self.mention.fullmatch(message.content)
        if match:
            await self._list_prefixes(message)
            await message.channel.send(f'You can always use my mention as a prefix!\n'
                                       f'For example: {self.bot.user.mention} ping', delete_after=10)

    async def _list_prefixes(self, message):
        prefixes = (await self.bot.get_prefix(message))[2:]
        formatted = ' '.join(prefixes)
        if message.guild is not None:
            here = f'for {message.guild.name}'
        else:
            here = 'here'

        if len(prefixes) > 1:
            await message.channel.send(f'My prefixes {here} are: `{formatted}`')
        else:
            await message.channel.send(f'My prefix {here} is: {formatted}')

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=24)
    async def save_prefixes_to_json(self):
        self.save_prefixes()

    def cog_unload(self):
        self.save_prefixes_to_json.cancel()
        self.save_prefixes()


def setup(bot):
    bot.add_cog(PrefixCog(bot))
