import io
import aiohttp
from datetime import datetime

import discord
from discord.ext import commands
from utils.global_utils import bright_color
from config import WOLFRAM_ALPHA_APPID

TEX_API = 'http://rtex.probablyaweb.site/api/v2'
WOLFRAM_API = 'http://api.wolframalpha.com/v1/simple'
TEMPLATE = r'''
\documentclass{article}

\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
\usepackage{geometry}
\usepackage{mathtools}
\usepackage{amsthm}
\usepackage{amssymb}
\usepackage{amsfonts}
\usepackage{chemfig}
\usepackage{color}
\usepackage{xcolor}
\geometry{textwidth=8cm}

\begin{document}
\pagenumbering{gobble}
\definecolor{darktheme}{HTML}{36393F}

\color{white}
\pagecolor{darktheme}

USERINPUTHERE

\end{document}
'''


class TexRenderError(commands.CommandError):
    def __init__(self, logs):
        self.logs = logs


class MathCog(commands.Cog, name='Math'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['tex'])
    async def latex(self, ctx, *, latex):
        if latex.startswith('```') and latex.endswith('```'):
            latex = '\n'.join(latex.split('\n')[1:-1])
        to_render = TEMPLATE.replace('USERINPUTHERE', latex)
        await self.render(ctx, to_render)

    async def render(self, ctx, latex):
        try:
            payload = {'code': latex, 'format': 'png'}
            async with self.bot.session.post(TEX_API, data=payload) as r:
                r.raise_for_status()
                jdata = await r.json()
                if jdata['status'] != 'success':
                    raise TexRenderError(jdata.get('log'))
                file_url = TEX_API + '/' + jdata['filename']

            async with self.bot.session.get(file_url) as fr:
                fr.raise_for_status()
                data = io.BytesIO(await fr.read())
                await ctx.send(file=discord.File(data, 'latex.png'))

        except aiohttp.ClientResponseError:
            raise TexRenderError(None)

    @commands.command(name='wolframalpha', aliases=['wolfram', 'wa', 'math', 'solve'])
    async def wolframalpha(self, ctx, *, query):
        wolfram_payload = {
            'appid': WOLFRAM_ALPHA_APPID,
            'i': query,
            'layout': 'labelbar',
            'background': 'black',
            'foreground': 'white',
            'width': '800',
            'fontsize': '22',
            'units': 'metric',
        }
        await ctx.trigger_typing()
        async with self.bot.session.get(WOLFRAM_API, params=wolfram_payload) as resp:
            print(resp.status)
            if resp.status == 501:
                return await ctx.reply('Invalid query')
            data = io.BytesIO(await resp.read())

        e = discord.Embed(color=bright_color(), timestamp=datetime.utcnow())
        e.set_image(url='attachment://response.png')
        e.set_footer(text=f'Query: {query[:30] + "..." if len(query)>30 else query}')
        await ctx.reply(embed=e, file=discord.File(data, filename='response.png'), mention_author=False)
        await ctx.tick()


def setup(bot):
    bot.add_cog(MathCog(bot))
