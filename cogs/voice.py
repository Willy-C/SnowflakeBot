import discord
from discord.ext import commands
from asyncio import TimeoutError
from utils.converters import CaseInsensitiveVoiceChannel


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def secure(self, ctx, voicechannel: CaseInsensitiveVoiceChannel = None):
        if (not ctx.guild or not ctx.author.voice) and voicechannel is None:
            return await ctx.send('You are not in a voice channel!')
        voicechannel = voicechannel or ctx.author.voice.channel
        if not voicechannel.guild.me.guild_permissions.mute_members:
            return await ctx.send('I do not have permission to mute!')

        await ctx.message.add_reaction('<a:typing:559157048919457801>')

        def check(member, before, after):
            return (member != ctx.author
                    and before.channel != voicechannel
                    and after.channel == voicechannel
                    and ctx.author in voicechannel.members)
        try:
            await self.bot.wait_for('voice_state_update', check=check, timeout=43200)
        except TimeoutError:
            pass
        else:
            await ctx.author.edit(mute=True)
        await ctx.message.add_reaction('<:greenTick:602811779835494410>')
        try:
            await ctx.message.remove_reaction('<a:typing:559157048919457801>', ctx.me)
        except:
            pass


def setup(bot):
    bot.add_cog(Voice(bot))
