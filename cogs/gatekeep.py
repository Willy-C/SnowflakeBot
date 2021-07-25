import discord
from discord.ext import commands

import asyncio
from utils.global_utils import bright_color

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
PRIVATE_GENERAL_CHANNEL = 709264610200649741
PUBLIC_GENERAL_CHANNEL = 868639752105132032
BOT_CHANNEL = 709277913471647824
PINS_CHANNEL = 824496525144096768

SPECIAL_ROLES = [803011517028237332,  # MOVIE ROLE
                 803009777830854677,  # League Role
                 803009851080310824,  # Valorant Role
                 ]


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verified = set()
        bot.loop.create_task(self.get_verified_ids())
        self.tasks = {}
        self.is_redirecting = False
        self.pinned = set()
        self._webhooks = {}

    async def get_verified_ids(self):
        query = '''SELECT id FROM gatekeep;'''
        records = await self.bot.pool.fetch(query)
        self.verified = {record.get('id') for record in records}

    async def get_webhook(self, channel: discord.TextChannel):
        webhook = discord.utils.get(await channel.webhooks(),
                                    user=self.bot.user)
        if webhook is None:
            webhook = await channel.create_webhook(name='Redirect')
            self._webhooks[channel.id] = webhook

        return webhook

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
            public = member.guild.get_channel(PUBLIC_GENERAL_CHANNEL)
            await private.set_permissions(member, read_message_history=True, read_messages=True)
            await public.set_permissions(member, read_messages=False)
            await asyncio.sleep(3600)
            await private.set_permissions(member, overwrite=None)
            await public.set_permissions(member, overwrite=None)

    async def temporary_visibility_task(self, obj, channel, duration=1200):
        await channel.set_permissions(obj, read_message_history=True, read_messages=True)
        await asyncio.sleep(duration)
        await channel.set_permissions(obj, overwrite=None)

    async def temporary_visbility(self, obj, channel, duration=1200):
        task = self.bot.loop.create_task(self.temporary_visibility_task(obj, channel, duration=duration))
        if obj.id in self.tasks:
            try:
                self.tasks.get(obj.id).cancel()
            except asyncio.CancelledError:
                pass
        self.tasks[obj.id] = task

    async def redirect_task(self, duration=1200):
        self.is_redirecting = True
        await asyncio.sleep(duration)
        self.is_redirecting = False

    async def start_redirect(self, duration=1200):
        task = self.bot.loop.create_task(self.redirect_task(duration))
        if 'redirect' in self.tasks:
            try:
                self.tasks.get('redirect').cancel()
            except asyncio.CancelledError:
                pass
        self.tasks['redirect'] = task

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

        e.add_field(name='Original Message', value=f'[Jump!]({message.jump_url})', inline=False)
        e.set_author(name=message.author.display_name, icon_url=message.author.avatar_url_as(format='png'))
        return e

    @commands.Cog.listener('on_message')
    async def redirect_new_pins(self, message):
        if message.guild is None or message.guild.id != GUILD_ID or message.channel.id == PUBLIC_GENERAL_CHANNEL:
            return

        if message.type is discord.MessageType.pins_add and message.channel.id != PINS_CHANNEL:
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

        if message.channel.id == PINS_CHANNEL:
            if message.author != self.bot.user:
                await message.delete()

    @commands.Cog.listener('on_message')
    async def visbility_control(self, message):
        if message.channel.id != PRIVATE_GENERAL_CHANNEL:
            return

        mirror = message.guild.get_channel(PUBLIC_GENERAL_CHANNEL)
        private = message.guild.get_channel(PRIVATE_GENERAL_CHANNEL)
        redirect = False
        for m in message.mentions:
            if not m.permissions_in(private).view_channel:
                await self.temporary_visbility(m, mirror, 1200)
                redirect = True

        for r in message.role_mentions:
            if r.id in SPECIAL_ROLES:
                await self.temporary_visbility(r, mirror, 1200)
                redirect = True

        if redirect:
            await self._redirect_message(message, private)
            await self.start_redirect(1200)

    async def _redirect_message(self, original: discord.Message, destination: discord.TextChannel):
        webhook = self._webhooks.get(destination.id)
        if webhook is None:
            webhook = await self.get_webhook(destination)

        if original.embeds:
            embeds = [e for e in original.embeds if
                      e.type == 'rich' and e.footer.icon_url != 'https://abs.twimg.com/icons/apple-touch-icon-192x192.png']
        else:
            embeds = None
        files = [await attachment.to_file() for attachment in original.attachments]
        await webhook.send(content=original.content,
                           embeds=embeds,
                           files=files,
                           username=original.author.display_name,
                           avatar_url=original.author.avatar_url)

    @commands.Cog.listener('on_message')
    async def forward_messages(self, message):
        if not self.is_redirecting or message.channel.id not in {PUBLIC_GENERAL_CHANNEL, PRIVATE_GENERAL_CHANNEL}:
            return

        if message.channel.id == PUBLIC_GENERAL_CHANNEL:
            output_channel = message.guild.get_channel(PRIVATE_GENERAL_CHANNEL)
        elif message.channel.id == PRIVATE_GENERAL_CHANNEL:
            output_channel = message.guild.get_channel(PUBLIC_GENERAL_CHANNEL)

        await self._redirect_message(message, output_channel)


def setup(bot):
    bot.add_cog(Gatekeep(bot))
