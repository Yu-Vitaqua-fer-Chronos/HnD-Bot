from collections import UserDict
from time import sleep
from math import ceil
from os import environ
from json import loads
import re

import d20
from ruamel.yaml import YAML
from hata import KOKORO, Client, Guild
from hata.ext import asyncio
from gspread import SpreadsheetNotFound
from gspread.utils import fill_gaps, a1_to_rowcol
from gspread.exceptions import APIError
import gspread_asyncio as gspread
from google.oauth2.service_account import Credentials

yaml = YAML()
POS_RE = re.compile(r"([A-Z]+)(\d+)")
client = Client(environ['TOKEN'], extensions=('slash'))
guilds = (Guild.precreate(902668029115138078),)

def get_creds():
    creds = Credentials.from_service_account_info(loads(environ.get('CREDENTIALS_JSON')))
    scoped = creds.with_scopes([
      "https://spreadsheets.google.com/feeds",
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive",
    ])
    return scoped

agcm = gspread.AsyncioGspreadClientManager(get_creds)

def letter2num(letters, zbase=True):
    """A = 1, C = 3 and so on. Convert spreadsheet style column
    enumeration to a number.
    """

    letters = letters.upper()
    res = 0
    weight = len(letters) - 1
    for i, ch in enumerate(letters):
        res += (ord(ch) - 64) * 26 ** (weight - i)
    if not zbase:
        return res
    return res - 1

class InvalidSheetException(Exception):
    pass

class GSheet(object):
    def __init__(self, worksheet):
        self.worksheet = worksheet

    async def init(self):
        self.values = await self.worksheet.get_all_values()
        self.unformatted_values = await self._get_all_unformatted_values()

    async def _get_all_unformatted_values(self):
        data = self.worksheet.ws.spreadsheet.values_get(
            self.worksheet.title,
            params={'valueRenderOption': "UNFORMATTED_VALUE"})
        try:
            return fill_gaps(data['values'])
        except KeyError:
            return []

    @staticmethod
    def _get_value(source, pos):
        _pos = POS_RE.match(pos)
        if _pos is None:
            raise ValueError("No A1-style position found.")
        col = letter2num(_pos.group(1))
        row = int(_pos.group(2)) - 1
        if row > len(source) or col > len(source[row]):
            raise IndexError("Cell out of bounds.")
        value = source[row][col]
        print(f"Cell {pos}: {value}")
        return value

    def value(self, pos):
        return self._get_value(self.values, pos)

    def unformatted_value(self, pos):
        return self._get_value(self.unformatted_values, pos)

    def value_range(self, rng):
        """Returns a list of values in a range."""
        start, end = rng.split(':')
        (row_offset, column_offset) = a1_to_rowcol(start)
        (last_row, last_column) = a1_to_rowcol(end)

        out = []
        for col in self.values[row_offset - 1:last_row]:
            out.extend(col[column_offset - 1:last_column])
        return out

class Stats(object):
    def __init__(self, fs, bs, data):
        self.fs = fs # Front sheet
        self.bs = bs # Back sheet
        self.data = data # Data sheet

    async def init(self):
        try:
            getattr(self, 'initialized')
        except AttributeError:
            await self.load()
            setattr(self, 'initialized', True)

    async def load(self):
        self.str = int(self.fs.value("F9"))        # Strength
        self.dex = int(self.fs.value("F10"))       # Dexterity
        self.con = int(self.fs.value("F11"))       # Constitution
        self.int = int(self.fs.value("F12"))       # Intelligence
        self.wis = int(self.fs.value("F13"))       # Wisdom
        self.cha = int(self.fs.value("F14"))       # Charisma

        self.ty = int(self.bs.unformatted_value("AR6"))  # Total Yen
        self.tw = int(self.bs.unformatted_value("AR23")) # Total Wealth

        self.str_mod = int(self.data.value("F2"))  # Strength Mod
        self.dex_mod = int(self.data.value("F3"))  # Dexterity Mod
        self.con_mod = int(self.data.value("F4"))  # Constitution Mod
        self.int_mod = int(self.data.value("F5"))  # Intelligence Mod
        self.wis_mod = int(self.data.value("F6"))  # Wisdom Mod
        self.cha_mod = int(self.data.value("F7"))  # Charisma Mod

        self.ce = self.data.value("B16").lower()   # Coin Encumbrance
        if self.ce == 'true':
            self.ce = True
        else:
            self.ce = False

        self.enc = self.bs.value("AE34")           # Total Encumbrance

    def ce_calc(self):
        return ceil(self.ty/1000)

acmap = {'strength':'str', 'dexterity':'dex', 'constitution':'con', 'intelligence':'int', 'wisdom':'wis', 'charisma':'cha'}

class CharSheet(object):
    def __init__(self, url, prnsoverride=None, vrbsoverride=None):
        self.url = url           # Google sheet URL
        self.prnsoverride = None # For overrides since gender != pronouns
        self.vrbsoverride = None
        if prnsoverride:
            self.prnsoverride = prnsoverride.lower().split('/')
        if vrbsoverride:
            self.vrbsoverride = vrbsoverride.lower().split('/')

    def __str__(self): # Just overriding the str function so it looks pretty
        try:
            getattr(self, 'initialized')
            return f"(Initialized)\nSheet URL: {self.url}\nName: {self.name}\nLevel; {self.level}\nGender: {self.gender}"
        except AttributeError:
            return f"(Uninitialized)\nSheet URL: {self.url}"

    def __repr__(self): # Makes it easier to recreate the class
        return f"CharSheet('{self.url}', {('/'.join(self.prnsoverride)).__repr__()}, {str('/'.join(self.vrbsoverride)).__repr__()})"

    async def init(self): # Async init function that initializes the
        try:              # Sheet if it isn't already loaded
            getattr(self, 'initialized')
        except AttributeError:
            await self.load()
            setattr(self, 'initialized', True)

    async def load(self):
        try:
            agc = await agcm.authorize()
            doc = await agc.open_by_url(self.url)
            self.fs = GSheet(await doc.worksheet('Front'))
            self.bs = GSheet(await doc.worksheet('Back'))
            self.data = GSheet(await doc.worksheet('Data'))
            await self.fs.init()
            await self.bs.init()
            await self.data.init()
            self.name = self.fs.value("B1")
            self.size = self.fs.value("B3").lower()
            self.hair = self.fs.value("H3").lower()
            self.eyes = self.fs.value("O3").lower()
            self.race = self.fs.value("T1").lower()
            self.age = int(self.fs.value("AF3"))
            self.height = self.fs.value("U3")
            self.weight = self.fs.value("AA3")
            self.level = int(self.fs.value("P1"))

            self.gender = self.fs.value("AB1").lower()
            self.verbs = ("is", "has")
            if self.prnsoverride:
                self.prns = self.prnsoverride
            elif self.gender == "male" :
                self.prns = ("he", "him", "himself")
            elif self.gender == "female":
                self.prns = ("she", "her", "herself")
            else:
                self.prns = ("they", "them", "themselves")
                self.verbs = ("are", "have")
            if self.vrbsoverride:
                self.verbs = self.vrbsoverride

            self.desc = f"{self.name} {self.verbs[0]} a {self.age} year old {self.gender} level {self.level} {self.race}. {self.prns[0].capitalize()} {self.verbs[0]} {self.height} and weighs {self.weight}. {self.prns[0].capitalize()} also {self.verbs[1]} {self.hair} hair and {self.eyes} eyes."

            self.image = self.fs.value("BC8").strip()

            self.fpm = int(self.fs.value("AV12")) # How many feet they can move
            self.spm = self.fpm / 5 # How many squares can be moved per turn

            self.stats = Stats(self.fs, self.bs, self.data)
            await self.stats.init()
        except (KeyError, SpreadsheetNotFound, APIError):
            raise InvalidSheetException(f"The sheet URL `{self.url}` is invalid! Make sure you've shared it with me at `hndbot@heroes-and-dragons-bot.iam.gserviceaccount.com` and that you double check it! (If it has /copy or /edit at the end, remove that!)")

    def roll(self, dice, mod=0):
        if isinstance(mod, str):
            try:
                mod = getattr(self.stats, acmap.get(mod.lower())+'_mod')
            except (AttributeError, TypeError):
                mod = 0
        return d20.roll(dice).total + mod

class DMSheet(object):
    def __init__(self, url): # Might as well make it easy to change
        self.url = url

    async def init(self):
        try: # Initialise sheet if it isn't already loaded
            getattr(self, 'initialized')
        except AttributeError:
            await self.reload()
            setattr(self, 'initialized', True)

    async def reload(self):
        agc = await agcm.authorize()
        doc = await agc.open_by_url(self.url)
        self.md = GSheet(await doc.worksheet('MonsterDex')) # MonsterDex sheet
        await self.md.init()
        MONSTERS = self.md.value_range("A2:A322")
        self.MONSTER_LIST = [MONSTER.title() for MONSTER in MONSTERS]
        self.monsters = dict(zip(self.MONSTER_LIST, self.md.value_range("B2:B322"))) # Zip the values together into an easy to lookup dict


dmsheet = DMSheet(environ['DM_SHEET'])

yaml.register_class(CharSheet)

class Data(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = False
        with open('userdata.yaml') as f:
            tmp = yaml.load(f)
            if tmp:
                self.data.update(tmp)
        self.counter = 0

    def __setitem__(self, key, value):
        self.counter += 1
        super().__setitem__(key, value)
        if self.counter >= 5:
            while self.lock:
                pass
            self.lock = True
            with open('userdata.yaml', 'w+') as f:
                yaml.dump(self.data, f)
            self.counter = 0
            self.lock = False

    def force_save(self):
        while self.lock:
            pass
        self.lock = True
        with open('userdata.yaml', 'w+') as f:
            yaml.dump(self.data, f)
        self.counter = 0
        self.lock = False

    def new_sheet(self, url, acc, prnsoverride=None, vrbsoverride=None):
        if self.get(acc):
            return False
        self[acc] = CharSheet(url, prnsoverride, vrbsoverride)
        self.force_save()
        return True


data = Data()

@client.events
async def ready(client):
    await dmsheet.init()
    print(f"`{client:f}` is ready.")

@client.interactions(guild=guilds)
async def ping():
    """Test ping command"""
    yield 'pong'

@client.interactions(guild=guilds)
async def link(event, sheet_url:str, prnsoverride:str=None, vrbsoverride:str=None):
    """Links a gsheet to your account. Add pronouns and verbs with format `he/him/himself`, and `is/has`."""
    try:
        sheet = data.new_sheet(sheet_url, event.user.id, prnsoverride, vrbsoverride)
        if sheet:
            yield "Verifying sheet..."
            await data.get(event.user.id).init()
            yield "Google sheet successfully linked!"
            return
        yield "You already linked a sheet to your account!"
        return
    except InvalidSheetException as e:
        del data[event.user.id]
        yield e

@client.interactions(guild=guilds)
async def unlink(event):
    """Unlinks a linked character sheet from your account."""
    sheet = data.get(event.user.id)
    if sheet:
        del data[event.user.id]
        yield "Successfully unlinked character sheet."
        return
    yield "No character sheet linked! If you'd like to link a new one, use the <`link`> command!"

@client.interactions(guild=guilds)
async def char_desc(event):
    """The brief description of your character generated by the bot."""
    sheet = data.get(event.user.id)
    if not sheet:
        yield "No character sheet linked! Link a character sheet with the command!"
        return
    yield
    await sheet.init()
    yield sheet.desc

BASE_STATS = (
  "Undefined",
  "Strength",
  "Dexterity",
  "Constitution",
  "Intelligence",
  "Wisdom",
  "Charisma"
)

ROLLABLE_STATS = [
  *BASE_STATS,
]

@client.interactions(guild=guilds)
async def roll(event, dice:('str', 'Use a format like `1d6` to roll 1 6-sided die'), stat:('str', 'Choose a value from the list!')="Undefined", mod:('str', 'Add a base to the stat')=0):
    """Roll dice!"""
    sheet = data.get(event.user.id)
    if not sheet:
        yield "No character sheet linked! Link a character sheet with the link command!"
        return
    dice = dice.lower()
    stat = stat.title()
    yield
    await sheet.init()
    if stat == 'undefined':
        yield f"Rolled a {sheet.roll(dice)}"
    elif not stat and mod:
        yield f"Rolled a {sheet.roll(dice, mod=mod)} with the {mod} modifier"
    elif stat and not mod:
        yield f"Rolled a {sheet.roll(dice)} for {stat}"
    else:
        yield f"Rolled a {sheet.roll(dice, mod)} for {stat} with the {mod} modifier"

@roll.autocomplete('stat')
async def stat_autocomplete(value):
    if value is None:
        return ROLLABLE_STATS
    return [ROLLABLE_STAT for ROLLABLE_STAT in ROLLABLE_STATS if value.title() in ROLLABLE_STAT]

@roll.autocomplete('mod')
async def modifier_autocomplete(value):
    if value is None:
        return BASE_STATS
    return [BASE_STAT for BASE_STAT in BASE_STATS if value.title() in BASE_STAT]

@client.interactions(guild=guilds)
async def monster_dex(event, monster:str):
    """Use the MonsterDex to look through monsters in the campaign!"""
    yield
    await dmsheet.init()
    m = dmsheet.monsters.get(monster.title())
    if not m:
        yield f"`{monster}` isn't a valid monster! Choose one from the list!"
        return
    yield f"```yaml\n{m}```"

@monster_dex.autocomplete('monster')
async def monster_autocomplete(value):
    if value is None:
        return dmsheet.MONSTER_LIST
    return [MONSTER for MONSTER in dmsheet.MONSTER_LIST if value.title() in MONSTER]

@client.interactions(guild=guilds)
async def reload_dm_sheet():
    """This command reloads the DM sheet"""
    yield "Reloading DM sheet..."
    await dmsheet.reload()
    yield "DM sheet reloaded!"

@client.interactions(guild=guilds)
async def debug():
    """Prints the raw output of data"""
    yield f"```yaml\n{data.data}```"

client.start()