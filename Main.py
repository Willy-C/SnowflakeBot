import discord
from discord.ext import commands

PREFIX = '!'
DESCR = 'This is a test'
TOKEN = 'NTQyOTUxOTAyNjY5OTYzMjcx.D0KQQg.7nEH1DzzXWsH6deNad8FftrRh38'

bot = commands.Bot(command_prefix=PREFIX, description=DESCR)


@bot.event
async def on_ready():
    print(f'Logged in as: {bot.user.name}')
    print(f'User id:  + {bot.user.id}')
    print('------')


@bot.command()
async def video(ctx):
    """Returns a link that links current channel and video"""
    if ctx.message.author.voice is not None:
        await ctx.send(f'https://discordapp.com/channels/{ctx.message.guild.id}'
                       f'/{ctx.message.author.voice.channel.id}/')
    else:
        await ctx.send('You are not in a voice channel! <:beemad:544404624724066304>')


bot.run(TOKEN)
