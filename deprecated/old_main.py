import discord
from discord.ext import commands

from typing import Union, Optional
import time

"""
To whomever is reading this file:
    I made this file without really knowing what I was doing so it is messy in a lot of places
    I know this is not very good pls no flame, it was just a side project I wanted to try out for fun.
    These are also some of the reasons why I have decided to redo the entire bot.
"""

PREFIX = '!'
DESCR = 'This bot is a small side project and still very WIP '
# If I eventually make the repo becomes public, this token would have been regenerated.
TOKEN = '--'

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
            f'The command {PREFIX}{ctx.command} can'
            f'not be used in private messages.')

    elif ctx.message.author.voice is not None:
        # await ctx.send(f'https://discordapp.com/channels/
        # {ctx.message.guild.id}/{ctx.message.author.voice.channel.id}/')

        author = ctx.message.author  # Instance of Member representing author
        timeout = 300  # seconds before the message is self-deleted

        embed = discord.Embed(title="Video in Voice channel",
                              colour=discord.Colour(0xff0000),
                              description="[Click here to join video session "
                                          f"for {author.voice.channel.name}]"
                                          f"(https://discordapp.com/channels/"
                                          f"{ctx.message.guild.id}/"
                                          f"{author.voice.channel.id}/)\n"
                                          f"Note: You must be in "
                                          f"#{author.voice.channel.name}"
                                          f" to join")
        #  embed.set_thumbnail(url=bot.user.avatar_url_as(format='png'))
        # embed.set_thumbnail(url="https://i.imgur.com/amveTdH.png")
        # embed.set_footer(
        #     text=f"This message will self-delete in {timeout/60} minute(s)"
        #          f" to reduce clutter")

        # embed.add_field(
        #     name="----------------------------------------------------------",
        #     value=f"[Click here to join video session for "
        #           f"{author.voice.channel.name}]"
        #           f"(https://discordapp.com/channels/"
        #           f"{ctx.message.guild.id}/"
        #           f"{author.voice.channel.id}/)")
        # embed.add_field(
        #     name=f"Note: You must be in #{author.voice.channel.name} to join",
        #     value=f"Otherwise the link does nothing!")
        await ctx.send(
            content=f"{author.mention} has started a video session in "
                    f"{author.voice.channel.name}!",
            embed=embed, delete_after=timeout)
        await ctx.message.delete()  # Delete command invocation message
    else:
        await ctx.send(
            'You are not in a voice channel! <:beemad:545443640323997717>')


@bot.command(aliases=['ava', 'pfp'])
async def avatar(ctx, *, user: Optional[discord.Member] = None):
    """Returns the avatar link of user"""
    # Prints this if user not found
    if user is None:
        await ctx.send("No user found on this server matching that name.\n"
                       "I will search in this order: \n"
                       "1.  By ID                          (ex. 5429519026)\n"
                       "2. By Mention               (ex. @Snowflake)\n"
                       "3. By Name#Discrim  (ex. Snowflake#7321)\n"
                       "4. By Name                   (ex. Snowflake)\n"
                       "5. By Nickname            (ex. BeepBoop)\n"
                       "Note: Names are Case-sensitive!\n")
    else:
        await ctx.send(user.avatar_url_as(static_format='png'))


@bot.command(hidden=True)
async def presence(ctx, mode: Union[int, str] = 0, *,
                   game: str = 'nothing'):
    """Change the bot's presence to specified mode and game"""
    modes = {0: None,
             1: discord.ActivityType.playing,
             2: discord.ActivityType.streaming,
             3: discord.ActivityType.listening,
             4: discord.ActivityType.watching}
    displaymode = {0: 'None',
                   1: 'Playing',
                   2: 'Streaming',
                   3: 'Listening to',
                   4: 'Watching'}

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
            await ctx.send('Removing my current presence')
            await ctx.message.delete()  # Delete command invocation message
            return

        # Make an instance of discord.Activity with given parameters
        activity = discord.Activity(type=modes[mode],
                                    name=game)
        # Change bot's presence with given activity
        await bot.change_presence(activity=activity)
        await ctx.send(f'Setting my presence to: {displaymode[mode]} {game}')
        # await ctx.message.delete()  # Delete command invocation message

    else:  # Change to check()
        # This command can only be invoked by bot owner
        emote = '<:beemad:545443640323997717>'
        await ctx.send(f"This command can only be invoked by my owner! {emote}")


@bot.command()
async def ping(ctx):
    start = time.perf_counter()
    message = await ctx.send('Beep...')
    end = time.perf_counter()
    duration = (end - start) * 1000

    await message.edit(content='Boop\n'
                               'Ping: {:.2f}ms'.format(duration))


bot.run(TOKEN)
