from __future__ import annotations

import io
import secrets
from typing import Optional, TYPE_CHECKING, Callable

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from main import SnowflakeBot


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
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()
        self.stop()


class DisambiguatorView(discord.ui.View):
    message: discord.Message

    def __init__(self, ctx: Context, data: list, entry: Callable):
        super().__init__()
        self.ctx: Context = ctx
        self.data: list = data

        options = []
        for i, x in enumerate(data):
            opt = entry(x)
            if not isinstance(opt, discord.SelectOption):
                opt = discord.SelectOption(label=str(opt))
            opt.value = str(i)
            options.append(opt)

        select = discord.ui.Select(options=options)

        select.callback = self.on_select_submit
        self.select = select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.ctx.author.id, self.ctx.bot.owner_id):
            await interaction.response.send_message('This select menu is not meant for you, sorry.', ephemeral=True)
            return False
        return True

    async def on_select_submit(self, interaction: discord.Interaction):
        index = int(self.select.values[0])
        self.selected = self.data[index]
        await interaction.response.defer()
        if not self.message.flags.ephemeral:
            await self.message.delete()

        self.stop()

    async def on_timeout(self) -> None:
        try:
            self.select.disabled = True
            await self.message.edit(view=self)
        except (discord.HTTPException, AttributeError):
            pass


class Context(commands.Context):
    bot: SnowflakeBot

    @property
    def session(self) -> ClientSession:
        return self.bot.session

    @discord.utils.cached_property
    def replied_message(self) -> discord.Message | None:
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved

    @discord.utils.cached_property
    def replied_reference(self) -> discord.MessageReference | None:
        if message := self.replied_message:
            return message.to_reference()

    @property
    def voice_channel(self) -> discord.VoiceChannel | None:
        """
        Returns VoiceChannel of ctx.author if available
        """
        if isinstance(self.author, discord.Member):
            if self.author.voice:
                return self.author.voice.channel

    @property
    def is_silent(self) -> bool:
        """
        Returns True if the command was invoked with a silent message
        """
        return self.message.flags.silent

    async def confirm_prompt(self, msg, *, timeout=60, delete_after=True, **kwargs) -> bool | None:
        """
        Asks author for confirmation
        Returns True if confirmed, False if cancelled, None if timed out
        """
        view = ConfirmView(context=self, timeout=timeout, author=self.author, delete_after=delete_after)
        view.message = await self.send(msg, view=view, **kwargs)
        await view.wait()
        return view.choice

    async def tick(self, value=True, reaction=True) -> str | None:
        """
        React to the message with green, red or grey tick depending on the value
        If reaction is False, return the emoji instead of reacting
        """
        emojis = {
            True: '<:greenTick:602811779835494410>',
            False: '<:redTick:602811779474522113>',
            None: '<:greyTick:602811779810328596>'
        }

        emoji = emojis.get(value, '<:redTick:602811779474522113>')
        if reaction:
            try:
                await self.message.add_reaction(emoji)
            except discord.HTTPException:
                pass
        else:
            return emoji

    async def silent_delete(self, message: Optional[discord.Message] = None, *, delay: Optional[float] = None) -> None:
        """
        Delete a message, but ignores discord.HTTPException
        """
        message = message or self.message
        try:
            await message.delete(delay=delay)
        except discord.HTTPException:
            pass

    async def send(
            self,
            content: Optional[str] = None,
            *,
            mystbin: bool = False,
            filetype: str = 'txt',
            force_upload: bool = False,
            **kwargs,
    ) -> discord.Message:
        """Send but if the content is too long, it will be uploaded to mystbin or a file."""
        content = str(content) if content is not None else None

        if content and (len(content) >= 2000 or force_upload):
            if mystbin:
                password = secrets.token_urlsafe(8)
                paste = await self.bot.mb_client.create_paste(
                    filename=f'output.{filetype}',
                    content=content,
                    password=password,
                )

                return await super().send(f'Output too long, uploaded to {paste.url} instead.\n'
                                          f'Password: `{password}`', **kwargs)
            else:
                fp = io.BytesIO(content.encode())
                files = [discord.File(fp, filename=f'output.{filetype}')]

                files.extend(kwargs.pop('file', []))
                files.extend(kwargs.pop('files', []))

                return await super().send(files=files, **kwargs)

        return await super().send(content, **kwargs)

    async def reply(self, content: Optional[str] = None, **kwargs) -> discord.Message:
        """Reply but send regular message if message was deleted or discord couldn't fetch it"""
        if self.interaction is None:
            return await self.send(content, reference=self.message.to_reference(fail_if_not_exists=False), **kwargs)
        else:
            return await self.send(content, **kwargs)

    async def disambiguate(self, matches: list, entry: Callable, *, ephemeral: bool = False):
        if len(matches) == 0:
            raise ValueError('No results found.')

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 25:
            raise ValueError('Too many results... sorry.')

        view = DisambiguatorView(self, matches, entry)
        view.message = await self.send(
            'There are too many matches... Which one did you mean?', view=view, ephemeral=ephemeral
        )
        await view.wait()
        return view.selected
