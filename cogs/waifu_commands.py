import discord
from discord.ext.commands import command, Context, group, Cog
import asyncio
import random
from waifu_manager import waifu_manager
from http_session import http_session
import itertools
from difflib import SequenceMatcher
from timers import timers
import os
import unicodedata
import github_api

from my_bot import MyBot


WAIFU_CLAIM_DELTA = 60
API_URL = "https://api.jikan.moe/v3/"
COMICVINE_API_KEY = os.getenv("COMICVINE_API_KEY")
COMICVINE_URL = "https://comicvine.gamespot.com/api/"
COMICVINE_TOTAL_CHARS = 100000
PASTEBIN_API_URL = "https://pastebin.com/api/api_post.php"
PASTEBIN_API_KEY = os.getenv('PASTEBIN_API_KEY')


class WaifuCommands(Cog, name="Waifu Commands"):

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.current_trades = {}
        self.waiting_to_trade = []

    async def find_mal(self, kind, name, limit):
        response = ""
        params = {'q': name, 'limit': limit}
        session = http_session.get_connection()
        async with session.get(API_URL + f"search/{kind}/", params=params) as resp:
            response = await resp.json()

        error = response.get('error', None)
        if error is not None:
            return None
        return response

    @command()
    async def lookup(self, ctx: Context, *args: str):
        name = ' '.join(args)
        message = ""
        response = await self.find_mal("character", name, 30)
        if response is None:
            await ctx.send("Character not found")
            return
        for character in response['results']:
            character_name = character['name'].split(', ')
            character_name.reverse()
            character_name = ' '.join(character_name)
            if name.lower() not in character_name.lower():
                continue
            message += str(character['mal_id'])
            message += " | "
            message += character_name
            message += "\n"
        embed = discord.Embed(title=f"Lookup: {name}", description=message,
                              color=0x200FB4)
        await ctx.send(embed=embed)

    @command()
    async def info(self, ctx: Context, *args: str):
        args = list(args)
        is_extended = False
        if args[-1].startswith('-extended'):
            DESCRIPTION_LIMIT = 1997
            SERIES_LIMIT = 20
            footer = "Use ?info to view shorter description."
            is_extended = True
            del args[-1]
        else:
            DESCRIPTION_LIMIT = 249
            SERIES_LIMIT = 2
            footer = "Use ?info name -extended to view extended description."
        if args[0].isdigit():
            response = await self.get_waifu_by_id(args[0])
            if response is None:
                await ctx.send("No character with that id found")
                return
        else:
            name = ' '.join(args)
            character_id = None
            response = await self.find_mal("character", name, 1)
            if response is None:
                await ctx.send("Character not found")
                return
            character = response['results'][0]
            character_id = str(character['mal_id'])
            response = ""
            session = http_session.get_connection()
            async with session.get(API_URL + f"/character/{character_id}/") as resp:
                response = await resp.json()

        description = response['about'][:DESCRIPTION_LIMIT]
        if len(response['about']) > DESCRIPTION_LIMIT:
            description += '...'
        title = f"{response['name']} ({response['name_kanji']}) ({response['mal_id']})"
        embed = discord.Embed(title=title, description=description, color=0x8700B6)
        if response.get('animeography', None) is not None and\
                response['animeography'] != []:
            anime_list = ""
            counter = 0
            for anime in response['animeography']:
                if counter == SERIES_LIMIT:
                    anime_list += "..."
                    break
                anime_list += anime['name']
                anime_list += "\n"
                counter += 1
            embed.add_field(name="Anime", value=anime_list, inline=False)
        if response.get('mangaography', None) is not None and\
                response['mangaography'] != []:
            manga_list = ""
            counter = 0
            for manga in response['mangaography']:
                if counter == SERIES_LIMIT:
                    manga_list += "..."
                    break
                manga_list += manga['name']
                manga_list += "\n"
                counter += 1
            embed.add_field(name="Manga", value=manga_list, inline=False)
        if is_extended:
            embed.add_field(name="Favorites", value=response['member_favorites'])
        embed._image = {
            'url': str(response['image_url'])
        }
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)
    
    @command()
    async def cinfo(self, ctx: Context, *args: str):
        args = list(args)
        author = ctx.message.author
        r_map = {
            0: "0⃣",
            1: "1⃣",
            2: "2⃣",
            3: "3⃣",
            4: "4⃣",
            5: "5⃣",
            "cancel": "⏹"
        }
        
        name = ' '.join(args)
        response = await self.find_comicvine_char(name)
        
        embed = discord.Embed(title=name.capitalize(), color=0x09d3e3)
        for i, character in enumerate(response['results']):
            embed.add_field(name=f"{i+1}: **{character['name']}**",
                            value=f"Real name: {character['real_name']}",
                            inline=False)
        msg = await ctx.send(embed=embed)

        for i in range(len(response['results'])):
            await msg.add_reaction(r_map[i + 1])
        await msg.add_reaction("⏹")

        def check(reaction, user):
            e = str(reaction.emoji)
            return e.startswith(('1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '⏹')) and user.id == author.id\
                and reaction.message.id == msg.id

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send("You didn't pick in time, too bad.")
            return
        await msg.delete()
        choice = None
        for k, v in r_map.items():
            if v == str(reaction.emoji):
                choice = k
                break
        
        if choice == "cancel":
            return

        url = response['results'][choice - 1]['api_detail_url']
        session = http_session.get_connection()
        params = {
            'api_key': COMICVINE_API_KEY,
            'format': 'json',
            'field_list': 'name,real_name,deck,image,site_detail_url'
        }
        async with session.get(url, params=params) as resp:
            response = await resp.json()
        
        character = response["results"]
        embed = discord.Embed(title=f"{character['name']}", color=0x09d3e3,
                              url=character['site_detail_url'])
        embed._image = {
            'url': character['image']['medium_url']
        }
        embed.add_field(name="Real name", value=character['real_name'], inline=False)
        embed.add_field(name="Description", value=character['deck'], inline=False)
        await ctx.send(embed=embed)

    async def find_comicvine_char(self, name):
        session = http_session.get_connection()
        params = {
            'api_key': COMICVINE_API_KEY,
            'format': 'json',
            'limit': 5,
            'query': name,
            'resources': 'character',
            'field_list': 'name,api_detail_url,real_name'
        }
        async with session.get(COMICVINE_URL + "search", params=params) as resp:
            response = await resp.json()
        if response['error'] != "OK":
            return None
        return response

    @command()
    async def series_lookup(self, ctx: Context, *args: str):
        message = ""
        name = ' '.join(args)
        anime_response = await self.find_mal("anime", name, 15)
        manga_response = await self.find_mal("manga", name, 15)
        if anime_response is None and manga_response is None:
            await ctx.send("Series not found")
            return
        if anime_response is not None:
            for anime in anime_response['results']:
                if name.lower() not in anime['title'].lower():
                    continue
                message += str(anime['mal_id'])
                message += " | "
                message += anime['title']
                message += " (A)"
                message += "\n"
        if manga_response is not None:
            for manga in manga_response['results']:
                if name.lower() not in manga['title'].lower():
                    continue
                message += str(manga['mal_id'])
                message += " | "
                message += manga['title']
                message += " (M)"
                message += "\n"
        embed = discord.Embed(title=f"Lookup: {name}", description=message,
                              color=0x200FB4)
        await ctx.send(embed=embed)

    @command()
    async def series_info(self, ctx: Context, *args: str):
        args = list(args)
        if args[-1].startswith('-m'):
            is_anime = False
            del args[-1]
        else:
            is_anime = True
        if args[0].isdigit():
            response = await self.get_series_characters_by_id("anime", args[0])
            if response is None or not is_anime:
                is_anime = False
                response = await self.get_series_characters_by_id("manga", args[0])
                if response is None:
                    await ctx.send("No series with this id")
                    return
        else:
            name = ' '.join(args)
            series_id = None
            response = await self.find_mal("anime", name, 1)
            if response is None or not is_anime:
                is_anime = False
                response = await self.find_mal("manga", name, 1)
                if response is None:
                    await ctx.send("Series not found")
                    return
            series = response['results'][0]
            series_id = str(series['mal_id'])
            if is_anime:
                response = await self.get_series_characters_by_id("anime", series_id)
            else:
                response = await self.get_series_characters_by_id("manga", series_id)

        message = ""
        counter = 0
        if is_anime:
            footer = "For manga with the same id, use this command with -m at the end.\n"
        else:
            footer = ""
        for character in response['characters']:
            if counter == 30:
                footer += f"{len(response['characters']) - counter} characters omitted."
                break
            message += str(character['mal_id'])
            message += " | "
            character_name = character['name'].split(', ')
            character_name.reverse()
            character_name = ' '.join(character_name)
            message += character_name
            message += "\n"
            counter += 1
        embed = discord.Embed(title=response['title'], description=message,
                              color=0x200FB4)
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)

    async def random_waifu(self, channel):
        DEFAULT_IMAGE_URL = "https://cdn.myanimelist.net/img/sp/icon/apple-touch-icon-256.png"

        if random.randint(0, 99) < 30:
            comicvine = True
        else:
            comicvine = False
        if waifu_manager.current_waifu_spawn is not None:
            if timers.get_time() - timers.get_waifu_claim_timer() < WAIFU_CLAIM_DELTA:
                return
            await waifu_manager.skip_waifu()
            claim_message = waifu_manager.claim_message
            old_embed = claim_message.embeds[0]
            desc = old_embed.description
            desc += "\nClaimed by nobody. So sad."
            embed = discord.Embed(title=old_embed.title,
                                  description=desc, color=old_embed.color)
            await claim_message.edit(embed=embed)
        if waifu_manager.is_prepared:
            response = waifu_manager.spawn_waifu()
            message = await channel.send(embed=response)
            waifu_manager.set_claim_message(message)
            timers.set_waifu_claim_timer()
        while True:
            if comicvine:
                response = await self.get_random_comic_char()
                if response is not None:
                    if not response['results'][0]['image']['medium_url'].endswith('blank.png'):
                        waifu_manager.prepare_comic_spawn(response)
                        return
            else:
                char_id = random.randint(1, 99999)
                response = await self.get_waifu_by_id(char_id)
                if response is not None:
                    if response['image_url'] != DEFAULT_IMAGE_URL and\
                            response['member_favorites'] >= 5:
                        pictures = await self.get_mal_waifu_pics(response['mal_id'])
                        waifu_manager.prepare_waifu_spawn(response, pictures['pictures'])
                        return
                await asyncio.sleep(3)

    async def get_waifu_by_id(self, mal_id):
        session = http_session.get_connection()
        async with session.get(API_URL + "character/{}".format(mal_id)) as resp:
            response = await resp.json()
        error = response.get('error', None)
        if error is not None:
            return None
        return response
    
    async def get_mal_waifu_pics(self, mal_id):
        session = http_session.get_connection()
        async with session.get(
                API_URL + f"character/{mal_id}/pictures") as resp:
            pictures = await resp.json()
        return pictures

    async def get_random_comic_char(self):
        global COMICVINE_TOTAL_CHARS
        session = http_session.get_connection()
        params = {
            'api_key': COMICVINE_API_KEY,
            'format': 'json',
            'limit': 1,
            'offset': random.randint(0, COMICVINE_TOTAL_CHARS)
        }
        async with session.get(COMICVINE_URL + "characters", params=params) as resp:
            response = await resp.json()
        if response['error'] != "OK":
            return None
        COMICVINE_TOTAL_CHARS = int(response['number_of_total_results'])
        return response

    async def get_series_characters_by_id(self, kind, mal_id):
        session = http_session.get_connection()
        if kind == "anime":
            async with session.get(API_URL + f"{kind}/{mal_id}/characters_staff") as resp:
                response = await resp.json()
            async with session.get(API_URL + "{}/{}".format(kind, mal_id)) as resp:
                anime = await resp.json()
            response['title'] = anime.get('title', "") + " (A)"
        else:
            async with session.get(API_URL + "{}/{}/characters".format(kind, mal_id)) as resp:
                response = await resp.json()
            async with session.get(API_URL + "{}/{}".format(kind, mal_id)) as resp:
                manga = await resp.json()
            response['title'] = manga.get('title', "") + " (M)"

        error = response.get('error', None)
        if error is not None:
            return None
        return response

    @command()
    async def spawn(self, ctx: Context):
        await self.random_waifu(ctx.message.channel)

    @command()
    async def claim(self, ctx: Context, *args: str):
        if waifu_manager.current_waifu_spawn is None:
            await ctx.send("No active waifu spawn, what a shame.")
            return
        name = ' '.join(args)
        if self.is_correct_name(name, waifu_manager.current_waifu_spawn.name):
            await ctx.send(
                f"You got it, {ctx.message.author.mention}! (But not really yet.)")
            waifu_manager.waifu_claimed(str(ctx.message.author.id))
            claim_message = waifu_manager.claim_message
            old_embed = claim_message.embeds[0]
            author = ctx.message.author
            description = f"{old_embed.description}\n**Claimed by {author.name}**"
            embed = discord.Embed(title=old_embed.title, description=description,
                                  color=old_embed.color)
            embed._image = {
                'url': old_embed.image.url
            }
            await claim_message.edit(embed=embed)
        else:
            result = await self.calculate_similarity(
                name, waifu_manager.current_waifu_spawn.name)
            if result > 5:
                await ctx.message.add_reaction('❌')
            else:
                await ctx.send(
                    "You were off by {} letter{}.".format(result, 's' if result > 1 else ''))

    def is_correct_name(self, guess, target):
        guess = guess.lower()
        guess = guess.strip()
        target = target.lower()
        target = target.strip()
        guess = guess.split(' ')
        target = target.split(' ')
        for word in target:
            if word not in guess:
                word = unicodedata.normalize('NFKD', word).encode('ascii', 'ignore')
                word = word.decode('ascii')
                if word not in guess:
                    return False
        return True

    async def calculate_similarity(self, guess, target):
        guess = guess.lower()
        guess = guess.strip()
        guess = guess.split(' ')
        target = target.lower()
        target = target.strip()
        target = target.split(' ')
        if len(target) != len(guess):
            return 99
        target_perms = [' '.join(x) for x in itertools.permutations(target)]
        min_result = 6
        for perm in target_perms:
            perm = perm.split(' ')
            result = 0
            groups = self.split_into_groups(list(itertools.product(perm, guess)), len(perm))
            for gr in groups:
                min_group_result = 99999
                for words in gr:
                    if words[0][0] != words[1][0]:
                        continue
                    mid_result = await self.calculate_word_similarity(words[1], words[0])
                    if mid_result < min_group_result:
                        min_group_result = mid_result
                result += min_group_result
            if result < min_result:
                min_result = result
        return min_result

    def split_into_groups(self, perms, num_of_words):
        result = [[] for x in range(len(perms) // num_of_words)]
        j = 0
        for i in range(len(perms)):
            if i != 0 and (i % num_of_words) == 0:
                j += 1
            result[j].append(perms[i])
        return result

    async def calculate_word_similarity(self, guess, target):
        if guess == target:
            return 0
        matches = SequenceMatcher(None, guess, target).get_matching_blocks()
        size = 0
        for match in matches:
            size += match.size
        extra_letters = len(guess) - size
        return (len(target) - size) + extra_letters

    @command(name='list')
    async def waifu_list(self, ctx: Context, *args):
        page = 1
        content = ctx.message.content
        filters = None
        if "-name" in content:
            i = content.index("-name")
            i += 6
            filters = {
                "name": content[i:]
            }
        elif "-favorite" in content:
            i = content.index("-favorite")
            i += 10
            if content[i:] == "":
                filters = {
                    "favorite": True
                }
            else:
                filters = {
                    "favorite": True,
                    "emoji": content[i:]
                }
        else:
            try:
                page = int(args[0])
            except IndexError:
                page = 1
        if page < 1:
            return
        author = ctx.message.author
        embed = await waifu_manager.get_player_waifus(str(author.id), author.name, page, filters)
        if embed is None:
            await ctx.send("No waifus, that's pretty sad.")
            return
        await ctx.send(embed=embed)

    @command()
    async def schedule(self, ctx: Context, day: str):
        day = day.lower()
        session = http_session.get_connection()
        async with session.get(API_URL + "schedule/{}".format(day)) as resp:
            response = await resp.json()
        embed = discord.Embed(title=day.capitalize(), color=0x09D3E3)
        for anime in response[day]:
            desc = ""
            episodes = "N/A" if anime.get('episodes', None) is None else str(anime['episodes'])
            desc += "**Episodes**: " + episodes
            desc += "\n"
            desc += "**Genres:** "
            for genre in anime['genres']:
                desc += "*{}* ".format(genre['name'])
            desc += "\n"
            desc += "Score: " + str(anime['score'])
            desc += "\n"
            desc += "Source: " + anime['source']
            embed.add_field(name="**" + anime['title'] + "**", value=desc, inline=False)
        await ctx.send(embed=embed)

    @command()
    async def view(self, ctx: Context, list_id: int):
        author = ctx.message.author
        waifu = await waifu_manager.get_player_waifu(str(author.id), list_id)
        if waifu is None:
            await ctx.send(f"No waifu with id {list_id}.")
            return
        waifu_data = await self.get_waifu_by_id(waifu.mal_id)
        desc = "More info soon"
        embed = discord.Embed(title=waifu.name, description=desc, color=0x200FB4)
        embed._image = {
            'url': waifu_data['image_url']
        }
        await ctx.send(embed=embed)
    
    @command()
    async def remove(self, ctx: Context, list_id: int):
        author = ctx.message.author
        waifu = await waifu_manager.get_player_waifu(str(author.id), list_id)
        if waifu is None:
            await ctx.send(f"No waifu with id {list_id}")
            return
        await ctx.send(f"Are you sure you want to remove {waifu.name} from your waifus? (yes or no)")

        def check_removal_confirmation(msg):
            return msg.content.lower() == "yes" or msg.content.lower() == "no"\
                and msg.author.id == author.id\
                and msg.channel.id == ctx.message.channel.id
        
        try:
            msg = await self.bot.wait_for('message', check=check_removal_confirmation, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send("Waited too long for confirmation, aborting.")
            return
        
        if msg.content.lower() == "yes":
            await waifu_manager.remove_waifu_from_player(str(author.id), list_id)
            await ctx.send(f"Successfully removed {waifu.name} from your waifus.")
        else:
            await ctx.send("Cancelled removal.")
    
    @group(aliases=['t'])
    async def trade(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use ?help trade to see available trading commands.")
    
    @trade.command(name="start", aliases=['s'])
    async def trade_start(self, ctx: Context, member: discord.Member):
        """Start trading with another user."""
        author = ctx.message.author
        if author.id == member.id:
            await ctx.send("You can't trade with yourself, dummy.")
            return
        if member.bot:
            await ctx.send("Can't trade with bots, mate.")
            return
        if author.id in self.current_trades or author.id in self.waiting_to_trade:
            await ctx.send("You're already trading with someone.")
            return
        if member.id in self.current_trades or member.id in self.waiting_to_trade:
            await ctx.send("They're already trading with someone.")
            return
        self.waiting_to_trade.append(author.id)
        self.waiting_to_trade.append(member.id)
        await ctx.send(f"{member.mention}, {author.mention} wants to trade with you. " +
                       "Say 'yes' to accept, 'no' to decline.")

        def check_trade_message(msg):
            return msg.content.lower() == "yes" or msg.content.lower() == "no"\
                and msg.author.id == member.id\
                and msg.channel.id == ctx.message.channel.id

        try:
            msg = await self.bot.wait_for('message', check=check_trade_message, timeout=120)
        except asyncio.TimeoutError:
            self.waiting_to_trade.remove(author.id)
            self.waiting_to_trade.remove(member.id)
            await ctx.send(f"{author.mention}, it seems that {member.mention} is asleep.")
            return           
        self.waiting_to_trade.remove(author.id)
        self.waiting_to_trade.remove(member.id)
        if msg.content.lower() == "no":
            await ctx.send(
                f"{member.name} doesn't want to trade with you, {author.mention}. " +
                "Too bad.")
            return
        
        trade = WaifuTrade(author, member)
        self.current_trades[author.id] = trade
        self.current_trades[member.id] = trade
        embed = discord.Embed(title="Trade", color=0x0934e3)
        embed.add_field(name=f"{author.name}'s offer:", value="Nothing.", inline=False)
        embed.add_field(name=f"{member.name}'s offer:", value="Nothing.", inline=False)
        embed_msg = await ctx.send(embed=embed)
        trade.set_embed_msg(embed_msg)
    
    @trade.command(name="cancel", aliases=['cl'])
    async def trade_cancel(self, ctx: Context):
        """Cancel your current trade."""
        author = ctx.message.author
        if author.id not in self.current_trades:
            await ctx.send("No active trade to cancel.")
            return
        trade = self.current_trades[author.id]
        member = trade.t2_member if author.id != trade.t2_member.id else trade.t1_member
        embed_msg = trade.get_embed_msg()
        await embed_msg.delete()
        del self.current_trades[author.id]
        del self.current_trades[member.id]
        await ctx.send("Cancelled trade.")
    
    @trade.command(name="add", aliases=['a'])
    async def trade_add_offer(self, ctx: Context, list_id: int):
        """Add a waifu offer to your trade."""
        author = ctx.message.author
        if author.id not in self.current_trades:
            await ctx.send("You're not trading with anyone right now.")
            return
        waifu = await waifu_manager.get_player_waifu(str(author.id), list_id)
        if waifu is None:
            await ctx.send(f"No waifu with id {list_id}.")
            return
        trade = self.current_trades[author.id]
        embed_msg = trade.get_embed_msg()
        embed = embed_msg.embeds[0]
        if trade.t1_member.id == author.id:
            trade.set_t1_offer(waifu)
            trade.set_t1_list_id(list_id)
            embed.set_field_at(0, name=f"{author.name}'s offer:", value=f"{waifu.name}", inline=False)
        else:
            trade.set_t2_offer(waifu)
            trade.set_t2_list_id(list_id)
            embed.set_field_at(1, name=f"{author.name}'s offer:", value=f"{waifu.name}", inline=False)
        await embed_msg.edit(embed=embed)
    
    @trade.command(name="remove", aliases=['r'])
    async def trade_remove_offer(self, ctx: Context):
        """Remove an offer from your trade."""
        author = ctx.message.author
        if author.id not in self.current_trades:
            await ctx.send("You're not trading with anyone right now.")
            return
        trade = self.current_trades[author.id]
        embed_msg = trade.get_embed_msg()
        embed = embed_msg.embeds[0]
        if trade.t1_member.id == author.id:
            if trade.t1_offer is None:
                await ctx.send("No offer to remove.")
                return
            trade.set_t1_offer(None)
            trade.set_t1_list_id(None)
            trade.t1_confirmed = False
            prev_field = embed.fields[0]
            embed.set_field_at(0, name=f"{prev_field.name}", value="Nothing.", inline=prev_field.inline)
        else:
            if trade.t2_offer is None:
                await ctx.send("No offer to remove.")
                return
            trade.set_t2_offer(None)
            trade.set_t2_list_id(None)
            trade.t2_confirmed = False
            prev_field = embed.fields[1]
            embed.set_field_at(1, name=f"{prev_field.name}", value="Nothing.", inline=prev_field.inline)
        await embed_msg.edit(embed=embed)
    
    @trade.command(name="confirm", aliases=['c'])
    async def trade_confirm(self, ctx: Context):
        """Confirm your trade."""
        author = ctx.message.author
        if author.id not in self.current_trades:
            await ctx.send("You're not trading with anyone right now.")
            return
        trade = self.current_trades[author.id]
        embed_msg = trade.get_embed_msg()
        embed = embed_msg.embeds[0]
        if trade.t1_member.id == author.id:
            trade.t1_confirmed = True
            prev_field = embed.fields[0]
            embed.set_field_at(0, name=f"{prev_field.name} ✅", value=prev_field.value, inline=prev_field.inline)
        else:
            trade.t2_confirmed = True
            prev_field = embed.fields[1]
            embed.set_field_at(1, name=f"{prev_field.name} ✅", value=prev_field.value, inline=prev_field.inline)
        await embed_msg.edit(embed=embed)
        if trade.t1_confirmed and trade.t2_confirmed:
            await self.finalize_trade(trade)
            await ctx.send(f"Finalized trade between {trade.t1_member.mention} and {trade.t2_member.mention}.")
    
    async def finalize_trade(self, trade):
        t1_member = trade.t1_member
        t2_member = trade.t2_member
        await waifu_manager.trade_waifus(str(t1_member.id), trade.t1_list_id, str(t2_member.id), trade.t2_list_id)
        del self.current_trades[t1_member.id]
        del self.current_trades[t2_member.id]

    @command()
    async def list_gist(self, ctx: Context, flag: str = None):
        author = ctx.message.author
        waifus = await waifu_manager.get_player_waifus_raw(str(author.id))
        if waifus is None:
            await ctx.send("No waifus, that's pretty sad.")
            return
        gist_id = waifu_manager.get_player_gist(str(author.id))
        msg = ""
        if gist_id is not None:
            if flag == "-update":
                await self.update_gist(ctx, gist_id, waifus)
                return
            response = await github_api.get_gist(gist_id)
            updated_at = response['updated_at'].replace('T', ' ').replace('Z', '')
            msg = f"Found your gist, last updated {updated_at}\n"
            msg += response['html_url']
        else:
            body = ""
            for waifu in waifus:
                body += f"{waifu.name} ({waifu.mal_id})\n"
            title = author.nick if author.nick is not None else author.name
            title += "'s waifus"
            response = await github_api.create_gist(title, body)
            new_gist_id = response['id']
            waifu_manager.update_player_gist(str(author.id), new_gist_id)
            msg = "Created new gist.\n"
            msg += response['html_url']
        await ctx.send(msg)
    
    async def update_gist(self, ctx: Context, gist_id: str, waifus):
        body = ""
        for waifu in waifus:
            body += f"{waifu.name} ({waifu.mal_id})\n"
        response = await github_api.update_gist(gist_id, body)
        msg = "Updated your gist.\n"
        msg += response['html_url']
        await ctx.send(msg)
    
    @command()
    async def favorite(self, ctx: Context, list_id: int, emoji: str = None):
        author = ctx.message.author
        waifu = await waifu_manager.get_player_waifu(str(author.id), list_id)
        if waifu is None:
            await ctx.send(f"No waifu with id {list_id}")
            return
        if emoji is None:
            if waifu.is_favorite:
                await waifu_manager.unfavorite_waifu(str(author.id), list_id)
                await ctx.send(f"Successfully removed {waifu.name} from favorites.")
                return
            else:
                emoji = "❤"
        try:
            emoji_code = ord(emoji)
        except TypeError:
            await ctx.send("Server specific emoji not supported yet, blame dad's laziness.")
            return
        await waifu_manager.set_waifu_as_favorite(str(author.id), list_id, emoji_code)
        await ctx.send(f"Set {waifu.name} as favorite under {emoji} emoji.")


class WaifuTrade:

    def __init__(self, t1_member, t2_member):
        self.t1_member = t1_member
        self.t2_member = t2_member
        self.embed_msg = None
        self.t1_confirmed = False
        self.t2_confirmed = False
        self.t1_offer = None
        self.t2_offer = None
        self.t1_list_id = None
        self.t2_list_id = None
    
    def set_embed_msg(self, embed_msg):
        self.embed_msg = embed_msg

    def get_embed_msg(self):
        return self.embed_msg
    
    def set_t1_offer(self, offer):
        self.t1_offer = offer
    
    def set_t2_offer(self, offer):
        self.t2_offer = offer
    
    def set_t1_list_id(self, list_id):
        self.t1_list_id = list_id
    
    def set_t2_list_id(self, list_id):
        self.t2_list_id = list_id


def setup(bot: MyBot):
    cog = WaifuCommands(bot)
    bot.add_cog(cog)
