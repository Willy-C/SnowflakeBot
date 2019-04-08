import json

import discord
from discord.ext import commands

from main import prefix_map, get_prefixes
from threading import Lock

mutex = Lock()  # make global so all threads can see same lock


def handle_new_prefixes(modifier, prefix):
    new_prefixes = []
    if ['add', 'rem', 'remove'].__contains__(modifier):  # modifier actually contains a modifier
        new_prefixes = prefix
    else:  # else modifier was also targeted new prefix, so add them both
        new_prefixes.append(modifier)  # append single string
        new_prefixes.extend(prefix)  # append list
    return new_prefixes


class SetPrefixCog(commands.Cog, name='General'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setprefix', aliases=['sp'])
    async def set_prefix(self, ctx: commands.Context, modifier, *prefix):
        """Sets the prefix for the current guild"""
        """Require: mutual exclusion to make sure map does not get modified unintentially, and that writes happen in correct sequence"""
        mutex.acquire()

        id = str(ctx.guild.id)
        pfx_map = self.bot.prefix_map

        new_prefixes = handle_new_prefixes(modifier, prefix)
        old_prefixes_pretty = "  ".join(get_prefixes(self.bot, ctx.guild.id))  # need to save this as a variable, since will be overwritten

        if modifier == 'add':
            if id in pfx_map:
                pfx_map[id].extend(new_prefixes)
            else:
                pfx_map[id] = ['?', '%']
                pfx_map[id].extend(new_prefixes)
        elif modifier == 'rem' or modifier == 'remove':  # send fail if map entry does not contain all of @new_prefixes
            curr_prefixes = ['?', '%'] if id not in pfx_map else pfx_map[id]
            if not all(prefix in curr_prefixes for prefix in new_prefixes):
                return await ctx.send(f'Not all of \"{" ".join(new_prefixes)}\" is in the current list of prefixes, \"{" ".join(curr_prefixes)}\"')
            else:  # curr prefixes has the target prefixes (@new_prefixes)
                pfx_map[id] = [pre for pre in pfx_map[id] if pre not in new_prefixes]
        elif modifier == 'list' or modifier == 'curr' or modifier == 'current':
            return await ctx.send(f'The prefixes for {ctx.guild.name} are ```\n{old_prefixes_pretty}```')
        else:  # was not add, rem, nor remove. force set to @new_prefixes
            pfx_map[id] = new_prefixes

        #  confirm embed
        confirm_msg = discord.Embed(
            color=discord.colour.Color.dark_gold(),
            description=f'Changing command prefix from '
            f'\"{old_prefixes_pretty}\" to '  # old prefixes
            f'\"{"  ".join(get_prefixes(self.bot, ctx.guild.id))}\"'  # new target prefixes
        )

        await ctx.send(embed=confirm_msg)

        with open("data/prefix_map.json", "w+") as prefix_map_json:
            pretty = json.dumps(pfx_map, indent=4, sort_keys=True)
            prefix_map_json.write(pretty)

        mutex.release()  # release lock at end of function



    @set_prefix.error
    async def set_prefix_handler(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("You are not elevated enough to run this command")
        else:
            await ctx.send(
                "Some unknown error occurred. Please try again, if this error persists, please contact someone smarter than @Willy#7692")


def setup(bot):
    bot.add_cog(SetPrefixCog(bot))
