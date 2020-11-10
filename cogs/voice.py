import discord
from discord.ext import commands

import contextlib
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
        if not ctx.guild:
            ctx.author = voicechannel.guild.get_member(ctx.author.id)

        await ctx.message.add_reaction('<a:typing:559157048919457801>')
        await ctx.message.add_reaction('<:status_online:602811779948740627>')

        current_members = voicechannel.members

        def check(member, before, after):
            return (member != ctx.author
                    and not member.bot
                    and before.channel != voicechannel
                    and after.channel == voicechannel
                    and ctx.author in voicechannel.members
                    and member not in current_members) \
                   or (member == ctx.author
                       and before.channel == voicechannel
                       and after.channel != voicechannel)
        try:
            member, _, _ = await self.bot.wait_for('voice_state_update', check=check, timeout=43200)
        except TimeoutError:
            await ctx.message.add_reaction('<:status_idle:602811780129095701>')
            return
        else:
            if member != ctx.author:
                await ctx.author.edit(mute=True)
                await ctx.message.add_reaction('<:status_dnd:602811779931701259>')
            else:
                await ctx.message.add_reaction('<:status_idle:602811780129095701>')
        finally:
            with contextlib.suppress(discord.HTTPException):
                await ctx.message.remove_reaction('<a:typing:559157048919457801>', ctx.me)
                await ctx.message.remove_reaction('<:status_online:602811779948740627>', ctx.me)

        if member != ctx.author:
            await ctx.message.add_reaction('\U0000203c')

            def reaction_check(reaction, user):
                return reaction.message.id == ctx.message.id and user == ctx.author and str(reaction.emoji) == '\U0000203c'
            try:
                await self.bot.wait_for('reaction_add', check=reaction_check, timeout=120)
            except TimeoutError:
                pass
            else:
                await ctx.author.edit(mute=False)
            finally:
                try:
                    await ctx.message.clear_reaction('\U0000203c')
                except discord.HTTPException:
                    pass


def setup(bot):
    bot.add_cog(Voice(bot))
