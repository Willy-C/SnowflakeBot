from __future__ import annotations

import io
import traceback
import contextlib
from typing import Optional

import discord
from discord.ext import commands


class ConfirmView(discord.ui.View):
    def __init__(self, *, context: Context, timeout: float, author: discord.User, delete_after: bool):
        super().__init__(timeout=timeout)
        self.ctx: Context = context
        self.author: discord.User = author
        self.delete_after: bool = delete_after
        self.message: Optional[discord.Message] = None
        self.choice: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if await self.ctx.bot.is_owner(interaction.user):
            return True
        if interaction.user == self.author:
            return True
        else:
            await interaction.response.send_message('You cannot use this', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        if self.message and self.delete_after:
            await self.message.delete()

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.choice = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.choice = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()


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
        if message := self.replied_message:
            return message.to_reference()
        return None

    async def confirm_prompt(self, msg, *, timeout=60, delete_after=True):
        """
        Asks author for confirmation
        Returns True if confirmed, False if cancelled, None if timed out
        """
        view = ConfirmView(context=self, timeout=timeout, author=self.author, delete_after=delete_after)
        view.message = await self.reply(msg, view=view)
        await view.wait()
        return view.choice

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
        except Exception:
            traceback.print_exc()

    async def safe_send(self, content, filename='message_too_long.txt', **kwargs):
        """
        Sends to ctx.channel if possible, upload to hastebin or send text file if too long
        """
        if len(content) <= 2000:
            return await self.send(content, **kwargs)
        else:
            fp = io.BytesIO(content.encode())
            kwargs.pop('file', None)
            return await self.send(file=discord.File(fp, filename=filename), **kwargs)

