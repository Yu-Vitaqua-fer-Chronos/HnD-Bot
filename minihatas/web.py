from os import environ
from subprocess import getoutput
from typing import Optional

from hata import parse_oauth2_redirect_url, USERS, BUILTIN_EMOJIS
from scarletio import enter_executor
from fastapi import Request, Cookie
from starlette.responses import Response, HTMLResponse, RedirectResponse

from ext.utils import Logger

root = environ['ROOT_URL']
url = environ['OAUTH']

msgs = []

tick = BUILTIN_EMOJIS['white_check_mark']
cross = BUILTIN_EMOJIS['x']

with open('favicon.ico', 'rb') as f:
    favicon_response = Response(content=f.read(), media_type=('image/x-icon'), status_code=200)

@app.get('/')
async def home(req:Request, user_id:Optional[int]=Cookie(False)):
    if not user_id:
        response = RedirectResponse(url=url)
        response.set_cookie(key='redir', value='/', expires=360)
        return response
    return templates.TemplateResponse("index.html", {"request":req, "name":USERS.get(user_id, "Unknown").full_name})

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return favicon_response

@app.get('/authorise')
async def authorise():
    return RedirectResponse(url=url)

@app.get('/callback')
async def authorised(redir:Optional[str]=Cookie('/'), code:str=None):
    Logger.debug('OAuth code', code)
    if not code:
        return HTMLResponse(f"""<h1>Invalid Access Code!</h1>
            <p>To login, go to <a href={root}/authorise>the OAuth page</>!</p>""")
    oauth_access = await client.activate_authorization_code(root+'/callback', code, 'identify')
    user = await client.user_info_get(oauth_access)
    response = RedirectResponse(url=redir)
    response.set_cookie(key='user_id', value=user.id, expires=360)
    Logger.debug('Authorised User', user.id)
    return response

@app.get('/logout')
async def logout(req:Request):
    response = templates.TemplateResponse("logout.html", {"request":req})
    response.delete_cookies(key="user_id")
    return response

@app.get('/git')
async def update():
    msg = await client.message_create(environ['LOGGING_CHANNEL'], "New commit pushed to GitHub! Would you like to update?")
    msgs.append(msg)
    await client.reaction_add(msg, tick)
    await client.reaction_add(msg, cross)

@client.events
async def reaction_add(client, event):
    if event.user.id == client.id:
        return
    if not client.is_owner(event.user) and event.emoji in (tick, cross):
        await client.message_create(event.message.channel, "You don't have permission to do this!!")
        await client.reaction_remove(event.message, event.emoji, event.user)
    if event.message.id not in msgs:
        return
    del msgs[msgs.index(event.message.id)]
    await client.reaction_clear(event.message)
    if event.emoji is tick:
        await client.message_edit(event.message, "Pulling changes from GitHub now..."):
        async with enter_executor():
            output = getoutput('git pull')
        await client.message_edit(event.message, "Done, here is the output:"+'```sh\n'+output+'```')
    elif event.emoji is cross:
        await client.message_edit(event.message, "Ignoring latest commit from git.")
