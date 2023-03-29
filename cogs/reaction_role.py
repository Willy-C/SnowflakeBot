import asyncio
import typing
import contextlib

import discord
from discord.ext import commands

from utils.converters import MessageConverter


def sort_emoji_role(arg1, arg2):
    if isinstance(arg1, discord.Role):
        if isinstance(arg2, discord.Role):
            raise commands.BadArgument('You seemed to have passed 2 roles when 1 role and 1 emoji is expected')
        else:
            return arg2, arg1
    else:
        if not isinstance(arg2, discord.Role):
            raise commands.BadArgument('I am unable to find that role')
        else:
            return arg1, arg2

class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.messages = {}
        self.interacting = {}
        bot.loop.create_task(self.get_message_ids())

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        if ctx.command.qualified_name in ('reactrole info', 'reactrole list'):
            return True
        return ctx.author.guild_permissions.manage_roles or await ctx.bot.is_owner(ctx.author)

    async def get_message_ids(self):
        query = '''SELECT * FROM reaction_roles;'''
        records = await self.bot.pool.fetch(query)
        self.messages = {r['message']: [r['type'], r['data'], r['channel'], r['guild']] for r in records}

    async def get_rr_info(self, message):
        data = self.messages[message.id][1]
        reaction_roles = []
        for e, r in data.items():
            role = message.guild.get_role(r)
            if not role:
                continue
            reaction_roles.append(f'{e} - {role.mention}')
        return reaction_roles

    async def update_message_content(self, message):
        if message.author != self.bot.user:
            return
        reaction_roles = await self.get_rr_info(message)
        await message.edit(content='\n'.join(reaction_roles), allowed_mentions=discord.AllowedMentions.none())

    async def update_message_data(self, message):
        query = '''SELECT * FROM reaction_roles WHERE message = $1;'''
        record = await self.bot.pool.fetchrow(query, message.id)
        self.messages[record['message']] = [record['type'], record['data'], record['channel'], record['guild']]

    async def remove_interacting(self, ctx):
        def check(c):
            return c.cog == self, c.author.id == ctx.author.id
        try:
            await self.bot.wait_for('command', check=check, timeout=900)
        except asyncio.TimeoutError:
            self.interacting.pop(ctx.author.id, None)

    async def cog_after_invoke(self, ctx):
        self.bot.loop.create_task(self.remove_interacting(ctx))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.messages:
            return
        info = self.messages[payload.message_id]
        if str(payload.emoji) not in info[1]:
            return
        if not payload.member:
            guild = self.bot.get_guild(info[3])
            member = guild.get_member(payload.user_id)
        else:
            member = payload.member
        if info[0] == 'group':
            current_roles = [(e, rid) for e, rid in info[1].items() if e != 'max' and e != str(payload.emoji) and rid in {r.id for r in member.roles}]
            to_remove = len(current_roles) - info[1]['max'] + 1
            to_remove = max(0, to_remove)
            _remove_roles = []
            for t in current_roles[:to_remove]:
                e, r = t
                _remove_roles.append(discord.Object(r))
                e = e.strip('<>')
                await self.bot.http.remove_reaction(payload.channel_id, payload.message_id, e, payload.user_id)
            await member.remove_roles(*_remove_roles)
        await member.add_roles(discord.Object(info[1][str(payload.emoji)]))

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.messages:
            return
        info = self.messages[payload.message_id]
        if str(payload.emoji) not in info[1]:
            return
        if info[0] == 'verify':
            return
        guild = self.bot.get_guild(info[3])
        member = guild.get_member(payload.user_id)
        await member.remove_roles(discord.Object(info[1][str(payload.emoji)]))

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.message_id in self.messages:
            query = '''DELETE FROM reaction_roles 
                       WHERE message = $1;'''
            await self.bot.pool.execute(query, payload.message_id)
            del self.messages[payload.message_id]

    async def create_reaction_role_with_type(self, ctx, message, role, emoji, type):
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            if not isinstance(emoji, discord.PartialEmoji):
                return await ctx.send('Sorry, I am unable to add that emoji to the message, are you sure it is a valid emoji?', delete_after=15)
            else:
                m = await ctx.send(f'I cannot add that reaction since its from another server, please do so for me by adding {emoji.name} to the message for me within the next **90 seconds**. You can remove the reaction after I added one.\n'
                                   f'The message: {message.jump_url}')

                def check(payload):
                    return payload.emoji == emoji and payload.message_id == message.id
                try:
                    await self.bot.wait_for('raw_reaction_add', check=check, timeout=90)
                except discord.HTTPException:
                    return await ctx.send('Sorry, I am unable to add that emoji to the message.', delete_after=15)
                except asyncio.TimeoutError:
                    return await ctx.send('Waited too long for the reaction, exiting...', delete_after=15)
                else:
                    try:
                        await message.add_reaction(emoji)
                    except:
                        return await ctx.send('I am unable to add that reaction', delete_after=15)
                    with contextlib.suppress(discord.HTTPException):
                        await message.remove_reaction(emoji, ctx.author)
                finally:
                    await m.delete()

        if role >= ctx.me.top_role:
            return await ctx.send('That role is above my role so I won\'t be able to add/remove it, please move my role up and try again!')

        query = '''INSERT INTO reaction_roles(message, channel, guild, type, data)
                   VALUES($1, $2, $3, $4, $5::jsonb)
                   ON CONFLICT(message) DO UPDATE
                   SET data = reaction_roles.data::jsonb || $5::jsonb;'''
        await self.bot.pool.execute(query, message.id, message.channel.id, message.guild.id, type, {str(emoji): role.id})


        description = f'Added {role.mention} with emoji {emoji if not isinstance(emoji, discord.PartialEmoji) else emoji.name} for [message]({message.jump_url})'
        if type == 'verify':
            description += f'\nRemoving reactions from this message will **not** remove the role.'

        emoji = discord.Embed(title='Reaction Role - Add emoji',
                              color=0x55dd55,
                              description=description)
        await ctx.send(embed=emoji, allowed_mentions=discord.AllowedMentions.none())
        await ctx.message.add_reaction('<:greenTick:602811779835494410>')
        await self.update_message_data(message)
        await self.update_message_content(message)

    @commands.group(name='reactrole', aliases=['rr'], invoke_without_command=True, case_insensitive=True)
    async def reactrole(self, ctx):
        await ctx.send_help(ctx.command)

    @reactrole.command(aliases=['msg'])
    async def message(self, ctx, message: MessageConverter=None):
        """Set the message you are editing or create a new message
        ```I will search in the following order:
        1. By {channel ID}-{message ID}
          This can be retrieved by shift-clicking on “Copy ID”
        2. Lookup by message ID
          The message must be in the current channel
        3. Lookup by message URL
          Note: You need Developer Mode enabled to retrieve message IDs```
        """
        if not message:
            if not await ctx.confirm_prompt('You have not specified a message, do you want me to create one for you?\n'
                                            'Note: Emojis from servers I am not in will not work for this.'):
                await ctx.send(f'If you are having trouble specifying an existing message, see `{ctx.prefix}help rr msg`')
                return
            message = await ctx.send('Setting up reaction roles...')
        if message.id not in self.messages:
            query = '''INSERT INTO reaction_roles(message, channel, guild, type, data)
                       VALUES($1, $2, $3, $4, $5::jsonb);'''
            await self.bot.pool.execute(query, message.id, message.channel.id, message.guild.id, 'normal', {})
            await self.update_message_data(message)
        self.interacting[ctx.author.id] = message
        e = discord.Embed(color=0x55dd55,
                          description=f'Ok, you are now editing [message]({message.jump_url}) {message.id}')
        await ctx.send(embed=e, allowed_mentions=discord.AllowedMentions.none(), delete_after=10)

    @reactrole.command(aliases=['new'])
    @commands.bot_has_permissions(add_reactions=True, manage_messages=True)
    async def add(self, ctx, message: typing.Optional[MessageConverter], role: typing.Union[discord.Role, discord.Emoji, discord.PartialEmoji, str], emoji: typing.Union[discord.Role, discord.Emoji, discord.PartialEmoji, str]):
        """Add a emoji and reaction to a message.
        If you recently used a reaction role command, it will automatically be for the same message, otherwise you must specify a message
        Role can be inputted with its ID, Mention or Name

        Example:
        `%rr add [message id] :thinking: @Member` (See `%help rr msg` on how to enter a message id)
        `%rr add :gun: @Admin` Note this only works if you recently used another reaction role command"""

        if message is None:
            if ctx.author.id in self.interacting:
                message = self.interacting[ctx.author.id]
            else:
                return await ctx.send(f'Please specify a message ID or use `{ctx.prefix}rr msg [message]` to set one')
        else:
            self.interacting[ctx.author.id] = message
        e, r = sort_emoji_role(role, emoji)

        if message.id in self.messages and e in self.messages[message.id][1]:
            return await ctx.send(f'This emoji is already used for a role on this message!')

        await self.create_reaction_role_with_type(ctx, message, r, e, 'normal')

    @reactrole.command()
    @commands.bot_has_permissions(add_reactions=True, manage_messages=True)
    async def remove(self, ctx, message: typing.Optional[MessageConverter], emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str]):
        """Remove an emoji from a message.
        If you recently used a reaction role command, it will automatically be for the same message, otherwise you must specify a message
        Role can be inputted with its ID, Mention or Name

        Example:
        `%rr remove [message id] :thinking:` (See `%help rr msg` on how to enter a message id)
        `%rr remove :gun:` Note this only works if you recently used another reaction role command"""
        if message is None:
            if ctx.author.id in self.interacting:
                message = self.interacting[ctx.author.id]
            else:
                return await ctx.send(f'Please specify a message ID or use `{ctx.prefix}rr msg [message]` to set one')
        else:
            self.interacting[ctx.author.id] = message
        if message.id not in self.messages:
            return await ctx.send('That message does not seem to have any reaction roles!')

        if emoji not in self.messages[message.id][1]:
            return await ctx.send('This emoji is not used for reaction roles on this message!')

        try:
            await message.clear_reaction(emoji)
        except discord.HTTPException:
            return await ctx.send('Sorry, I am unable to remove that reaction from the message', delete_after=15)
        get_query = '''SELECT data FROM reaction_roles WHERE message = $1'''
        data = await self.bot.pool.fetchval(get_query, message.id)
        role = data[str(emoji)]
        role = message.guild.get_role(role)
        del data[str(emoji)]
        if not data or ('max' in data and len(data) == 1):
            query = '''DELETE FROM reaction_roles 
                       WHERE message = $1;'''
            await self.bot.pool.execute(query, message.id)
        else:
            query = '''UPDATE reaction_roles
                       SET data = $1::jsonb
                       WHERE message = $2;'''
            await self.bot.pool.execute(query, data, message.id)
        e = discord.Embed(title='Reaction Role - Remove emoji',
                          color=0x55dd55,
                          description=f'Removed {role.mention} with emoji {emoji if not isinstance(emoji, discord.PartialEmoji) else emoji.name} from [message]({message.jump_url})')
        await ctx.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        await ctx.message.add_reaction('<:greenTick:602811779835494410>')
        await self.update_message_data(message)
        await self.update_message_content(message)

    @reactrole.group(aliases=['group'], invoke_without_command=True, case_insensitive=True)
    async def toggle(self, ctx, message: typing.Optional[MessageConverter], toggle: bool=None):
        """Set a reaction role message to only allow 1 role
        Defaults to ON
        Ex.
        `%rr toggle` - restrict the message to allow 1 role (only works if you recently used a rr command)
        `%rr [message id] toggle` - restrict the message to allow 1 role
        `%rr toggle off` - users can have any amount of roles from this message
        """
        if message is None:
            if ctx.author.id in self.interacting:
                message = self.interacting[ctx.author.id]
            else:
                return await ctx.send(f'Please specify a message ID or use `{ctx.prefix}rr msg [message]` to set one')
        else:
            self.interacting[ctx.author.id] = message

        if message.id not in self.messages:
            return await ctx.send('That message does not seem to have any reaction roles!')
        if self.messages[message.id][0] != 'group' and toggle is not False:
            query = '''UPDATE reaction_roles
                       SET type = 'group',
                           data = reaction_roles.data::jsonb || '{"max": 1}'::jsonb
                       WHERE message = $1;'''
            await self.bot.pool.execute(query, message.id)
            self.messages[message.id][0] = 'group'
            e = discord.Embed(title=f'Reaction Role - {ctx.invoked_with.capitalize()} set',
                              color=0x55dd55,
                              description=f'This [message]({message.jump_url}) is now set to {ctx.invoked_with}. Only 1 role from this message will be allowed.')

        elif self.messages[message.id][0] == 'group' and toggle is False:
            query = '''UPDATE reaction_roles
                       set type = 'normal',
                           data = data::jsonb - 'max'
                       WHERE message = $1;'''
            await self.bot.pool.execute(query, message.id)
            self.messages[message.id][0] = 'normal'
            e = discord.Embed(title=f'Reaction Role - {ctx.invoked_with.capitalize()} disabled',
                              color=0x55dd55,
                              description=f'This [message]({message.jump_url}) is no longer set to {ctx.invoked_with}. Users can have any number of roles from this message.')
        else:
            e = discord.Embed(title='Reaction Role - Already set',
                              color=0xFAA935,
                              description=f'This [message]({message.jump_url}) was {"already" if toggle is not False else "not"} a {ctx.invoked_with}! Nothing has changed')
            await ctx.send(embed=e)
            return
        await ctx.send(embed=e)
        await ctx.message.add_reaction('<:greenTick:602811779835494410>')
        await self.update_message_data(message)

    @toggle.command()
    async def set(self, ctx, message: typing.Optional[MessageConverter], number: int):
        """Set the max number of reaction roles a user can have for this message
        Example:
        `%rr toggle set 2` will restrict only max of 2 reaction roles from this message
        """
        number = max(1, number)
        if message is None:
            if ctx.author.id in self.interacting:
                message = self.interacting[ctx.author.id]
            else:
                return await ctx.send(f'Please specify a message ID or use `{ctx.prefix}rr msg [message]` to set one')
        else:
            self.interacting[ctx.author.id] = message

        if message.id not in self.messages:
            return await ctx.send('That message does not seem to have any reaction roles!')

        if self.messages[message.id][0] != 'group':
            await self.toggle(ctx, message, True)
        query = '''UPDATE reaction_roles
                   SET data = reaction_roles.data::jsonb || $1::jsonb
                   WHERE message = $2;'''
        await self.bot.pool.execute(query, {'max': number}, message.id)
        e = discord.Embed(title='Reaction Role',
                          color=0x55dd55,
                          description=f'Users can now have up to {number} roles from [message]({message.jump_url})')
        await ctx.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        await self.update_message_data(message)

    @reactrole.command()
    async def info(self, ctx, message: typing.Optional[MessageConverter]):
        """Lists info about a reaction role message"""
        if message is None:
            if ctx.author.id in self.interacting:
                message = self.interacting[ctx.author.id]
            else:
                return await ctx.send(f'Please specify a message ID or use `{ctx.prefix}rr msg [message]` to set one')
        else:
            self.interacting[ctx.author.id] = message

        reaction_roles = await self.get_rr_info(message)
        fmt = '\n'.join(reaction_roles)
        e = discord.Embed(title='Reaction Roles Info',
                          color=0x55dd55,
                          description=f'[Message]({message.jump_url})\n\n{fmt}')
        e.add_field(name='Type', value='Regular' if self.messages[message.id][0] == 'normal' else 'Toggle/Group')
        await ctx.send(embed=e)

    @reactrole.command()
    async def list(self, ctx):
        """List all reaction role message on this server"""
        query = '''SELECT message, type, data, channel FROM reaction_roles WHERE guild = $1;'''
        records = await self.bot.pool.fetch(query, ctx.guild.id)
        messages = []
        for r in records:
            count = len(r['data'])
            if r['type'] == 'group':
                count -= 1
            url = f'https://discord.com/channels/{ctx.guild.id}/{r["channel"]}/{r["message"]}'
            messages.append(f'[{r["message"]}]({url}) - {count} - {r["type"].capitalize()}')

        e = discord.Embed(title='Reaction Roles List',
                          color=0x55dd55,
                          description='\n'.join(messages) if messages else 'No reaction roles on this server')
        await ctx.send(embed=e)

    @reactrole.command(name='reset')
    async def clear(self, ctx, message: MessageConverter):
        """Remove all reaction roles from a message
        A message must be given"""
        if not await ctx.confirm_prompt('Are you sure you want to completely remove reaction roles from this message?\n'
                                        'This will make it be a regular message. **This cannot be undone.**'):
            return
        query = '''DELETE FROM reaction_roles WHERE message = $1;'''
        status = await self.bot.pool.execute(query, message.id)
        if status == 'DELETE 0':
            return await ctx.send('Unable to remove reaction roles with that ID')
        self.messages.pop(message.id, None)
        await ctx.message.add_reaction('<:greenTick:602811779835494410>')
        try:
            await message.clear_reactions()
        except discord.HTTPException:
            pass

    @reactrole.command(name='verify', aliases=['once'])
    async def add_only(self, ctx, message: typing.Optional[MessageConverter], role: typing.Union[discord.Role, discord.Emoji, discord.PartialEmoji, str], emoji: typing.Union[discord.Role, discord.Emoji, discord.PartialEmoji, str]):
        """Set a reaction role message to a verification message.
        This essentially means removing the reaction will not remove the role, making it a 1 time interaction.

        If you recently used a reaction role command, it will automatically be for the same message, otherwise you must specify a message
        Role can be inputted with its ID, Mention or Name

        Example:
        `%rr verify [message id] :thinking: @Member` (See `%help rr msg` on how to enter a message id)
        `%rr verify :gun: @Admin` Note this only works if you recently used another reaction role command
        """
        if message is None:
            if ctx.author.id in self.interacting:
                message = self.interacting[ctx.author.id]
            else:
                return await ctx.send(f'Please specify a message ID or use `{ctx.prefix}rr msg [message]` to set one')
        else:
            self.interacting[ctx.author.id] = message
        e, r = sort_emoji_role(role, emoji)

        if message.id in self.messages and e in self.messages[message.id][1]:
            return await ctx.send(f'This emoji is already used for a role on this message!')

        await self.create_reaction_role_with_type(ctx, message, r, e, 'verify')
        query = '''UPDATE reaction_roles
                   SET type = 'verify'
                   WHERE message = $1;'''
        await self.bot.pool.execute(query, message.id)
        await self.update_message_data(message)


    @reactrole.command(name='unverify')
    async def unverify(self, ctx, message: MessageConverter):
        """Undo setting a message as a verification
        A message must be given"""
        if not await ctx.confirm_prompt('Are you sure you want to undo setting message to be verification\n'
                                        'This will make it be a regular reaction role.\n'):
            return

        if message.id in self.messages and self.messages[message.id][0] != 'verify':
            return await ctx.send(f'This message is not a verification message!')

        query = '''UPDATE reaction_roles
                   SET type = 'normal'
                   WHERE message = $1;'''
        await self.bot.pool.execute(query, message.id)
        await self.update_message_data(message)
        await ctx.message.add_reaction('<:greenTick:602811779835494410>')



async def setup(bot):
    await bot.add_cog(ReactionRole(bot))
