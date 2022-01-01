from os import environ
from typing import Optional

from hata import parse_oauth2_redirect_url, USERS
from fastapi import Request, Cookie
from starlette.responses import Response, HTMLResponse, RedirectResponse

from ext.utils import Logger

root = environ['ROOT_URL']
url = environ['OAUTH']

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
    response =  templates.TemplateResponse("index.html", {"request":req})
    response.delete_cookies(key="user_id")
    return response
