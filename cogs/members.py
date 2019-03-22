import discord
from discord.ext import commands


class MembersCog(commands.Cog, name='Member Commands'):
    def __init__(self, bot):
        self.bot = bot

    # Applies commands.guild_only() check for all methods in this cog
    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return True

    @commands.command()
    async def joined(self, ctx, *, member: discord.Member = None):
        """Says when a member joined."""
        if not member:
            member = ctx.author
        await ctx.send(f'{member.display_name} joined on {member.joined_at}')

    @commands.command(name='perms', aliases=['permissions'])
    async def check_permissions(self, ctx, *, member: discord.Member = None):
        """A simple command which checks a members Guild Permissions.
        If member is not provided, the author will be checked."""

        if not member:
            member = ctx.author

        # Check if the value of each permission is True.
        perms = '\n'.join(perm for perm, value in member.guild_permissions if value)

        # Embeds look nicer
        embed = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        embed.set_author(icon_url=member.avatar_url, name=str(member))

        # \uFEFF is a Zero-Width Space, which allows us to have an empty field name.
        embed.add_field(name='\uFEFF', value=perms)

        await ctx.send(content=None, embed=embed)

    @commands.command(name='video in vc', aliases=['viv'])
    async def video_inVC(self, ctx):
        """Enables video call functionality in a guild voice channel"""
        author = ctx.message.author
        timeout = 180  # seconds before the message is self-deleted to reduce clutter

        embed = discord.Embed(title="Video in Voice channel",
                              colour=author.color,
                              description=f"[Click here to join video session for {author.voice.channel.name}](https://discordapp.com/channels/{ctx.message.guild.id}/{author.voice.channel.id}/)\n"
                                          f"Note: You must be in #{author.voice.channel.name} to join")

        await ctx.send(content=f"{author.mention} has started a video session in {author.voice.channel.name}!",
                       embed=embed,
                       delete_after=timeout)
        await ctx.message.delete()  # Delete command invocation message


def setup(bot):
    bot.add_cog(MembersCog(bot))
