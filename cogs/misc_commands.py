import discord
from discord.ext.commands import Cog, Context, command
from my_bot import MyBot
from io import BytesIO
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
from http_session import http_session
from bot_config import bot_config
import datetime


class MiscCommands(Cog, name="Misc Commands"):
    
    def __init__(self, bot: MyBot):
        self.newt_id = 266639261523116053
        self.bot = bot

    @command()
    async def suggest(self, ctx: Context, *args):
        suggestion = ' '.join(args)
        description = suggestion
        embed = discord.Embed(title=ctx.message.author.name, description=description,
                              color=0x0760FA)
        channel = await self.bot.get_suggestion_channel()
        message = await channel.send(embed=embed)
        await message.add_reaction(':yes_emoji:529842623532367872')
        await message.add_reaction(':no_emoji:529843815415021587')
        await ctx.message.add_reaction('👌')
    
    @command()
    async def gib_code(self, ctx: Context):
        await ctx.send("https://github.com/ZackUnfair/yet-another-waifu-bot")
    
    @command()
    async def uwot(self, ctx: Context, member: discord.Member, *args):
        author = ctx.message.author
        url = member.avatar_url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                target_avatar = await resp.read()
        url = author.avatar_url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                author_avatar = await resp.read()
        base = Image.open('images/uwot.png').convert('RGBA')
        target_av = Image.open(BytesIO(target_avatar)).convert('RGBA')
        target_av = ImageOps.fit(target_av, (260, 260))
        target_av2 = Image.open(BytesIO(target_avatar)).convert('RGBA')
        target_av2 = ImageOps.fit(target_av2, (114, 114))
        author_av = Image.open(BytesIO(author_avatar)).convert('RGBA')
        author_av = ImageOps.fit(author_av, (122, 122))

        txt = Image.new('RGBA', base.size, (255, 255, 255, 0))

        fnt = ImageFont.truetype('fonts/big_noodle_titling.ttf', 20)
        d = ImageDraw.Draw(txt)

        res = ""
        for a in args:
            res += a
            res += " "

        d.text((455, 450), res, font=fnt, fill=(0, 0, 0, 255))

        txt = txt.rotate(-25, resample=Image.BILINEAR)
        out = Image.alpha_composite(base, txt)
        out.paste(target_av, box=(85, 360))
        out.paste(author_av, box=(116, 33))
        out.paste(target_av2, box=(477, 8))
        output = BytesIO()
        out.save(output, format="PNG")
        output.seek(0)
        f = discord.File(output, 'uwot.png')
        await ctx.send(file=f)
        output.close()
    
    @command()
    async def insult(self, ctx: Context, member: discord.Member):
        name = member.nick if member.nick is not None else member.name
        author = ctx.message.author
        if member.id == self.bot.user.id:
            await ctx.send("No u.")
            name = author.nick if author.nick is not None else author.name
        session = http_session.get_connection()
        params = {'who': name}
        async with session.get("https://insult.mattbas.org/api/insult", params=params) as resp:
            response = await resp.text()
        await ctx.send(response)

    @command()
    async def rip(self, ctx: Context, member: discord.Member):
        await ctx.send(
            f"{member.mention}, hope you come back to life one day.")

    @command()
    async def no_bully(self, ctx: Context, member: discord.Member):
        author = ctx.message.author
        if author.id == self.newt_id:
            await ctx.send(
                f"{member.mention} stop it! Don't be mean to Newt he did nothing to deserve this.")
        elif member.id not in [self.newt_id]:
            await ctx.send(
                f"{member.mention}, you're being mean to {author.name} again. "
                "It's mean to bully someone too much unless it's Colm.") 
        if member.id == self.newt_id:
            await ctx.send("Newt it's fine don't worry about them. "
                           f"Just pay attention to me more and ignore what {author.name} is trying to say.")
    
    def is_before(self, last_time, delta_h):
        # if between 0 and 6 then same day else next day, set breakpoint, then simply check if now is before it
        # only care for the hour and set day accordingly
        now = datetime.datetime.now(tz=last_time.tzinfo)
        return (last_time + datetime.timedelta(hours=delta_h)) <= now

    @command()
    async def test_time(self, ctx: Context):
        last_time = bot_config.config.get('reset_time', None)
        if last_time is None or self.is_before(last_time, 1):
            bot_config.update_reset_time()
            await ctx.send("Necessary time passed, updated to new time.")
        else:
            await ctx.send("Nope, not yet")


def setup(bot: MyBot):
    c = MiscCommands(bot)
    bot.add_cog(c)
