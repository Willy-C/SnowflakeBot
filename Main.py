import discord
from discord.ext import commands

from typing import Union

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


@bot.command(aliases=['ava', 'pfp'])
async def avatar(ctx, *, user: discord.Member = None):
    """Returns the avatar link of user"""
    # if user is None:
    #     user = ctx.message.author
    user = ctx.message.author if user is None else user
    await ctx.send(user.avatar_url_as(static_format='png'))


@bot.command(aliases=['presence'])
async def change_presence(ctx, mode: Union[int, str], *, game: str = 'nothing'):
    """Change the bot's presence to specified mode and game"""
    modes = {0: None,
             1: discord.ActivityType.playing,
             2: discord.ActivityType.streaming,
             3: discord.ActivityType.listening,
             4: discord.ActivityType.watching}

    if ctx.message.author.id == 94271181271605248:  # Change to check()

        if mode == 'list':
            await ctx.send('Here is a list of valid modes: \n '
                           '0: None \n '
                           '1: Playing \n'
                           '2: Streaming \n'
                           '3: Listening to \n'
                           '4: Watching')
            return

        # Converts inputted mode to predefined key if mode is a string
        elif isinstance(mode, str):
            mode = mode.lower()
            if mode in ['n', 'none']:
                mode = 0
            elif mode in ['p', 'playing']:
                mode = 1
            elif mode in ['s', 'streaming']:
                mode = 2
            elif mode in ['l', 'listening']:
                mode = 3
            elif mode in ['w', 'watching']:
                mode = 4
            else:
                await ctx.send("Invalid mode! Use: n/p/s/l/w/list)")
                return

        elif mode not in modes:
            await ctx.send("Invalid mode! Use: 0-4 or list")
            return

        if mode == 0:
            await bot.change_presence(activity=None)
            return

        # Make an instance of discord.Activity with given parameters
        activity = discord.Activity(type=modes[mode],
                                    name=game)
        # Change bot's presence with given activity
        await bot.change_presence(activity=activity)

    else:  # Change to check()
        # This command can only be invoked by bot owner
        emote = '<:beemad:545443640323997717>'
        await ctx.send(f"This command can only be invoked by my owner! {emote}")


bot.run(TOKEN)
