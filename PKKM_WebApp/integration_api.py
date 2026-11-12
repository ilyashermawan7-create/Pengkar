"""Revocable read-only integration credentials, separate from login sessions."""
import datetime
import hashlib
import json
import secrets
from fastapi import Depends,Header,HTTPException
from fastapi.responses import JSONResponse,StreamingResponse
from pydantic import BaseModel,Field,ConfigDict

class KeyRequest(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    name:str=Field(min_length=3,max_length=100)
    days:int=Field(default=30,ge=1,le=90)

def register(app,connect,auth,audit,build_snapshot,stream_snapshot):
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS integration_keys(
          id INTEGER PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,
          owner_id INTEGER NOT NULL REFERENCES users(id),expires_at TEXT NOT NULL,
          revoked INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    def admin(user=Depends(auth)):
        if user['role']!='admin':raise HTTPException(403,'Hanya Super Admin dapat mengelola API key')
        return user
    @app.get('/api/integration/keys')
    def keys(user=Depends(admin)):
        with connect() as c:
            rows=[dict(row) for row in c.execute('SELECT id,name,expires_at,revoked,created_at FROM integration_keys ORDER BY id DESC')]
        return JSONResponse({'items':rows},headers={'Cache-Control':'no-store'})
    @app.post('/api/integration/keys',status_code=201)
    def create_key(data:KeyRequest,user=Depends(admin)):
        token='pkkm_'+secrets.token_urlsafe(32)
        expires=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=data.days)).isoformat()
        with connect() as c:
            ident=c.execute('INSERT INTO integration_keys(name,token_hash,owner_id,expires_at) VALUES(?,?,?,?)',
                (data.name,hashlib.sha256(token.encode()).hexdigest(),user['id'],expires)).lastrowid
            audit(c,user,'create_integration_key','integration_key',ident)
        return JSONResponse({'id':ident,'token':token,'expires_at':expires},status_code=201,headers={'Cache-Control':'no-store'})
    @app.delete('/api/integration/keys/{ident}')
    def revoke_key(ident:int,user=Depends(admin)):
        with connect() as c:
            if not c.execute('UPDATE integration_keys SET revoked=1 WHERE id=?',(ident,)).rowcount:raise HTTPException(404,'API key tidak ditemukan')
            audit(c,user,'revoke_integration_key','integration_key',ident)
        return JSONResponse({'ok':True},headers={'Cache-Control':'no-store'})
    def credential(authorization:str|None=Header(None)):
        if not authorization or not authorization.startswith('Bearer ') or len(authorization)>200:raise HTTPException(401,'API key diperlukan')
        digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with connect() as c:
            row=c.execute('''SELECT k.id AS key_id,u.id,u.username,u.full_name,u.email,u.institution,u.campus FROM integration_keys k
                JOIN users u ON u.id=k.owner_id WHERE k.token_hash=? AND k.revoked=0 AND k.expires_at>?
                AND u.active=1 AND COALESCE(NULLIF(u.dashboard_role,''),u.role)='admin' ''',(digest,now)).fetchone()
            if not row:raise HTTPException(401,'API key tidak berlaku atau sudah dicabut')
            user=dict(row,role='admin')
            audit(c,user,'read_integration','integration_key',row['key_id'])
        return user
    @app.get('/api/integration/data')
    def data(user=Depends(credential)):
        def snapshot():
            dashboard=build_snapshot(user)
            # Read business data only. Never disclose users, sessions, or credential hashes.
            result={key:dashboard[key] for key in ('activities','students','surveys','masterStudents')}
            result['exportedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            from dashboard_aggregate import dashboard_stats
            from ppkt_api import CaseRecord,summary
            with connect() as c:
                result['dashboardStats']=dashboard_stats(c,[item['id'] for item in result['activities']])
                result['cases']=[dict(json.loads(row['payload']),id=row['id']) for row in c.execute('SELECT id,payload FROM ppkt_cases ORDER BY id')]
            result['caseSummary']=summary([CaseRecord.model_validate({k:v for k,v in item.items() if k!='id'}) for item in result['cases']])
            return result
        return StreamingResponse(stream_snapshot(snapshot),media_type='application/json',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
