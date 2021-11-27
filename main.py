from os import environ

from hata import Client, Guild
from hata.ext import asyncio
from hata.ext.extension_loader import EXTENSION_LOADER

from ext.utils import Data
from ext.web import app

client = Client(environ['TOKEN'], extensions=('slash'))
guilds = (Guild.precreate(902668029115138078),)

try:
    with open('userdata.yaml') as f:
        pass
except FileNotFoundError:
    with open('userdata.yaml', 'w+') as f:
        f.write("{}")

data = Data()

# Add default variables
EXTENSION_LOADER.add_default_variables(
  client=client,
  guilds=guilds,
  data=data,
)
EXTENSION_LOADER.add('minihatas')
EXTENSION_LOADER.load_all()

# Start the client
client.start()
