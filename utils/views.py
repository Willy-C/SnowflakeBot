from __future__ import annotations
from typing import Optional, Union, List, Any
from textwrap import dedent

import random
import wavelink
import discord
from discord.ext import commands
from utils.context import Context
from utils.global_utils import copy_context


class ReactRoleButton(discord.ui.Button):
    def __init__(self,
                 *,
                 custom_id: Optional[str] = None,
                 emoji: Union[str, discord.Emoji, discord.PartialEmoji],
                 role_id: int):

        super().__init__(style=discord.ButtonStyle.secondary,
                         custom_id=custom_id,
                         emoji=emoji)
        self.role_id: int = role_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user is None:
            return

        if not isinstance(interaction.user, discord.Member):
            if not interaction.guild:
                return
            if not (member := interaction.guild.get_member(interaction.user.id)):
                return
        else:
            member = interaction.user

        await member.add_roles(discord.Object(self.role_id))


class ReactRoleView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = None, single: bool = False, data: dict):
        super().__init__(timeout=timeout)
        self.single = single
        self.add_buttons(data)

    def add_buttons(self, data: dict):
        pass


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
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cmd = self.bot.get_command('stop')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)

    @discord.ui.button(emoji='\U000023ed\U0000fe0f')
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cmd = self.bot.get_command('skip')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)

    @discord.ui.button(emoji='\U0001f500')
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cmd = self.bot.get_command('shuffle')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)

    @discord.ui.button(emoji='\U0001f501')
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        cmd = self.bot.get_command('loop')
        new_ctx = await copy_context(self.ctx, author=interaction.user)
        await cmd(new_ctx)
        button.style = discord.ButtonStyle.green if self.player.looping else discord.ButtonStyle.grey
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Queue')
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            await interaction.delete_original_response()
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
            await interaction.delete_original_response()
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


# VALORANT Stuff

class CredentialsInput(discord.ui.Modal, title='VALORANT Login'):
    def __init__(self) -> None:
        super().__init__(timeout=180)
        self.interaction = None

    username = discord.ui.TextInput(label='Username')
    password = discord.ui.TextInput(label='Password')

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True,
                                         thinking=True)
        self.interaction = interaction


class LoginView(discord.ui.View):
    def __init__(self, *, ctx):
        super().__init__()
        self.ctx = ctx
        self.author = ctx.author

        self.username = None
        self.password = None
        self.interaction = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if interaction.user == self.author:
            return True
        else:
            await interaction.response.send_message('You cannot use this', ephemeral=True)
            return False

    @discord.ui.button(label='Click', style=discord.ButtonStyle.primary)
    async def send_modal(self, interaction: discord.Interaction,  button: discord.ui.Button):
        inp = CredentialsInput()
        await interaction.response.send_modal(inp)
        button.disabled = True
        await interaction.edit_original_response(view=self)
        await inp.wait()
        self.interaction = inp.interaction
        self.username = inp.username
        self.password = inp.password
        self.stop()

    @discord.ui.button(label='Why do you need my login?', style=discord.ButtonStyle.grey, row=1)
    async def send_help(self, interaction: discord.Interaction,  button: discord.ui.Button):
        msg = '''
        Unfortunately, Riot does not give an official way to get the shop data, since the shop incentivizes people to open the game.
        This means I have to pretend to be the official client and ask the Riot servers for the shop data. This process requires using your username and password to login.
        '''
        await interaction.response.send_message(dedent(msg), ephemeral=True)

    @discord.ui.button(label='Can I trust you with my login?', style=discord.ButtonStyle.grey, row=1)
    async def send_priv_poli(self, interaction: discord.Interaction,  button: discord.ui.Button):
        msg = '''
        Your login is not used anywhere else and I *cannot* see it when you enter it here.

        While there is no real way for me to prove that I am not lying, I hope the fact this bot has been around for 3+ years is testament to my commitment to create a useful bot instead of any malicious intent.
        
        There are plans to convert this system to never need to store your password and only store cookies, however this is WIP.

        For full transparency, this bot is open source so you can check what it's doing and I will disclose that it is still technically possible for me to view your login after it is saved even if I cannot see it when you submit it, but it will take extra effort to do so as this data wasn't designed for viewing.
        '''
        await interaction.response.send_message(dedent(msg), ephemeral=True)

    @discord.ui.button(label='Will I get banned?', style=discord.ButtonStyle.grey, row=1)
    async def send_banned_disclaimer(self, interaction: discord.Interaction,  button: discord.ui.Button):
        msg = '''
        The short answer is No. However, since this is not officially supported use of the Riot API, so it is "use at own risk". 
        
        Riot said they will not go after those who are not doing anything malicious. For example, instalock scripts *will* get you banned. Checking the shop is not considered malicious or gameplay altering.
        '''
        await interaction.response.send_message(dedent(msg), ephemeral=True)


class _2FAInput(discord.ui.Modal, title='VALORANT 2FA Login'):
    def __init__(self) -> None:
        super().__init__(timeout=180)
        self.interaction = None

    code = discord.ui.TextInput(label='Enter your 6 digit 2fa code', min_length=6, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.interaction = interaction


class _2FAView(discord.ui.View):
    def __init__(self, *, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.author = ctx.author
        self.code = None
        self.interaction = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if interaction.user == self.author:
            return True
        else:
            await interaction.response.send_message('You cannot use this', ephemeral=True)
            return False

    @discord.ui.button(label='Click', style=discord.ButtonStyle.primary)
    async def send_modal(self, interaction: discord.Interaction,  button: discord.ui.Button):
        inp = _2FAInput()
        await interaction.response.send_modal(inp)
        button.disabled = True
        await interaction.edit_original_response(view=self)
        await inp.wait()
        self.interaction = inp.interaction
        self.code = inp.code
        self.stop()


class TWOMView(discord.ui.View):
    def __init__(self, *, player):
        super().__init__(timeout=3600)
        self.player: discord.User = player
        self.even = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if interaction.user == self.player:
            return True
        else:
            await interaction.response.send_message('This game is not yours', ephemeral=True)
            return False

    @discord.ui.button(label='Even')
    async def even(self, interaction: discord.Interaction,  button: discord.ui.Button):
        self.even = True
        self.clear_items()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label='Odd')
    async def odd(self, interaction: discord.Interaction,  button: discord.ui.Button):
        self.even = False
        self.clear_items()
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        self.even = random.choice([True, False])
