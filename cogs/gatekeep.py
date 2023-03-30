import discord
from discord.ext import commands

import asyncio
from utils.global_utils import bright_color
from utils.converters import CaseInsensitiveMember

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
PRIVATE_GENERAL_CHANNEL = 709264610200649741
PUBLIC_GENERAL_CHANNEL = 876381841471471656
VOICE_TEXT_CHANNEL = 868639752105132032
BOT_CHANNEL = 709277913471647824
PINS_CHANNEL = 824496525144096768
GAS_ROLE = 1046676933527744634

SPECIAL_ROLES = [803011517028237332,  # MOVIE ROLE
                 803009777830854677,  # League Role
                 803009851080310824,  # Valorant Role
                 ]


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verified = set()
        bot.loop.create_task(self.get_verified_ids())
        self.pinned = set()
        self.redirecting = asyncio.Lock()

    async def get_verified_ids(self):
        query = '''SELECT id FROM gatekeep;'''
        records = await self.bot.pool.fetch(query)
        self.verified = {record.get('id') for record in records}

    def cog_check(self, ctx):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return False
        return True

    # We will just silently ignore commands not used in the guild
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            ctx.local_handled = True

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return
        if member.id in self.verified:
            await member.add_roles(discord.Object(id=VERIFIED_ROLE), reason='Automatic verification')
        else:
            private = member.guild.get_channel(PRIVATE_GENERAL_CHANNEL)
            await private.set_permissions(member, read_messages=True)
            await asyncio.sleep(3600)
            await private.set_permissions(member, overwrite=None)

    def build_embed(self, message: discord.Message):
        e = discord.Embed(description=message.content,
                          color=bright_color(),
                          timestamp=message.created_at)
        if message.embeds:
            msg_embed = message.embeds[0]
            if msg_embed.type == 'image':
                e.set_image(url=msg_embed.url)

        if message.attachments:
            file = message.attachments[0]
            spoiler = file.is_spoiler()
            if not spoiler and file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                e.set_image(url=file.url)
            elif spoiler:
                e.add_field(name='Attachment', value=f'||[{file.filename}]({file.url})||', inline=False)
            else:
                e.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

        ref = message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            e.add_field(name='Replying to...', value=f'[{ref.resolved.author}]({ref.resolved.jump_url})', inline=False)

        e.add_field(name='Original Message', value=f'[Jump!]({message.jump_url})', inline=False)
        e.set_author(name=f'{message.author.display_name} ({message.author})',
                     icon_url=message.author.display_avatar.with_static_format('png').url)
        e.set_footer(text=message.author.id)
        return e

    @commands.Cog.listener('on_message')
    async def redirect_new_pins(self, message):
        if message.type is discord.MessageType.pins_add and message.channel.id != PINS_CHANNEL:
            if message.channel.id == PRIVATE_GENERAL_CHANNEL:
                ref = message.reference
                ref_msg = await self.bot.get_channel(ref.channel_id).fetch_message(ref.message_id)
                if ref_msg.id in self.pinned:
                    await message.channel.send('This message is already pinned')
                else:
                    embed = self.build_embed(ref_msg)
                    prox = await message.guild.get_channel(PINS_CHANNEL).send(embed=embed)
                    e = discord.Embed(color=0x2F3136,  # rounded corners
                                      description=f'{message.author.mention} pinned a [message]({ref_msg.jump_url}). It has been [posted]({prox.jump_url}) in <#{PINS_CHANNEL}>')
                    await message.channel.send(embed=e)
                    self.pinned.add(ref_msg.id)
                await message.delete()
                await ref_msg.unpin(reason='Pinned in #pins')
                return
            elif message.channel.id == PINS_CHANNEL:
                ref = message.reference
                ref_msg = await self.bot.get_channel(ref.channel_id).fetch_message(ref.message_id)
                await message.delete()
                await ref_msg.unpin()

        if message.channel.id == PINS_CHANNEL:
            if message.author != self.bot.user:
                await message.delete()

    async def _redirect_message(self, original: discord.Message, destination: discord.TextChannel):
        webhook = discord.utils.get(await destination.webhooks(),
                                    user=self.bot.user)

        if webhook is None:
            webhook = await destination.create_webhook(name='Redirect')

        embeds = [e for e in original.embeds if
                  e.type == 'rich' and e.footer.icon_url != 'https://abs.twimg.com/icons/apple-touch-icon-192x192.png'
                  and e.color != 0x1da1f2]

        files = [await attachment.to_file() for attachment in original.attachments]
        await webhook.send(content=original.content,
                           embeds=embeds,
                           files=files,
                           username=original.author.display_name,
                           avatar_url=original.author.display_avatar)

    # @commands.Cog.listener('on_message')
    async def echo_pings(self, message: discord.Message):
        if message.channel.id != PRIVATE_GENERAL_CHANNEL:
            return

        to_ping = set()
        for r in message.role_mentions:
            if r.id in SPECIAL_ROLES:
                to_ping.update({m.id for m in r.members})

        for u in message.mentions:
            if not message.channel.permissions_for(u).read_messages and not u.bot:
                to_ping.add(u.id)

        if not to_ping:
            return

        to_exclude = to_ping & self.verified - {message.author.id}
        public_channel = message.guild.get_channel(PUBLIC_GENERAL_CHANNEL)
        async with self.redirecting:
            for uid in to_exclude:
                user = self.bot.get_user(uid)
                await public_channel.set_permissions(user, read_messages=False)

            await self._redirect_message(message, public_channel)

            for uid in to_exclude:
                user = self.bot.get_user(uid)
                await public_channel.set_permissions(user, overwrite=None)

    # @commands.Cog.listener()
    # async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    #     if member.guild.id != GUILD_ID:
    #         return
    #
    #     if member.guild_permissions.administrator:
    #         return
    #     voice_text_channel = member.guild.get_channel(VOICE_TEXT_CHANNEL)
    #     if before.channel is None and after.channel is not None:
    #         # joined voice channel
    #         await voice_text_channel.set_permissions(member, read_messages=True)
    #     elif before.channel is not None and after.channel is None:
    #         # left voice channel
    #         await voice_text_channel.set_permissions(member, overwrite=None)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def verify(self, ctx, member: CaseInsensitiveMember, level):
        query = '''INSERT INTO gatekeep(id, by, level)
                   VALUES($1, $2, $3)'''
        await self.bot.pool.execute(query, member.id, ctx.author.id, level)
        await member.add_roles(discord.Object(id=VERIFIED_ROLE), reason='Manual verification')
        await ctx.tick()

    @commands.command(name='nick')
    async def change_nick(self, ctx, member: CaseInsensitiveMember, *, nick=None):
        """Change nickname of someone
        `%nick [user] [nickname]`
        leave [nickname] blank to clear nickname"""
        if ctx.author.id not in self.verified:
            return

        if member == ctx.guild.owner:
            return await ctx.reply(f'Due to discord limitations, I cannot change the nickname of {member.mention} as they are the server owner',
                                   allowed_mentions=discord.AllowedMentions.none())

        before = member.nick
        if before is None and nick is None:
            return await ctx.reply(f'{member.mention} does not have a nickname',
                                   allowed_mentions=discord.AllowedMentions.none())

        await member.edit(nick=nick)
        if nick is None:
            msg = f"Cleared {member.mention}'s nickname (was `{before}`)"
        else:
            msg = f"Changed {member.mention} ({member})'s nickname to `{nick}`"
            if before is not None:
                msg += f" (from `{before}`)"
        await ctx.reply(msg, allowed_mentions=discord.AllowedMentions.none())
        await ctx.tick()

    @commands.command(hidden=True)
    async def gas(self, ctx):
        r = ctx.guild.get_role(GAS_ROLE)
        if not r:
            await ctx.send('Unable to find role!')
            return

        if ctx.author.get_role(GAS_ROLE):
            await ctx.author.remove_roles(r)
            await ctx.reply('Removed Gas role', mention_author=False)
        else:
            await ctx.author.add_roles(r)
            await ctx.reply('Added Gas role', mention_author=False)


async def setup(bot):
    await bot.add_cog(Gatekeep(bot))
