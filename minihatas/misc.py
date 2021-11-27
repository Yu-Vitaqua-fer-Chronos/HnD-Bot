from os import system

from hata.ext.extension_loader import EXTENSION_LOADER

@client.interactions(guild=guilds)
async def ping():
    """Test ping command"""
    yield 'pong'

@client.interactions(guild=guilds)
async def git_pull(event, reload_on_success:bool=True):
    if not client.is_owner(event.user):
        yield "You don't have access to this command!"
        return
    yield "Updating with git..."
    code = system("git pull")
    result = "Unknown"
    if code == 0:
        result = "Success"
    elif code == 1:
        result = "Failed"
    if not reload_on_success:
        yield f"Exited with exit code `{code}`! ({result})"
        return
    if code == 0 and reload_on_success:
        yield f"Exited with exit code `{code}`! Reloading all minihatas now..."
        EXTENSION_LOADER.reload_all()
        yield "Reloaded all minihatas!"
        return
    yield f"Exited with exit code `{code}`! ({result})"
