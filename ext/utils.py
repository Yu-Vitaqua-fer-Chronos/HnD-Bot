from collections import UserDict
from types import SimpleNamespace as SN # Abbreviation for convinience
from time import sleep
from math import ceil
from os import environ
from json import loads
import re

import d20
from ruamel.yaml import YAML
from gspread import SpreadsheetNotFound
from gspread.utils import fill_gaps, a1_to_rowcol
from gspread.exceptions import APIError
import gspread_asyncio as gspread
from google.oauth2.service_account import Credentials

yaml = YAML(typ='unsafe')
yaml.register_class(SN)
POS_RE = re.compile(r"([A-Z]+)(\d+)")

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


class Size: # Encumbrance calc
    tiny = 0.5
    small = 1
    medium = 1
    large = 2
    huge = 4
    gargantuan = 8


class GSheet(object): # GSheet implementation to easily access values
    def __init__(self, worksheet):
        self.worksheet = worksheet

    async def init(self): # Due to it being an async function it can't be called without an await, so make sure it's called once before trying to do anything
        self.values = await self.worksheet.get_all_values()
        self.unformatted_values = await self._get_all_unformatted_values()

    async def _get_all_unformatted_values(self): # Grab all of the unformatted values from the sheet
        data = self.worksheet.ws.spreadsheet.values_get(
            self.worksheet.title,
            params={'valueRenderOption': "UNFORMATTED_VALUE"})
        try:
            return fill_gaps(data['values'])
        except KeyError:
            return []

    @staticmethod
    def _get_value(source, pos): # Any function prefixed with _ is not meant to be used by the user using the class, and it's mainly for internal program use
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

    def value(self, pos): # Grab the formatted value from the sheet
        return self._get_value(self.values, pos)

    def unformatted_value(self, pos): # Grab the unformatted value from the sheet
        return self._get_value(self.unformatted_values, pos)

    def value_range(self, rng):
        """Returns a list of values in a range.""" # Triple speech marks indicate a docstring/multiline string
    #they help users going through the code to understand it, but normal comments like this are also good
        start, end = rng.split(':')
        (row_offset, column_offset) = a1_to_rowcol(start)
        (last_row, last_column) = a1_to_rowcol(end)

        out = []
        for col in self.values[row_offset - 1:last_row]:
            out.extend(col[column_offset - 1:last_column])
        return out


class SpreadsheetStats(object): # This just loads the stats for the sheet, in a way that is formatted nice. It isn't needed but makes it nicer to use and write
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

    async def load(self): # Loads the sheet data and adds it into the class namespace (self)
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

        self.ce = self.data.value("B16").lower()   # Indicates if coin encumbrance is on
        if self.ce == 'true': # Sets it as a boolean
            self.ce = True
        else:
            self.ce = False

acmap = {'strength':'str', 'dexterity':'dex', 'constitution':'con', 'intelligence':'int', 'wisdom':'wis', 'charisma':'cha'} # Just maps the values to a dict that it is easily accessed

class CharSpreadsheet(object):
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

    def __repr__(self): # Makes it easier to recreate the class when printing it out
        return f"CharSpreadsheet('{self.url}', {('/'.join(self.prnsoverride)).__repr__()}, {str('/'.join(self.vrbsoverride)).__repr__()})"

    async def init(self): # Async init function that initializes the
        try:              # Sheet if it isn't already loaded
            getattr(self, 'initialized')
        except AttributeError:
            await self.load()
            setattr(self, 'initialized', True)

    async def load(self):
        try:
            agc = await agcm.authorize() # Authorise the google key when accessing the sheet, should be made once every time you plan to access the sheet
            doc = await agc.open_by_url(self.url) # Opens the doc from the sheet
            self.fs = GSheet(await doc.worksheet('Front'))
            self.bs = GSheet(await doc.worksheet('Back'))
            self.data = GSheet(await doc.worksheet('Data'))
            await self.fs.init()
            await self.bs.init()
            await self.data.init()
            self.name = self.fs.value("B1").title()
            self.size = self.fs.value("B3").lower()
            self.hair = self.fs.value("H3").lower()
            self.eyes = self.fs.value("O3").lower()
            self.race = self.fs.value("T1").title()
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

            self.image = self.fs.value("BC8").strip()

            self.fpm = int(self.fs.value("AV12")) # How many feet they can move
            self.spm = self.fpm / 5 #    How many squares can be moved per turn, since 5 feet is 1 square

            self.stats = SpreadsheetStats(self.fs, self.bs, self.data)
            await self.stats.init()
        except (KeyError, SpreadsheetNotFound, APIError):
            raise InvalidSheetException(f"The sheet URL `{self.url}` is invalid! Make sure you've shared it with me at `hndbot@heroes-and-dragons-bot.iam.gserviceaccount.com` and that you double check it! (If it has /copy or /edit at the end, remove that!)")


class DMSheet(object):
    def __init__(self, url): # Might as well make it easy to change if the DM sheet has a new URL
        self.url = url

    async def init(self):
        try: # Initialise sheet if it isn't already loaded
            getattr(self, 'initialized')
        except AttributeError:
            await self.reload()
            setattr(self, 'initialized', True)

    async def reload(self):
        agc = await agcm.authorize() # Authorise with the Google API before accessing
        doc = await agc.open_by_url(self.url)
        self.fs = GSheet(await doc.worksheet('General DM Sheet'))
        self.md = GSheet(await doc.worksheet('MonsterDex')) # MonsterDex sheet, allows the DM to easily add and remove monsters so they can be looked up via the bot
        await self.fs.init()
        await self.md.init()
        MONSTERS = self.md.value_range("A2:A322")
        self.MONSTER_LIST = [MONSTER.title() for MONSTER in MONSTERS]
        self.monsters = dict(zip(self.MONSTER_LIST, self.md.value_range("B2:B322"))) # Zip the values together into an easy to lookup dict


def roll(u, dice, mod): # Rolls the dice, u is the character the dice is rolling on, dice is the dice in the format `1d6` or `3d20`
    if isinstance(mod, str): # Check if the modifier is a string, if so, use acmap to look up the modifier value
        try:
            mod = getattr(u.stats.base, acmap.get(mod.lower())+'_mod')
        except (AttributeError, TypeError):
            mod = False   # You can perform operations on booleans, False is equal to 0 in Python
    return (d20.roll(dice).total, mod) # Returns a python tuple (like a list that can't have new values added or existing ones deleted)


class ClashingPropertyError(Exception): # Define a few exceptions to be raised
    pass


class InvalidTargetError(Exception):
    pass


class InventoryFullError(Exception):
    pass


class ItemProperties(object): # The properties an item has
    def __init__(self, dice=None, damage=False, heal=False, non_self=False, on_self=False):
        if damage and heal:
            raise ClashingPropertyError("Items can't damage and heal! Make up your mind!")
        self.dice = dice
        self.damage = damage
        self.heal = heal
        self.ns = non_self
        self.os = on_self


class Item(object):
    def __init__(self, name, weight=1, props=None): # Weight is weight per object, in lbs
        self.name = name
        self.weight = weight # Weight just means encumberance
        self.props = props # Make it props so it's quicker to type
        self.amount = 1

    def use(self, user, dice, target=None, mod=0):
        if not target:
            target = user
        if not self.props:
            raise ItemNotUsable(f"`{self.name}` can't be used as it has no properties by itself!") # If props is None, then say that the item isn't usable directly. Items like this tend to be RP items more then anything
        if user == target and not self.props.os: # Checks if you can use it on yourself when someone is trying to do that
            raise InvalidTargetError(f"`{self.name}` can't be used on yourself!")
        if user != target and not self.props.ns: # Checks if you're trying to use it on someone else but you can't do that
            raise InvalidTargetError(f"`{self.name}` can't be used on other people!")
        result = roll(user, dice, mod)
        if self.props.damage:
            target.health - (result[0][0] + result[0][1])
            return (result, "D")
        elif self.props.heal:
            target.health + (result[0][0] + result[0][1])
            return (result, "H") # H for heal

    @property
    def total_weight(self):
        return self.weight * amount


class Arrow(Item):
    def __init___(self, name, weight=0.05): # Arrow weighs 0.05 lbs on it's own
        self.name = name
        self.weight = weight
        self.props = ItemProperties("1d4-4", True, False, True, False)
        self.amount = 1


class PreciousMaterial(Item):
    def __init__(self, name, value): # A type of item specifically for gems, etc
        self.name = name
        self.weight = 0 # Negligible
        self.value = value
        self.props = ItemProperties("0", False, False, False, False)
        self.amount = 1


class Inventory(object):
    def __init__(self, limiter, weight=0, type=Item):
        self.limiter = limiter # Value for how many items can be in the inventory
        self.weight = weight # Some inventories have a weight themselves
        self.type = type # The type of items the inventory accepts
        self.inv = [] # A list of items to just store it

    @property
    def inv_e(self):
        result = self.weight
        for item in self.inv:
            result += item.total_weight
        return result

    def add(self, item):
        if len(self.inv) + 1 > self.limiter:
            raise InventoryFullError("Inventory is full! Can't hold anymore items! Clear up your bag or maybe use a different inventory?")
        self.inv.append(item)
        return len(self.inv)


class Character(object):
    def __init__(self, name, race, eyes, hair, age, gender, verbs, pronouns, height, weight, level, fpm, yen, base, mods):
        # Player desc stuff
        self.name = name
        self.race = race
        self.eyes = eyes
        self.hair = hair
        self.age = age
        self.gender = gender
        self.verbs = verbs.lower().split('/')
        self.pronouns = pronouns.lower().split('/')
        self.height = height
        self.weight = weight
        self.level = level
        self.yen = yen

        # Player stats
        self.stats = SN(base=base, mods=mods)
        self.fpm = fpm

        # Inventory stuff
        self.body_inv = Inventory(9)
        self.belt_pouch = Inventory(12, 1)
        self.quiver = Inventory(6, 1, Arrow)
        self.backpack = Inventory(6, 5)
        self.bag_of_holding = Inventory(0, 15)
        self.bpa = False # Player doesn't have a backpack either
        self.boha = False # Player doesn't have bag of holding yet so don't give them access to it
        self.gems = Inventory(6)
        self.valuables = Inventory(7)

    @staticmethod # Not a class method and should really only be called externally
    async def import_from_url(url, prns, vrbs): # Asynchronous so it can use asynchronous functions
        sheet = CharSpreadsheet(url, prns, vrbs)
        await sheet.init() # Initialise sheet
        return Character(
          sheet.name,
          sheet.race,
          sheet.eyes,
          sheet.hair,
          sheet.age,
          sheet.gender,
          sheet.vrbsoverride,
          sheet.prnsoverride,
          sheet.height,
          sheet.weight,
          sheet.level,
          sheet.fpm,
          sheet.stats.ty,
          SN(
            str=sheet.stats.str,
            dex=sheet.stats.dex,
            con=sheet.stats.con,
            int=sheet.stats.int,
            wis=sheet.stats.wis,
            cha=sheet.stats.cha
          ),
          SN(
            str=sheet.stats.str_mod,
            dex=sheet.stats.dex_mod,
            con=sheet.stats.con_mod,
            int=sheet.stats.int_mod,
            wis=sheet.stats.wis_mod,
            cha=sheet.stats.cha_mod
          ),
        )

    @property
    def spm(self): # Squares per move
        return self.fpm / 5

    @property # A property is read only unless otherwise specified in the class
    def desc(self):
        return f"{self.name} {self.verbs[0]} a {self.age} year old {self.gender} level {self.level} {self.race}. {self.pronouns[0].capitalize()} {self.verbs[0]} {self.height} and weighs {self.weight}. {self.pronouns[0].capitalize()} also {self.verbs[1]} {self.hair} hair and {self.eyes} eyes." # Generates a simple desc to just highlight the main features of a character

    @property
    def inv_total_e(self):
        result = self.body_inv.inv_e() + self.belt_pouch.inv_e() + self.quiver.inv_e()
        result += self.belt_pouch.weight + self.quiver.weight
        if self.bpa:
            result += self.backpack.weight
        if self.boha:
            result += self.bag_of_holding.weight # Bag of Holding always weighs 15 lbs
        return result

    @property
    def _get_light_e(self):
        return (self.stat.str * 5) * self.size # Returns light encumbrance value in lbs

    @property
    def _get_heavy_e(self):
        return (self.stat.str * 10) * self.size

    @property
    def _get_max_e(self):
        return (self.stat.str * 15) * self.size

    @property
    def wealth(self):
        result = self.yen
        for i in gems:
            result += i.value
        for i in valuables:
            result += i.value
        return result

    @property
    def encumbered_calc(self): # Calculates if the player is encumbered
        if self._get_max_e() >= self.inv_total_e():
            return "M" # Return strings as they're easier to check
        elif self._get_heavy_e() >= self.inv_total_e():
            return "H"
        elif self._get_light_e() >= self.inv_total_e():
            return "L"
        return "N"

    def __bool__(self):
        return True


RARITIES = ( # Valid item rarities for DM to make new items
  "Common",
  "Uncommon",
  "Rare",
  "Very Rare",
  "Legendary",
  "Artifact"
)

yaml.register_class(ItemProperties);yaml.register_class(Item);yaml.register_class(Arrow);yaml.register_class(PreciousMaterial);yaml.register_class(Inventory);yaml.register_class(Character)

class Data(UserDict): # Subclassing UserDict (an implementation of a normal python dictionary that was *made* to be subclassed) so it can automatically load and save from files
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) # Initialise the superclass (UserDict) so everything is initialised
        self.lock = False
        with open('characters.yaml') as f: # Open characters.yaml to load the data into the dict
            tmp = yaml.load(f)
            if tmp:
                self.data.update(tmp) # `data` points to the actual dict that is implemented in the UserDict code. Update just adds all values from characters.yaml into the current dict
        self.counter = 0

    def __setitem__(self, key, value):
        self.counter += 1 # Incremented every time data is written to the dict
        super().__setitem__(key, value) # Call UserDict's setitem function
        if self.counter >= 5: # If counter is 5 then save all data
            while self.lock:
                pass
            self.lock = True
            with open('characters.yaml', 'w+') as f:
                yaml.dump(self.data, f)
            self.counter = 0
            self.lock = False

    def force_save(self): # So it can easily be saved on demand
        while self.lock:
            pass
        self.lock = True
        with open('characters.yaml', 'w+') as f:
            yaml.dump(self.data, f)
        self.counter = 0
        self.lock = False

    async def new_character(self, url, acc, prnsoverride=None, vrbsoverride=None): # Creates the character and adds it to the dict
        if self.get(acc):
            return False # Returns False if the account already has a character sheet linked to it
        self[acc] = await Character.import_from_url(url, prnsoverride, vrbsoverride)
        self.force_save() # So it isn't deleted after a restart call force save
        return True # Return True to indicate success

















