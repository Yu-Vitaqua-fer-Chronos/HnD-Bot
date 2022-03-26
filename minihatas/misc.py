from os import system
from collections import namedtuple

from hata import Role, Emoji, ERROR_CODES
from hata import DiscordException
from hata.ext.extension_loader import EXTENSION_LOADER


People = Role.precreate(902669243248697404)

RoleMoji = namedtuple("RoleMoji", 'name plural role emoji')

Hero = RoleMoji('Hero', 'Heroes', Role.precreate(925119945254240296), Emoji.precreate(925123866471333918))
Villain = RoleMoji('Villain', 'Villains', Role.precreate(925119971485450292), Emoji.precreate(925123931403350097))
Antihero = RoleMoji('Anti-Hero', 'Anti-Heroes', Role.precreate(925119994247921705), Emoji.precreate(925127759880159322))
Antivillain = RoleMoji('Anti-Villain', 'Anti-Villains', Role.precreate(925120023964569612), Emoji.precreate(925130493828136990))
Vigilante = RoleMoji('Vigilante', 'Vigilantes', Role.precreate(925120050657108028), Emoji.precreate(925130551097163806))

RoleMojis = (Hero, Villain, Antihero, Antivillain, Vigilante)

@client.events
async def ready(client):
    info = "===__`User Roles`__===\n"

    for rolemoji in RoleMojis:
        for user in rolemoji.role.guild.users.values():
            if user.has_role(rolemoji.role):
                await client.user_role_delete(user, rolemoji.role, reason="Recalculating roles")

        try:
            await client.reaction_add((913148168756162590, 925140179516272660), rolemoji.emoji)
        except DiscordException:
            pass

        reactors = await client.reaction_user_get_all((913148168756162590, 925140179516272660), rolemoji.emoji)
        count = 0
        for reactor in reactors:
            if reactor.id == client.id or reactor.has_role(rolemoji.role):
                continue
            count +=1
            try:
                await client.user_role_add(reactor, rolemoji.role, reason="User reacted to "+rolemoji.name)
            except DiscordException as err:
                count -= 1
                if err.code == ERROR_CODES.unknown_member:
                    await client.reaction_delete((902668029115138078, misc['info']['message']), rolemoji.emoji, reactor)
                else:
                    raise
        info += ("  - "+rolemoji.plural+" ⟩ " + str(count) + '\n')
    info += "\nNote: Users can have more than one role"

    try:
        await client.message_edit((925141885213888583, misc['info'].get('message', 0)), info)
    except DiscordException:
        misc['info']['message'] = (await client.message_create(925141885213888583, info)).id
        misc.force_save()

@client.events
async def reaction_add(client, event):
    if not event.message.id == 913148168756162590:
        return

    rolemoji = None
    for re in RoleMojis:
        if re.emoji.id == event.emoji.id:
            rolemoji = re

    if not rolemoji:
        return

    await client.user_role_add(user, rolemoji.role, reason="User reacted to "+rolemoji.name)

@client.events
async def reaction_delete(client, event):
    if not event.message.id == 913148168756162590:
        return

    rolemoji = None
    for re in RoleMojis:
        if re.emoji.id == event.emoji.id:
            rolemoji = re

    if not rolemoji:
        return

    await client.user_role_delete(user, rolemoji.role, reason="User removed reaction from `"+rolemoji.plural+"` group")

@client.interactions(guild=guilds)
async def doing_your_mum():
    """Test command"""
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
