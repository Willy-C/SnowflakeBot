import discord
from discord.ext import commands


class MembersCog(commands.Cog, name='Guild'):
    def __init__(self, bot):
        self.bot = bot

    # Applies commands.guild_only() check for all methods in this cog
    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return True

    @commands.command()
    async def joined(self, ctx, *, member: discord.Member = None):
        """Looks up when a member joined the server."""
        if not member:
            member = ctx.author
        await ctx.send(f'{member.display_name} joined on {member.joined_at.isoformat(" ", "seconds")}')

    @commands.command(name='perms', aliases=['permissions'])
    async def check_permissions(self, ctx, *, member: discord.Member = None):
        """Lists all permissions of a member in current guild.
        If member is not provided, the author will be checked."""

        if not member:
            member = ctx.author
        # Check if the value of each permission is True.
        perms = '\n'.join(perm for perm, value in member.guild_permissions if value)

        # Embeds look nicer
        e = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        e.set_author(icon_url=member.avatar_url, name=str(member))
        # \uFEFF is a Zero-Width Space, which allows us to have an empty field name.
        e.add_field(name='\uFEFF', value=perms)

        await ctx.send(content=None, embed=e)

    @commands.command(name='allperms')
    async def check_permissions_long(self, ctx, *, member: discord.Member = None):
        """Lists all permissions and shows which ones the member has.
        If member is not provided, the author will be checked."""
        if not member:
            member = ctx.author
        perms = '\n'.join(f'\U00002705 {perm}' if value else f'<:white_X:555196323574579200> {perm}' for perm, value in
                          member.guild_permissions)

        e = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        e.set_author(icon_url=member.avatar_url, name=str(member))
        e.add_field(name='\uFEFF', value=perms)

        await ctx.send(content=None, embed=e)

    @commands.command(name='sharescreen', aliases=['share', 'ss', 'video'])
    async def video_inVC(self, ctx):
        """Enables video call functionality in a guild voice channel."""
        author = ctx.message.author
        timeout = 600  # seconds before the message is self-deleted to reduce clutter

        if author.voice is None:
            return await ctx.send('You are not in a voice channel! <:beemad:545443640323997717>')
        link = discord.utils.escape_markdown(
            f'https://discordapp.com/channels/{ctx.message.guild.id}/{author.voice.channel.id}/')
        name = discord.utils.escape_markdown(author.voice.channel.name)
        e = discord.Embed(colour=author.color,
                          description=f"[Click here to join video session for {name}]({link})\n"
                                      f"You must be in the voice channel to use this link")

        await ctx.send(embed=e)
        # await ctx.message.delete()  # Delete command invocation message

    @commands.command(name='shareall')
    async def sharescreen_all(self, ctx, output: discord.TextChannel = None):
        """Returns all voice channel's video links
        Output channel is optional, defaults to current channel"""
        if output is None:
            output = ctx.channel

        _vc = [vc for vc in ctx.guild.voice_channels]
        guild_id = ctx.guild.id
        template = f'https://discordapp.com/channels/{guild_id}/'
        links = [f'[{vc.name}]({template}{vc.id})' for vc in _vc]
        combined = '\n'.join(links)
        formatted = discord.utils.escape_markdown(combined)  # because some ppl like to have ||name|| for some reason

        e = discord.Embed(title="Video Links for Voice Channels",
                          colour=6430916,
                          description=formatted)

        await output.send(embed=e)

def setup(bot):
    bot.add_cog(MembersCog(bot))
