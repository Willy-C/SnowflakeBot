import discord
from discord.ext import commands

import humanize
from datetime import datetime

GUILD_ID = 567520394215686144
FLOATER_ROLE_ID = 567539820545572865


class ViCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vc_history = {597288448562429972: {'join': None,
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

        if before.channel and before.channel.id in self.vc_history:
            self.vc_history[before.channel.id]['leave'] = (str(member), datetime.utcnow())
        if after.channel and after.channel.id in self.vc_history:
            self.vc_history[after.channel.id]['join'] = (str(member), datetime.utcnow())

    # noinspection PyTupleAssignmentBalance
    @commands.command()
    async def who(self, ctx, *, voicechannel: discord.VoiceChannel = None):
        if ctx.guild and ctx.guild.id != GUILD_ID:
            return
        if voicechannel is None:
            if ctx.author.voice is None:
                return await ctx.send('Please specify a voice channel')
            voicechannel = ctx.author.voice.channel

        if voicechannel.id not in self.vc_history:
            return await ctx.send('Sorry, I am not monitoring this vc\'s history', delete_after=30)

        if self.vc_history[voicechannel.id]['leave'] is not None:
            last_leave, leave_time = self.vc_history[voicechannel.id]['leave']
            leave_delta = humanize.naturaldelta(datetime.utcnow() - leave_time)
            await ctx.send(f'Last person to leave {voicechannel} was {last_leave} - {leave_delta} ago')

        if self.vc_history[voicechannel.id]['join'] is not None:
            last_join, join_time = self.vc_history[voicechannel.id]['join']
            join_delta = humanize.naturaldelta(datetime.utcnow() - join_time)
            await ctx.send(f'Last person to join {voicechannel} was {last_join} - {join_delta} ago')


def setup(bot):
    bot.add_cog(ViCog(bot))
