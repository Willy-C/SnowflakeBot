import discord
from discord.ext import commands

from collections import Counter


# Checks


def can_manage_messages():
    async def predicate(ctx):
        is_owner = await ctx.bot.is_owner(ctx.author)
        if is_owner:
            return True
        if ctx.channel.permissions_for(ctx.author).manage_messages:
            return True
        raise commands.MissingPermissions(['Manage Messages'])
    return commands.check(predicate)


def can_kick():
    async def predicate(ctx):
        is_owner = await ctx.bot.is_owner(ctx.author)
        if is_owner:
            return True
        if ctx.channel.permissions_for(ctx.author).kick_members:
            return True
        raise commands.MissingPermissions(['Kick Members'])
    return commands.check(predicate)


def can_ban():
    async def predicate(ctx):
        is_owner = await ctx.bot.is_owner(ctx.author)
        if is_owner:
            return True
        if ctx.channel.permissions_for(ctx.author).ban_members:
            return True
        raise commands.MissingPermissions(['Ban Members'])
    return commands.check(predicate)


# The actual cog


class ModCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
# TODO: make custom checks for these

    @commands.command(name='delmsg')
    @commands.bot_has_permissions(manage_messages=True)
    @can_manage_messages()
    async def del_msg(self, ctx, message: discord.Message):
        """Deletes a specific message"""
        try:
            await message.delete()
        except discord.HTTPException:
            await ctx.send('Discord is being dumb, try again later')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

    @del_msg.error
    async def del_msg_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            return await ctx.send('```I am unable to find the specified message.\n'
                                  'I will search in the following order:\n\n'
                                  '1. By {channel ID}-{message ID}\n'
                                  'This can be retrieved by shift-clicking on “Copy ID”\n\n'
                                  '2. Lookup by message ID\n'
                                  'The message must be in the current channel\n\n'
                                  '3. Lookup by message URL\n\n'
                                  'Note: You need Developer Mode enabled to retrieve message IDs```')

    async def _sad_clean(self, ctx, limit):
        counter = 0
        async for msg in ctx.history(limit=limit, before=ctx.message):
            if msg.author == ctx.me:
                await msg.delete()
                counter += 1
        return {str(self.bot.user): counter}

    async def _good_clean(self, ctx, limit):
        def check(m):
            return m.author == ctx.me or m.content.startswith(ctx.prefix)
        deleted = await ctx.channel.purge(limit=limit, check=check, before=ctx.message)
        return Counter(str(msg.author) for msg in deleted)

    @commands.command()
    @can_manage_messages()
    async def clean(self, ctx, limit: int = 10):
        """Clean's up the bot's messages"""
        if ctx.me.permissions_in(ctx.channel).manage_messages:
            spam = await self._good_clean(ctx, limit)
        else:
            spam = await self._sad_clean(ctx, limit)

        deleted = sum(spam.values())

        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed']
        if deleted:
            messages.append('')
            spammers = sorted(spam.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'- **{author}**: {count}' for author, count in spammers)

        await ctx.send('\n'.join(messages), delete_after=60)
        await ctx.message.add_reaction('\U00002705')  # React with checkmark

    @commands.command()
    @commands.bot_has_permissions(kick_members=True)
    @can_kick()
    @commands.guild_only()
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kicks member from server"""
        if reason is None:
            reason = f'Done by: {ctx.author} ({ctx.author.id})'
        else:
            reason = f'{ctx.author} ({ctx.author.id}): {reason}'

        await member.kick(reason=reason)
        await ctx.send('\U0001f44c')  # OK

    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    @can_ban()
    @commands.guild_only()
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Bans someone from the server"""
        if reason is None:
            reason = f'Done by: {ctx.author} ({ctx.author.id})'
        else:
            reason = f'{ctx.author} ({ctx.author.id}): {reason}'

        await ctx.guild.ban(member, reason=reason, delete_message_days=0)
        await ctx.send('\U0001f44c')  # OK

    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    @can_ban()
    @commands.guild_only()
    async def unban(self, ctx, id: int, *, reason=None):
        """Unbans someone from the server. Must provide user's ID"""
        if reason is None:
            reason = f'Done by: {ctx.author} ({ctx.author.id})'
        else:
            reason = f'{ctx.author} ({ctx.author.id}): {reason}'

        try:
            await ctx.guild.unban(discord.Object(id=id), reason=reason)
        except discord.HTTPException:
            await ctx.send('Unban failed')
        else:
            await ctx.send('\U0001f44c')  # OK


    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    @can_kick()
    @commands.guild_only()
    async def softban(self, ctx, member: discord.Member, *, reason=None):
        """Soft bans a member from the server
        Essentially kicks the member while deleting all messages from the last week"""
        if reason is None:
            reason = f'Done by: {ctx.author} ({ctx.author.id})'
        else:
            reason = f'{ctx.author} ({ctx.author.id}): {reason}'

        await ctx.guild.ban(member, reason=reason, delete_message_days=7)
        await ctx.guild.unban(member, reason=reason)
        await ctx.send('\U0001f44c')  # OK


def setup(bot):
    bot.add_cog(ModCog(bot))
