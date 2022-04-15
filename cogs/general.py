import io
import random
import datetime
import unicodedata
from typing import Optional
from asyncio import TimeoutError

import discord
import googletrans
from PIL import Image
from discord.ext import commands
from discord import app_commands

from utils import converters
from utils.global_utils import last_image, is_image, upload_hastebin, bright_color


def make_more_jpeg(content):
    img = Image.open(content)
    buffer = io.BytesIO()
    img.convert('RGB').save(buffer, "jpeg", quality=random.randrange(1, 8))
    buffer.seek(0)
    return buffer


translator = googletrans.Translator()


async def do_translate(bot, text):
    res = await bot.loop.run_in_executor(None, translator.translate, text)

    embed = discord.Embed(title='Translated', colour=bright_color())
    src = googletrans.LANGUAGES.get(res.src, '(auto-detected)').title()
    dest = googletrans.LANGUAGES.get(res.dest, 'Unknown').title()
    original = res.origin if len(
        res.origin) < 1024 else f'[Text too long to send, uploaded instead]({await upload_hastebin(bot, res.origin)})'
    translated = res.text if len(
        res.text) < 1024 else f'[Text too long to send, uploaded instead]({await upload_hastebin(bot, res.text)})'
    embed.add_field(name=f'From {src}', value=original, inline=False)
    embed.add_field(name=f'To {dest}', value=translated, inline=False)
    if len(res.origin) > 1024 or len(res.text) > 1024:
        embed.description = 'Text too long to send, uploaded instead'

    return embed


@app_commands.context_menu(name='Translate')
async def translate_contextmenu(interaction: discord.Interaction, message: discord.Message):
    if not message.content:
        await interaction.response.send_message('This message has no content!', ephemeral=True)
        return
    try:
        embed = await do_translate(interaction.client, message.content)
    except Exception as e:
        await interaction.response.send_message(f'An error occurred: {e.__class__.__name__}: {e}', ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed)


class GeneralCog(commands.Cog, name='General'):
    def __init__(self, bot):
        self.bot = bot
        self.translator = translator

    @commands.command(name='avatar', aliases=['ava', 'pfp'])
    async def get_avatar(self, ctx, *, user: converters.CaseInsensitiveMember = None):
        """Retrieves the avatar of a user.
        Defaults to author if no user is provided."""
        user = user or ctx.author
        avatar_url = user.display_avatar.with_static_format('png')

        if user.avatar:
            query = '''SELECT url
                       FROM avatar_changes
                       WHERE hash = $1'''
            record = await self.bot.pool.fetchrow(query, user.avatar.key)
            if record:
                avatar_url = record['url']
            else:
                avatar_url = await self.bot.get_cog('TrackerCog').log_avatar(user)

        embed = discord.Embed(colour=user.colour)
        embed.set_image(url=avatar_url)
        embed.set_author(name=user, url=avatar_url)

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def quote(self, ctx, user: converters.CaseInsensitiveMember, *, message):
        """Send a message as someone else
        Requires manage webhooks permission"""
        webhook = discord.utils.get(await ctx.channel.webhooks(),
                                    user=self.bot.user)

        if webhook is None:
            webhook = await ctx.channel.create_webhook(name='Quote')

        await webhook.send(message,
                           username=user.display_name,
                           avatar_url=user.display_avatar.with_static_format('png'),
                           allowed_mentions=discord.AllowedMentions.none())
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.command(name='poll')
    async def create_poll(self, ctx, *questions_and_choices: str):
        """Makes a poll.
        Ex. %poll "question here" "answer 1" answer2 "answer 3"...
        " " Quotations only necessary if there are spaces.
        """
        if len(questions_and_choices) < 3:
            await ctx.send('Need at least 1 question with 2 choices.')
            return await ctx.send(f'Ex. {ctx.prefix}poll "Is this bot good?" Yes No "Answer with spaces must be quoted" Maybe')
        elif len(questions_and_choices) > 21:
            return await ctx.send('You can only have up to 20 choices.')

        perms = ctx.channel.permissions_for(ctx.me)
        if not (perms.read_message_history or perms.add_reactions):
            return await ctx.send('Need Read Message History and Add Reactions permissions.')

        question = questions_and_choices[0]
        choices = [(to_emoji(e), v) for e, v in enumerate(questions_and_choices[1:])]

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        body = "\n".join(f"{key}: {c}" for key, c in choices)
        e = discord.Embed(color=0xFFFF00, timestamp=datetime.datetime.utcnow())
        e.set_footer(text=ctx.author)
        e.add_field(name=f'{question}', value=body)
        poll = await ctx.send(embed=e)

        for emoji, _ in choices:
            await poll.add_reaction(emoji)

    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        """Gives you information about character(s).
        Only up to 25 characters at a time.
        """
        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Name not found.')
            return f'`\\U{digit:>08}`: {name} \U00002014 {c} \U00002014 <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        if len(msg) > 2000:
            await ctx.send('Up to 25 characters at a time and no custom emojis!', delete_after=5)
            return await ctx.send('Output too long to display.')
        await ctx.send(msg)

    @commands.command(hidden=True)
    async def eyes(self, ctx, msg: Optional[discord.Message]):
        """Send old eyes emoji (twemoji v2.2)
        or give a message ID to add reaction instead"""
        if msg:
            try:
                await msg.add_reaction('<:eyes:644633489727291402>')
            except discord.HTTPException:
                pass
        else:
            await ctx.send('<:eyes:644633489727291402>')

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.command(name='needsmorejpeg', aliases=['needsmorejpg', 'morejpeg', 'morejpg'])
    async def needs_more_jpeg(self, ctx, url=None):
        url = url or await last_image(ctx)
        if url is None:
            return await ctx.send('Unable to find an image')
        if not await is_image(ctx, url):
            return await ctx.send('That is not a valid image url')
        async with self.bot.session.get(url) as resp:
            data = io.BytesIO(await resp.read())
        jpeg = await self.bot.loop.run_in_executor(None, make_more_jpeg, data)
        await ctx.send(file=discord.File(jpeg, filename='more_jpeg.jpg'))

    async def get_txt_from_file(self, ctx, messages=[]):
        for msg in messages:
            if msg.attachments:
                for attachment in msg.attachments:
                    if attachment.filename.endswith(('.txt', '.py', '.java', '.json')):
                        try:
                            async with ctx.bot.session.get(attachment.url) as resp:
                                content = await resp.text()
                        except:
                            pass
                        else:
                            return content

    @commands.command(name='filetopaste', aliases=['txttopaste', 'ftp'])
    async def txt_to_pastebin(self, ctx, message: discord.Message = None):
        """Upload the last text file in chat (within 25 messages)
        Sending a .txt file because your message is too long?
        Use this command to upload it so people dont have to download a file!
        """
        messages = []
        if message:
            messages.append(message)
        else:
            messages.extend(await ctx.channel.history(limit=25).flatten())
        content = await self.get_txt_from_file(ctx, messages)
        if content is None:
            return await ctx.send('Unable to find a txt file. Try specifying a message URL or ID')
        url = await upload_hastebin(ctx, content)
        await ctx.send(url)

    @commands.command()
    async def translate(self, ctx, *, text: commands.clean_content=None):
        """Translates a message to English using Google translate.
        If no message is given, I will try and find the last message with text or use the replied message if available"""
        if text is None:
            if ctx.replied_message and ctx.replied_message.content:
                text = ctx.replied_message.clean_content
            else:
                async for message in ctx.channel.history(limit=25, before=ctx.message):
                    if message.content:
                        text = message.clean_content
                        break
                if text is None:
                    return await ctx.send('Unable to find text to translate!')

        try:
            embed = await do_translate(self.bot, text)
        except Exception as e:
            return await ctx.send(f'An error occurred: {e.__class__.__name__}: {e}')

        await ctx.send(embed=embed)

    @commands.command()
    async def say(self, ctx, *, message):
        await ctx.send(message, allowed_mentions=discord.AllowedMentions.none())

    @commands.command()
    async def waitfor(self, ctx, channel: Optional[discord.TextChannel], user: converters.CaseInsensitiveMember = None):
        """Wait for a reply to your channel
        Will send you a DM when I see a reply

        - Will not trigger on messages by you or bots
        - Only waits for a max of 24 hours
        - You can specify a channel to wait for in, if none is given, defaults to this channel
        - You can specify a user to only wait for their message, if none is given, defaults to anyone

        `Ex. %waitfor` will wait for a message from anyone in the current channel
        `Ex. %waitfor Bob` will wait for a message from Bob in the current channel
        `Ex. %waitfor #general Bob` will wait for a message from Bob in #general"""
        if not ctx.guild and channel is None:
            return await ctx.send('Please specify a channel!')
        await ctx.send(f'Waiting for reply from `{user if user is not None else "anyone"}` in {f"`{channel}`" if channel else "this channel"} for up to 24 hours', delete_after=5)
        await ctx.message.add_reaction('<a:typing:559157048919457801>')
        channel = channel or ctx.channel
        try:
            msg = await self.bot.wait_for('message',
                                          check=lambda m: m.channel == channel
                                                          and m.author != ctx.author
                                                          and not m.author.bot
                                                          and (not user or m.author == user),
                                          timeout=129600)
        except TimeoutError:
            try:
                await ctx.message.add_reaction('<:redTick:602811779474522113>')
            except discord.HTTPException:
                pass
        else:
            try:
                await ctx.message.add_reaction('\U00002705')
            except discord.HTTPException:
                pass
            try:
                e = discord.Embed(title=f'You got a reply at: {channel.guild} | #{channel}',
                                  description=f'{msg.author}: {msg.content}\n'
                                              f'[Jump to message]({msg.jump_url})',
                                  colour=0x0DF33E,
                                  timestamp=datetime.datetime.utcnow())
                await ctx.author.send(embed=e)
            except discord.Forbidden:
                pass
        finally:
            try:
                await ctx.message.remove_reaction('<a:typing:559157048919457801>', ctx.me)
            except discord.HTTPException:
                pass


def to_emoji(c):
    base = 0x1f1e6
    return chr(base + c)


def setup(bot):
    bot.add_cog(GeneralCog(bot))
    bot.tree.add_command(translate_contextmenu)
