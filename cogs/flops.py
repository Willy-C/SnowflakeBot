from __future__ import annotations

import asyncio
from datetime import timedelta
from collections import Counter
from typing import TYPE_CHECKING, Optional, Literal

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import SnowflakeBot
    from utils.context import Context

GUILD_IDS = [709264610200649738, 561073510127108096]


class FlopView(discord.ui.View):
    message: discord.Message

    def __init__(self, flopper: discord.Member, *, cog, limit=None, timeout=600):
        super().__init__(timeout=timeout)
        self._votes: dict[int, Literal['Yes', 'No']] = {}  # user: vote
        self.flopper: discord.Member = flopper
        self.limit: Optional[int] = limit
        self.cog: Flopper = cog
        self._end_task: asyncio.Task = self.cog.bot.loop.create_task(self._explicit_end())

    def get_vote_total(self) -> Counter:
        counter = Counter(self._votes.values())
        return counter

    def calculate_result(self) -> bool:
        """Return True if the vote passed, False if it failed
        If its a tie, if flopper voted then it passes, else it fails
        """
        votes = self.get_vote_total()
        if len(self._votes) < 2:
            return False

        if votes['Yes'] > votes['No']:
            return True
        elif votes['No'] > votes['Yes']:
            return False
        else:
            if len(self._votes) == 2:
                return False
            return self.flopper.id in self._votes

    def _update_embed(self) -> discord.Embed | None:
        votes = self.get_vote_total()
        if not self.message.embeds:
            return
        embed = self.message.embeds[0]
        embed.clear_fields()

        for choice in ('Yes', 'No'):
            embed.add_field(name=choice, value=votes[choice])

        return embed

    def end_embed(self) -> discord.Embed | None:
        if not self.message.embeds:
            return
        embed = self.message.embeds[0]
        result = self.calculate_result()
        if result:
            embed.colour = discord.Color.green()
        else:
            embed.colour = discord.Color.red()
        embed.description = f'Flop vote for {self.flopper.mention} has ended.\nThe verdict: {"Flopped!" if result else "No Flop!"}'

        return embed

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._votes[interaction.user.id] = 'Yes'
        embed = self._update_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='No', style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._votes[interaction.user.id] = 'No'
        embed = self._update_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_end(self) -> None:
        if self.message:
            embed = self.end_embed()
            try:
                await self.message.edit(view=None, embed=embed)
            except discord.NotFound:
                pass
            result = self.calculate_result()
            await self.message.channel.send(f'Flop vote for {self.flopper.mention} has ended.\nThe verdict: {"Flopped!" if result else "No Flop!"}',
                                            reference=self.message.to_reference(fail_if_not_exists=False))

        if self.calculate_result():
            await self.cog.add_flop(self.flopper.id, count=1)

    async def _explicit_end(self) -> None:
        await asyncio.sleep(self.timeout)
        self.stop()
        await self._handle_end()

    async def on_timeout(self) -> None:
        try:
            self._end_task.cancel()
        except asyncio.CancelledError:
            pass
        await self._handle_end()


class Flopper(commands.Cog):
    def __init__(self, bot: SnowflakeBot):
        self.bot: SnowflakeBot = bot

    async def add_flop(self, user_id: int, count=1):
        query = '''INSERT INTO flop_count(id, count) VALUES ($1, $2)
                   ON CONFLICT (id) DO UPDATE SET count = flop_count.count + $2'''
        await self.bot.pool.execute(query, user_id, count)

    @commands.hybrid_group(name='flop', description='Start a flop vote', fallback='vote')
    @app_commands.guilds(*GUILD_IDS)
    async def flop(self, ctx: Context, *, flopper: discord.Member):
        if flopper.bot:
            return await ctx.send('Invalid flopper!')
        timeout = 10 # minutes
        embed = discord.Embed(
            title=f'Flop Vote for {flopper} - by {ctx.author}',
            description=f'Did {flopper.mention} flop?\nCloses {discord.utils.format_dt(discord.utils.utcnow()+timedelta(minutes=timeout), "R")}',
            color=discord.Color.yellow()
        )
        view = FlopView(flopper, cog=self, timeout=timeout*60)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    @flop.command(name='leaderboard', aliases=['lb'], description='Show flop leaderboard')
    async def flop_leaderboard(self, ctx: Context):
        query = '''SELECT id, count FROM flop_count ORDER BY count DESC;'''
        records = await self.bot.pool.fetch(query)
        if not records:
            return await ctx.send('No flops have been recorded yet.')

        lb = '\n'.join(f'{idx + 1}. <@{record["id"]}> - {record["count"]}' for idx, record in enumerate(records))
        embed = discord.Embed(
            title='Flop Leaderboard',
            description=lb,
            color=discord.Color.teal()
        )
        await ctx.send(embed=embed)

    @flop.command(name='stats', description='Show your flop stats')
    async def flop_stats(self, ctx: Context, *, member: Optional[discord.Member] = None):
        member = member or ctx.author
        query = '''SELECT count FROM flop_count WHERE id = $1'''
        record = await self.bot.pool.fetchrow(query, member.id)
        if not record:
            count = 0
        else:
            count = record['count']

        await ctx.send(f'{member.mention} has flopped {count} time(s).', allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: SnowflakeBot):
    await bot.add_cog(Flopper(bot))
