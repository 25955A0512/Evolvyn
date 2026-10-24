"""Personal display/notification preferences, isolated by authenticated account."""
import json
from typing import Literal
from fastapi import Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict

class Preferences(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    theme:Literal['light','dark','system']='system'
    text_size:Literal['normal','large']='normal'
    sound:bool=False
    browser_notifications:bool=False

def install(app,conn,auth):
    def account(request):
        identity=getattr(request.state,'identity',None)
        if not identity or not identity.get('account_id'):raise HTTPException(403,'Sign in with an account to save personal settings')
        return identity['account_id']

    @app.get('/api/account/preferences')
    def get_preferences(request:Request,owner=Depends(auth)):
        id=account(request)
        with conn() as c:row=c.execute('SELECT body FROM account_preferences WHERE account_id=%s',(id,)).fetchone()
        return Preferences.model_validate(row['body'] if row else {}).model_dump()

    @app.put('/api/account/preferences')
    def save_preferences(body:Preferences,request:Request,owner=Depends(auth)):
        id=account(request)
        with conn() as c:c.execute('INSERT INTO account_preferences(account_id,body) VALUES (%s,%s) ON CONFLICT(account_id) DO UPDATE SET body=EXCLUDED.body',(id,json.dumps(body.model_dump())))
        return body.model_dump()
