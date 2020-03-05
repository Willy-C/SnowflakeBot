import discord
from discord.ext import commands

import re


class PrefixCog(commands.Cog, name='Prefix'):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.set_mention_regex())

    async def set_mention_regex(self):
        await self.bot.wait_until_ready()
        self.mention = re.compile(r'<@!?' + str(self.bot.user.id) + r'>')

    @commands.group(invoke_without_command=True, case_insensitive=True)
    async def prefix(self, ctx):
        await ctx.send_help(ctx.command)

    @prefix.command()
    @commands.guild_only()
    async def set(self, ctx, *new_prefixes):
        """Set my prefix(es) for this guild.
        Separate multiple prefixes with spaces."""
        new = list(new_prefixes)
        self.bot.prefixes[ctx.guild.id] = new
        await ctx.send(f'This guild\'s prefix is set to {", ".join(new_prefixes)}\n')
        await ctx.send(f'Note: Mentioning the bot will always be a valid prefix. Ex: {self.bot.user.mention} ping', delete_after=10)
        query = '''DELETE FROM prefixes WHERE guild = $1;'''
        await self.bot.pool.execute(query, ctx.guild.id)
        add_new = '''INSERT INTO prefixes(guild, prefix)
                     VALUES($1, $2);'''
        prefixes_with_guild = [(ctx.guild.id, n) for n in new]
        await self.bot.pool.executemany(add_new, prefixes_with_guild)

    @prefix.command(aliases=['clear'])
    @commands.guild_only()
    async def reset(self, ctx):
        """Reset my prefix for this guild to the default"""
        try:
            del self.bot.prefixes[ctx.guild.id]
            await ctx.send('Prefix for this guild has been reset. Default: %')
            await ctx.send(f'Note: Mentioning the bot will always be a valid prefix. Ex: {self.bot.user.mention} ping', delete_after=10)
            query = '''DELETE FROM prefixes WHERE guild = $1;'''
            await self.bot.pool.execute(query, ctx.guild.id)
        except KeyError:
            await ctx.send('This guild is already using the default prefix: %')

    @prefix.command()
    @commands.guild_only()
    async def add(self, ctx, *new_prefixes):
        """Add new prefix(es) for this guild.
        Separate multiple prefixes with spaces."""
        # self.bot.prefixes.setdefault(ctx.guild.id, ['%']).extend(new_prefixes)
        added = []
        if ctx.guild.id not in self.bot.prefixes:
            self.bot.prefixes[ctx.guild.id] = ['%']
        current = self.bot.prefixes[ctx.guild.id]
        for prefix in new_prefixes:
            if prefix not in current:
                current.append(prefix)
                added.append(prefix)
        if added:
            await ctx.send(f'Added {", ".join(added)} to this guild\'s prefixes')
            added.append('%')
            query = '''INSERT INTO prefixes(guild, prefix)
                       VALUES ($1, $2);'''
            prefixes_with_guild = [(ctx.guild.id, p) for p in added]
            await self.bot.pool.executemany(query, prefixes_with_guild)
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
            query = '''DELETE FROM prefixes 
                       WHERE guild = $1
                       AND prefix = $2;'''
            await self.bot.pool.execute(query, ctx.guild.id, prefix_to_remove)
            await ctx.send(f'Removed prefix: {prefix_to_remove} from this server')
        else:
            return await ctx.send('This is not an existing prefix!')

    @prefix.command()
    async def list(self, ctx):
        """Lists my prefixes here"""
        await self._list_prefixes(ctx.message)
        await ctx.send(f'\u200b\nYou can always use my mention as a prefix!\n'
                       f'For example: {self.bot.user.mention} ping\n\n'
                       f'Or just mention me and I will tell you my prefix', delete_after=10)

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


def setup(bot):
    bot.add_cog(PrefixCog(bot))
