from __future__ import annotations
from typing import Optional, Union, List, Any

import wavelink
import discord
from discord.ext import commands
from utils.context import Context
from utils.global_utils import copy_context


class MusicPlayerView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = None, context: Context):
        super().__init__(timeout=timeout)
        self.ctx: Context = context
        self.bot: commands.Bot = context.bot
        self.player: Optional[wavelink.Player] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if (interaction.user.voice and interaction.user.voice.channel == self.player.channel) or await self.ctx.bot.is_owner(interaction.user):
            return True
        else:
            await interaction.response.send_message('You must be in the voice channel to use this', ephemeral=True)
            return False

    @discord.ui.button(emoji='\U000023f8\U0000fe0f')
    async def pause(self, button: discord.ui.Button, interaction: discord.Interaction):
        if button.emoji == discord.PartialEmoji(name='\U000023f8\U0000fe0f'):
            button.emoji = '\U000025b6\U0000fe0f'
            button.style = discord.ButtonStyle.green
            cmd = self.bot.get_command('pause')
        else:
            button.emoji = '\U000023f8\U0000fe0f'
            button.style = discord.ButtonStyle.grey
            cmd = self.bot.get_command('resume')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='\U000023f9\U0000fe0f', style=discord.ButtonStyle.red)
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        cmd = self.bot.get_command('stop')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)

    @discord.ui.button(emoji='\U000023ed\U0000fe0f')
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        cmd = self.bot.get_command('skip')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)

    @discord.ui.button(emoji='\U0001f500')
    async def shuffle(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        cmd = self.bot.get_command('shuffle')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)

    @discord.ui.button(emoji='\U0001f501')
    async def loop(self, button: discord.ui.Button, interaction: discord.Interaction):
        cmd = self.bot.get_command('loop')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)
        button.style = discord.ButtonStyle.green if self.player.looping else discord.ButtonStyle.grey
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Queue')
    async def queue(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        cmd = self.bot.get_command('queue')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)


class ChoiceButton(discord.ui.Button):
    def __init__(self, *, label: Union[str, int]):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: AskChoice = self.view
        if view is None:
            return
        view.set_choice(self.label)
        if view.delete_after:
            await interaction.delete_original_message()
        view.stop()


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji='<:redTick:602811779474522113>', style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: AskChoice = self.view
        if view is None:
            return
        if view.delete_after and view.message:
            await interaction.delete_original_message()
        view.cancelled = True
        view.stop()


class AskChoice(discord.ui.View):
    def __init__(self, choices: List[Any], *, context: Context, timeout: float, author: Optional[discord.User] = None, delete_after: bool=True):
        super().__init__(timeout=timeout)
        self.choices: List[Any] = choices
        self.ctx: Context = context
        self.author: discord.User = author or context.author
        self.delete_after: bool = delete_after
        self.message: Optional[discord.Message] = None
        self.chosen_item = None
        self.chosen_index = None
        self.cancelled = False
        self._add_buttons()

    def _add_buttons(self):
        for index, track in enumerate(self.choices):
            self.add_item(ChoiceButton(label=index+1))
        self.add_item(CancelButton())

    def set_choice(self, label: str):
        self.chosen_index = int(label)-1
        self.chosen_item = self.choices[self.chosen_index]
        return self.chosen_item

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



