import discord
from discord.ext import commands

import humanize
from datetime import datetime

GUILD_ID = 567520394215686144
FLOATER_ROLE_ID = 567539820545572865


class ViCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vc_history = {658169579452760099: {'join': None,
                                                'leave': None},
                           631344051442155520: {'join': None,
                                                'leave': None}}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return

        floater = discord.Object(id=FLOATER_ROLE_ID)
        try:
            await member.add_roles(floater)
        except (discord.HTTPException, AttributeError):
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.guild.id != GUILD_ID:
            return

        if before.channel and before.channel.id in self.vc_history and after.channel != before.channel:
            self.vc_history[before.channel.id]['leave'] = (str(member), datetime.utcnow())
        if after.channel and after.channel.id in self.vc_history and before.channel != after.channel:
            self.vc_history[after.channel.id]['join'] = (str(member), datetime.utcnow())

    # noinspection PyTupleAssignmentBalance
    @commands.command(hidden=True)
    async def who(self, ctx, *, voicechannel: discord.VoiceChannel = None):
        if ctx.guild and ctx.guild.id != GUILD_ID:
            return
        if ctx.author.voice is not None:
            voicechannel = voicechannel or ctx.author.voice.channel
        if ctx.author.id not in (ctx.guild.owner_id, self.bot.owner_id) and (ctx.author.voice is None or ctx.author.voice.channel != voicechannel):
            return await ctx.send('You are not in that voice channel!', delete_after=15)

        if voicechannel is None and ctx.author.voice is None:
            return await ctx.send('Please specify a voice channel', delete_after=15)

        if voicechannel.id not in self.vc_history:
            return await ctx.send('Sorry, I am not monitoring this vc\'s history', delete_after=15)

        if self.vc_history[voicechannel.id]['leave'] is not None:
            last_leave, leave_time = self.vc_history[voicechannel.id]['leave']
            leave_delta = humanize.naturaldelta(datetime.utcnow() - leave_time)
            await ctx.send(f'Last person to leave {voicechannel} was {last_leave} - {leave_delta} ago', delete_after=30)

        if self.vc_history[voicechannel.id]['join'] is not None:
            last_join, join_time = self.vc_history[voicechannel.id]['join']
            join_delta = humanize.naturaldelta(datetime.utcnow() - join_time)
            await ctx.send(f'Last person to join {voicechannel} was {last_join} - {join_delta} ago', delete_after=30)


def setup(bot):
    bot.add_cog(ViCog(bot))
