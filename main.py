from os import environ

from hata import Client, Guild
from scarletio.ext import asyncio
from hata.ext.commands_v2 import checks
from hata.ext.extension_loader import EXTENSION_LOADER
from uvicorn import run as run_server
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from ext.utils import FileDict
from ext.interpreter import Interpreter

client = Client(environ['TOKEN'], secret=environ['SECRET'], client_id=int(environ['CLIENT_ID']), prefix=environ.get('PREFIX', 'h>'), extensions=('slash', 'commands_v2'))
HNDHQ = Guild.precreate(902668029115138078)
guilds = (HNDHQ,)

MESSAGE = None

@client.events
async def launch(client):
    global MESSAGE
    MESSAGE = await client.message_get(913148168756162590, 925140179516272660)

chars = FileDict('{}', 'characters.yaml')
items = FileDict('[]', 'items.yaml')
misc = FileDict("{'info':{}}", 'miscellaneous.yaml')

PORT = 8080
app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Add default variables
EXTENSION_LOADER.add_default_variables(
  client=client,
  HNDHQ=HNDHQ,
  guilds=guilds,
  chars=chars,
  items=items,
  misc=misc,
  app=app,
  templates=templates,
)
EXTENSION_LOADER.add('minihatas')
EXTENSION_LOADER.load_all()

# Set up execute command
client.commands(Interpreter(globals()), name='execute', checks=[checks.owner_only()])

# Start the client
client.start()

# Start uvicorn (Now supported by Hata!)
if environ.get('WEB'):
    run_server(app, host="0.0.0.0", port=PORT, log_level="info")
