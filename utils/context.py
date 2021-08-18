import discord
from discord.ext import commands

import io
import traceback
import contextlib
from asyncio import TimeoutError


class Context(commands.Context):

    @property
    def session(self):
        return self.bot.session

    @discord.utils.cached_property
    def replied_message(self):
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        return None

    @discord.utils.cached_property
    def replied_reference(self):
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved.to_reference()
        return None

    async def confirm_prompt(self, msg, extra=True):
        """
        Asks author for confirmation, returns True if confirmed, False if user typed abort or timed out
        """
        def confirm(m):
            if self.author.id != m.author.id or self.channel.id != m.channel.id:
                return False
            return m.content.lower() in ('**confirm**', 'confirm', '**abort**', 'abort')

        if extra:
            msg += '\nPlease type **confirm** within 1 minute to continue or type **abort** if you change your mind.'

        prompt = await self.reply(msg)

        try:
            reply = await self.bot.wait_for('message', check=confirm, timeout=60)
        except TimeoutError:
            await self.send('1 minute has passed. Aborting...', delete_after=5)
            return False
        else:
            choice = reply.content
            await reply.delete()
            if choice.lower() in ('**confirm**', 'confirm'):
                return True
            else:
                await self.send('Aborting...', delete_after=5)
                return False
        finally:
            with contextlib.suppress(discord.HTTPException):
                await prompt.delete()

    async def confirm_reaction(self, msg, extra=True):
        """
        Asks author for confirmation via reactions, returns True if confirmed, False if user clicked X or timed out
        """
        emojis = ['<:greenTick:602811779835494410>', '<:redTick:602811779474522113>']

        def confirm(r, u):
            return self.author.id == u.id and prompt == r.message and str(r.emoji) in emojis

        if extra:
            msg += '\nPlease react with <:greenTick:602811779835494410> within 1 minute to continue or <:redTick:602811779474522113> if you change your mind.'

        prompt = await self.reply(msg)

        for e in emojis:
            await prompt.add_reaction(e)
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=confirm, timeout=60)
        except TimeoutError:
            await self.send('1 minute has passed. Aborting...', delete_after=5)
            return False
        else:
            if str(reaction.emoji) == '<:greenTick:602811779835494410>':
                return True
            else:
                await self.send('Aborting...', delete_after=5)
                return False
        finally:
            with contextlib.suppress(discord.HTTPException):
                await prompt.delete()

    async def tick(self, value=True, reaction=True):
        emojis = {True:  '<:greenTick:602811779835494410>',
                  False: '<:redTick:602811779474522113>',
                  None:  '<:greyTick:602811779810328596>'}
        emoji = emojis.get(value, '<:redTick:602811779474522113>')
        if reaction:
            with contextlib.suppress(discord.HTTPException):
                await self.message.add_reaction(emoji)
        else:
            return emoji

    async def silent_delete(self, message=None):
        message = message or self.message
        with contextlib.suppress(discord.HTTPException):
            await message.delete()

    async def _upload_content(self, content, url='https://mystb.in'):
        async with self.bot.session.post(f'{url}/documents', data=content.encode('utf-8')) as post:
            return f'{url}/{(await post.json())["key"]}'

    async def upload_hastebin(self, content, url='https://mystb.in'):
        """
        Uploads content to hastebin and return the url
        """
        try:
            return await self._upload_content(content, url)
        except:
            try:
                return await self._upload_content(content, 'https://hastebin.com')
            except:
                traceback.print_exc()

    async def safe_send(self, content, file=False, filename='message_too_long.txt', url='https://mystb.in', **kwargs):
        """
        Sends to ctx.channel if possible, upload to hastebin or send text file if too long
        """
        if len(content) <= 2000:
            return await self.send(content, **kwargs)
        elif file:
            fp = io.BytesIO(content.encode())
            kwargs.pop('file', None)
            return await self.send(file=discord.File(fp, filename=filename), **kwargs)
        else:
            paste_url = await self.upload_hastebin(content, url)
            return await self.send(f'Output too long, uploaded here instead: {paste_url}', **kwargs)

