import discord
from discord.ext import commands


class VideoInVoiceChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='Video in VC', aliases=['viv'], brief='Enables video call functionality on a voice channel')
    @commands.guild_only()
    async def enable_videoinVC(self, ctx):
        author = ctx.message.author
        timeout = 300  # seconds before the message is self-deleted

        embed = discord.Embed(title="Video in Voice channel",
                              colour=author.color,
                              description=f"[Click here to join video session for {author.voice.channel.name}](https://discordapp.com/channels/{ctx.message.guild.id}/{author.voice.channel.id}/)\n"
                                          f"Note: You must be in #{author.voice.channel.name} to join")

        await ctx.send(content=f"{author.mention} has started a video session in {author.voice.channel.name}!",
                       embed=embed,
                       delete_after=timeout)
        await ctx.message.delete()  # Delete command invocation message


def setup(bot):
    bot.add_cog(VideoInVoiceChannel(bot))
