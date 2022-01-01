from os import system
from collections import namedtuple

from hata import Role, Emoji
from hata import DiscordException
from hata.ext.extension_loader import EXTENSION_LOADER

People = Role.precreate(902669243248697404)

RoleMoji = namedtuple("RoleMoji", 'role emoji')

Hero = RoleMoji(Role.precreate(925119945254240296), Emoji.precreate(925123866471333918))
Villain = RoleMoji(Role.precreate(925119971485450292), Emoji.precreate(925123931403350097))
Antihero = RoleMoji(Role.precreate(925119994247921705), Emoji.precreate(925127759880159322))
Antivillain = RoleMoji(Role.precreate(925120023964569612), Emoji.precreate(925130493828136990))
Vigilante = RoleMoji(Role.precreate(925120050657108028), Emoji.precreate(925130551097163806))

@client.events
async def ready(client):
    info = "===__`User Roles`__===\n"
    try:
        await client.reaction_add((913148168756162590, 925140179516272660), Hero.emoji)
    except DiscordException:
        pass
    try:
        await client.reaction_add((913148168756162590, 925140179516272660), Villain.emoji)
    except DiscordException:
        pass
    try:
        await client.reaction_add((913148168756162590, 925140179516272660), Antihero.emoji)
    except DiscordException:
        pass
    try:
        await client.reaction_add((913148168756162590, 925140179516272660), Antivillain.emoji)
    except DiscordException:
        pass
    try:
        await client.reaction_add((913148168756162590, 925140179516272660), Vigilante.emoji)
    except DiscordException:
        pass

    reactors = await client.reaction_user_get_all((913148168756162590, 925140179516272660), Hero.emoji)
    for reactor in reactors:
        if reactor.id == client.id or Hero.role in reactor.get_guild_profile_for(guilds[0]).roles:
            continue
        await client.user_role_add(reactor, Hero.role, reason="User reacted to Hero")
    info += ("  - Heroes ⟩ " + str(len(reactors) - 1) + '\n')
    reactors = await client.reaction_user_get_all((913148168756162590, 925140179516272660), Villain.emoji)
    for reactor in reactors:
        if reactor.id == client.id or Villain.role in reactor.get_guild_profile_for(guilds[0]).roles:
            continue
        await client.user_role_add(reactor, Villain.role, reason="User reacted to Villain")
    info += ("  - Villains ⟩ " + str(len(reactors) - 1) + '\n')
    reactors = await client.reaction_user_get_all((913148168756162590, 925140179516272660), Antihero.emoji)
    for reactor in reactors:
        if reactor.id == client.id or Antihero.role in reactor.get_guild_profile_for(guilds[0]).roles:
            continue
        await client.user_role_add(reactor, Antihero.role, reason="User reacted to Anti-Hero")
    info += ("  - Anti-Heroes ⟩ " + str(len(reactors) - 1) + '\n')
    reactors = await client.reaction_user_get_all((913148168756162590, 925140179516272660), Antivillain.emoji)
    for reactor in reactors:
        if reactor.id == client.id or Antivillain.role in reactor.get_guild_profile_for(guilds[0]).roles:
            continue
        await client.user_role_add(reactor, Antivillain.role, reason="User reacted to Anti-Villain")
    info += ("  - Anti-Villains ⟩ " + str(len(reactors) - 1) + '\n')
    reactors = await client.reaction_user_get_all((913148168756162590, 925140179516272660), Vigilante.emoji)
    for reactor in reactors:
        if reactor.id == client.id or Vigilante.role in reactor.get_guild_profile_for(guilds[0]).roles:
            continue
        await client.user_role_add(reactor, Vigilante.role, reason="User reacted to Vigilante")
    info += ("  - Vigilantes ⟩ " + str(len(reactors) - 1) + '\n\n')
    info += "Note: Users can have more than one role"

    try:
        await client.message_edit((925141885213888583, misc['info'].get('message', 0)), info)
    except DiscordException:
        misc['info']['message'] = (await client.message_create(925141885213888583, info)).id
        misc.force_save()

@client.interactions(guild=guilds)
async def doing_your_mum():
    """Test ping command"""
    yield '***DOIN UR MOM***'

@client.interactions(guild=guilds)
async def git_pull(event, reload_on_success:bool=True):
    """Pulls changes from upstream"""
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

@client.interactions(guild=guilds)
async def git_push(event, msg:str="Autocommit"):
    """Commits all changes to git"""
    if not client.is_owner(event.user):
        yield "You don't have access to this command!"
        return
    yield "Saving and pushing changes to git..."
    code = system(f"autocommit \"{msg}\"")
    result = "Unknown"
    if code == 0:
        result = "Success"
    elif code == 1:
        result = "Failed"
    yield result

@client.interactions(guild=guilds)
async def reload(event):
    """Reloads all minihatas"""
    if not client.is_owner(event.user):
        yield "You don't have access to this command!"
        return
    yield "Reloading all minihatas!"
    EXTENSION_LOADER.reload_all()
    yield "Done!"
