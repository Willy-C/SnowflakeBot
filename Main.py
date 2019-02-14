import discord
from discord.ext import commands

PREFIX = '!'
DESCR = 'This is a test'
TOKEN = 'NTQyOTUxOTAyNjY5OTYzMjcx.D0KQQg.7nEH1DzzXWsH6deNad8FftrRh38'

bot = commands.Bot(command_prefix=PREFIX, description=DESCR)


@bot.event
async def on_ready():
    print(f'Logged in as: {bot.user.name}')
    print(f'User id: {bot.user.id}')
    print('------')
    print('Ready!')
    activity = discord.Activity(type=discord.ActivityType.listening,
                                name='you :)')
    await bot.change_presence(activity=activity)


@bot.command()
async def viv(ctx):
    """Returns a link that links current channel and video in an embed"""
    if isinstance(ctx.message.author, discord.User):
        await ctx.author.send(
            f'The command {PREFIX}{ctx.command} can '
            f'not be used in Private Messages.')

    elif ctx.message.author.voice is not None:
        # await ctx.send(f'https://discordapp.com/channels/
        # {ctx.message.guild.id}/{ctx.message.author.voice.channel.id}/')

        author = ctx.message.author  # Instance of Member representing author
        timeout = 120  # seconds before the message is self-deleted

        embed = discord.Embed(title="Video in Voice channel",
                              colour=discord.Colour(0xff0000))

        embed.set_thumbnail(url="https://i.imgur.com/amveTdH.png")
        embed.set_footer(
            text=f"This message will self-delete in {timeout/60} minute(s)"
                 f" to reduce clutter")

        embed.add_field(
            name="----------------------------------------------------------",
            value=f"[Click here to join video session for "
                  f"{author.voice.channel.name}]"
                  f"(https://discordapp.com/channels/"
                  f"{ctx.message.guild.id}/"
                  f"{author.voice.channel.id}/)")
        embed.add_field(
            name=f"Note: You must be in {author.voice.channel.name} to join",
            value=f"Otherwise the link does nothing!")
        await ctx.send(
            content=f"{author.mention} has started a video session in "
                    f"{author.voice.channel.name}!",
            embed=embed, delete_after=timeout)
        await ctx.message.delete()  # Delete command invocation message
    else:
        await ctx.send(
            'You are not in a voice channel! <:beemad:545443640323997717>')


@bot.command()
async def avatar(ctx, *, user: discord.Member = None):
    """Returns the avatar link of user"""
    # if user is None:
    #     user = ctx.message.author
    user = ctx.message.author if user is None else user
    await ctx.send(user.avatar_url_as(static_format='png'))


bot.run(TOKEN)
