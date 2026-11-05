"""PKKM reporting app. SQLite is centralized when deployed on one server."""
import os, sqlite3, hashlib, hmac, secrets, csv, io, datetime, contextlib
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE=Path(__file__).resolve().parent
DB=Path(os.getenv('PKKM_DB_PATH',str(BASE/'pkkm.sqlite3')))
app=FastAPI(title='PKKM Telkom University API',version='1.0.0')
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware,minimum_size=1000,compresslevel=3)

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    return c

def hash_password(p,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(p.encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1).hex()

def check_password(p,stored):
    try:
        salt=stored.split(':')[0]
        return hmac.compare_digest(hash_password(p,salt),stored)
    except Exception:return False

with connect() as c:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,full_name TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','pengkar','asrama','viewer')),active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY,nama_kegiatan TEXT NOT NULL,tanggal TEXT NOT NULL,program TEXT NOT NULL CHECK(program IN ('Pengembangan Karakter','Asrama')),kategori TEXT NOT NULL,tempat TEXT NOT NULL DEFAULT '',unit_kerjasama TEXT NOT NULL DEFAULT '',pembicara TEXT NOT NULL DEFAULT '',target_peserta INTEGER NOT NULL DEFAULT 0,jumlah_peserta INTEGER NOT NULL DEFAULT 0,anggaran REAL NOT NULL DEFAULT 0,realisasi REAL NOT NULL DEFAULT 0,laporan TEXT NOT NULL DEFAULT '',kendala TEXT NOT NULL DEFAULT '',tindak_lanjut TEXT NOT NULL DEFAULT '',link_eviden TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Terlaksana','Dievaluasi')),created_by INTEGER REFERENCES users(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY,activity_id INTEGER NOT NULL UNIQUE REFERENCES activities(id) ON DELETE CASCADE,jumlah_responden INTEGER NOT NULL DEFAULT 0,skor_materi REAL,skor_narasumber REAL,skor_fasilitas REAL,skor_dampak REAL,temuan TEXT NOT NULL DEFAULT '',rekomendasi TEXT NOT NULL DEFAULT '',updated_by INTEGER REFERENCES users(id),updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT NOT NULL,entity TEXT NOT NULL,entity_id INTEGER,at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')
    if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        username=os.getenv('PKKM_ADMIN_USER')
        password=os.getenv('PKKM_ADMIN_PASSWORD')
        if username and password and len(password)>=12:
            c.execute('INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)',(username,hash_password(password),'Administrator PKKM','admin'))
        else:
            print('SETUP: set PKKM_ADMIN_USER and PKKM_ADMIN_PASSWORD (min 12 chars), then restart to create initial administrator.')

from dashboard_api import initialize, register
initialize(connect)

def audit(c,user,action,entity,entity_id):
    c.execute('INSERT INTO audit(user_id,action,entity,entity_id) VALUES(?,?,?,?)',(user['id'],action,entity,entity_id))

def auth(authorization:Optional[str]=Header(None)):
    if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Login diperlukan')
    token=authorization[7:]
    with connect() as c:
        u=c.execute('''SELECT u.id,u.username,u.full_name,COALESCE(NULLIF(u.dashboard_role,''),u.role) AS role,u.email,u.institution,u.campus FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at > ? AND u.active=1''',(hashlib.sha256(token.encode()).hexdigest(),datetime.datetime.now(datetime.timezone.utc).isoformat())).fetchone()
    if not u:raise HTTPException(401,'Sesi kedaluwarsa')
    return dict(u)

def allow(u,program=None,admin=False):
    if admin and u['role']!='admin':raise HTTPException(403,'Hanya administrator')
    if u['role'] in ('viewer','verifier','ppkpt'):raise HTTPException(403,'Akses baca saja')
    if program and u['role'] not in ('admin','operator', 'pengkar' if program=='Pengembangan Karakter' else 'asrama'):
        raise HTTPException(403,'Tidak berwenang pada program ini')

class Login(BaseModel):
    username:str
    password:str
@app.post('/api/login')
def login(data:Login):
    with connect() as c:
        u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(data.username,)).fetchone()
        if not u or not check_password(data.password,u['password_hash']):raise HTTPException(401,'Kredensial tidak sesuai')
        token=secrets.token_urlsafe(32)
        exp=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)).isoformat()
        c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],exp))
        return {'token':token,'user':{'username':u['username'],'full_name':u['full_name'],'role':u['role']}}
@app.post('/api/logout')
def logout(authorization:Optional[str]=Header(None),u=Depends(auth)):
    with connect() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(authorization[7:].encode()).hexdigest(),))
    return {'ok':True}
@app.get('/api/me')
def me(u=Depends(auth)):return u

class Activity(BaseModel):
    nama_kegiatan:str=Field(min_length=3,max_length=200)
    tanggal:datetime.date
    program:str
    kategori:str=Field(min_length=1,max_length=100)
    tempat:str=''
    unit_kerjasama:str=''
    pembicara:str=''
    target_peserta:int=Field(default=0,ge=0)
    jumlah_peserta:int=Field(default=0,ge=0)
    anggaran:float=Field(default=0,ge=0)
    realisasi:float=Field(default=0,ge=0)
    laporan:str=''
    kendala:str=''
    tindak_lanjut:str=''
    link_eviden:str=''
    status:str='Draft'
    
    def validate_values(self):
        if self.program not in ('Pengembangan Karakter','Asrama') or self.status not in ('Draft','Terlaksana','Dievaluasi'):
            raise HTTPException(422,'Program atau status tidak valid')

FIELDS=['nama_kegiatan','tanggal','program','kategori','tempat','unit_kerjasama','pembicara','target_peserta','jumlah_peserta','anggaran','realisasi','laporan','kendala','tindak_lanjut','link_eviden','status']
@app.get('/api/activities')
def activities(program:str='',year:str='',status:str='',u=Depends(auth)):
    if u['role'] in ('pengkar','asrama'):
        permitted='Asrama' if u['role']=='asrama' else 'Pengembangan Karakter'
        if program and program!=permitted:return []
        program=permitted
    clauses=[];args=[]
    if program:clauses.append('a.program=?');args.append(program)
    if year:clauses.append("(substr(a.tanggal,1,4)=? OR (a.tanggal='' AND json_extract(d.payload,'$.tahun')=?))");args.extend([year,year])
    if status:clauses.append('a.status=?');args.append(status)
    where='WHERE '+' AND '.join(clauses) if clauses else ''
    with connect() as c:
        rows=c.execute(f'''SELECT a.*,e.jumlah_responden,e.skor_materi,e.skor_narasumber,e.skor_fasilitas,e.skor_dampak,e.temuan,e.rekomendasi FROM activities a LEFT JOIN evaluations e ON e.activity_id=a.id LEFT JOIN activity_details d ON d.activity_id=a.id {where} ORDER BY a.tanggal DESC,a.id DESC''',args).fetchall()
    return [dict(x) for x in rows]
@app.post('/api/activities',status_code=201)
def create_activity(data:Activity,u=Depends(auth)):
    data.validate_values();allow(u,data.program)
    values=data.model_dump(mode='json')
    with connect() as c:
        cur=c.execute('INSERT INTO activities('+','.join(FIELDS)+',created_by) VALUES('+','.join('?' for _ in FIELDS)+',?)',tuple(values[k] for k in FIELDS)+(u['id'],))
        audit(c,u,'create','activity',cur.lastrowid)
        return {'id':cur.lastrowid}
@app.put('/api/activities/{id}')
def update_activity(id:int,data:Activity,u=Depends(auth)):
    data.validate_values()
    with connect() as c:
        existing=c.execute('SELECT program FROM activities WHERE id=?',(id,)).fetchone()
        if not existing:raise HTTPException(404,'Kegiatan tidak ditemukan')
        allow(u,existing['program']);allow(u,data.program)
        values=data.model_dump(mode='json')
        c.execute('UPDATE activities SET '+','.join(k+'=?' for k in FIELDS)+',updated_at=CURRENT_TIMESTAMP WHERE id=?',tuple(values[k] for k in FIELDS)+(id,))
        audit(c,u,'update','activity',id)
    return {'ok':True}
@app.delete('/api/activities/{id}')
def delete_activity(id:int,u=Depends(auth)):
    with connect() as c:
        a=c.execute('SELECT program FROM activities WHERE id=?',(id,)).fetchone()
        if not a:raise HTTPException(404,'Kegiatan tidak ditemukan')
        allow(u,a['program'])
        c.execute('DELETE FROM activities WHERE id=?',(id,));audit(c,u,'delete','activity',id)
    return {'ok':True}

class Evaluation(BaseModel):
    jumlah_responden:int=Field(ge=0)
    skor_materi:Optional[float]=Field(default=None,ge=1,le=5)
    skor_narasumber:Optional[float]=Field(default=None,ge=1,le=5)
    skor_fasilitas:Optional[float]=Field(default=None,ge=1,le=5)
    skor_dampak:Optional[float]=Field(default=None,ge=1,le=5)
    temuan:str=''
    rekomendasi:str=''
@app.put('/api/activities/{id}/evaluation')
def save_evaluation(id:int,data:Evaluation,u=Depends(auth)):
    with connect() as c:
        a=c.execute('SELECT program FROM activities WHERE id=?',(id,)).fetchone()
        if not a:raise HTTPException(404,'Kegiatan tidak ditemukan')
        allow(u,a['program'])
        c.execute('''INSERT INTO evaluations(activity_id,jumlah_responden,skor_materi,skor_narasumber,skor_fasilitas,skor_dampak,temuan,rekomendasi,updated_by) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(activity_id) DO UPDATE SET jumlah_responden=excluded.jumlah_responden,skor_materi=excluded.skor_materi,skor_narasumber=excluded.skor_narasumber,skor_fasilitas=excluded.skor_fasilitas,skor_dampak=excluded.skor_dampak,temuan=excluded.temuan,rekomendasi=excluded.rekomendasi,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP''',(id,data.jumlah_responden,data.skor_materi,data.skor_narasumber,data.skor_fasilitas,data.skor_dampak,data.temuan,data.rekomendasi,u['id']))
        c.execute("UPDATE activities SET status='Dievaluasi',updated_at=CURRENT_TIMESTAMP WHERE id=?",(id,))
        audit(c,u,'evaluate','activity',id)
    return {'ok':True}

@app.get('/api/summary')
def summary(program:str='',year:str='',u=Depends(auth)):
    rows=activities(program,year,'',u)
    done=[r for r in rows if r['status']!='Draft']
    scored=[r for r in done if r['skor_dampak'] is not None]
    return {'total':len(rows),'terlaksana':len(done),'dievaluasi':sum(r['status']=='Dievaluasi' for r in rows),'peserta':sum(r['jumlah_peserta'] for r in done),'target_peserta':sum(r['target_peserta'] for r in done),'anggaran':sum(r['anggaran'] for r in rows),'realisasi':sum(r['realisasi'] for r in rows),'rerata_dampak':round(sum(r['skor_dampak'] for r in scored)/len(scored),2) if scored else None,'by_program':{p:sum(r['program']==p for r in rows) for p in ('Pengembangan Karakter','Asrama')},'by_quarter':{f'TW{i}':sum((int(r['tanggal'][5:7])-1)//3+1==i for r in rows if len(r['tanggal'])>=10) for i in range(1,5)}}

@app.get('/api/report.csv')
def report_csv(program:str='',year:str='',u=Depends(auth)):
    rows=activities(program,year,'',u)
    output=io.StringIO();writer=csv.writer(output)
    cols=['id']+FIELDS+['jumlah_responden','skor_materi','skor_narasumber','skor_fasilitas','skor_dampak','temuan','rekomendasi']
    writer.writerow(cols)
    for r in rows:writer.writerow([r.get(k) for k in cols])
    return StreamingResponse(iter(['\ufeff'+output.getvalue()]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="laporan_pkkm.csv"'})

class NewUser(BaseModel):
    username:str=Field(min_length=3,max_length=60)
    password:str=Field(min_length=12)
    full_name:str=Field(min_length=2,max_length=120)
    role:str
@app.get('/api/users')
def users(u=Depends(auth)):
    if u['role']!='admin':raise HTTPException(403,'Hanya administrator')
    with connect() as c:return [dict(r) for r in c.execute('SELECT id,username,full_name,role,active FROM users ORDER BY id')]
@app.post('/api/users',status_code=201)
def create_user(data:NewUser,u=Depends(auth)):
    allow(u,admin=True)
    if data.role not in ('admin','pengkar','asrama','viewer'):raise HTTPException(422,'Role tidak valid')
    try:
        with connect() as c:
            cur=c.execute('INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)',(data.username,hash_password(data.password),data.full_name,data.role))
            audit(c,u,'create','user',cur.lastrowid)
            return {'id':cur.lastrowid}
    except sqlite3.IntegrityError:raise HTTPException(409,'Username sudah digunakan')
@app.get('/api/audit')
def audit_log(u=Depends(auth)):
    allow(u,admin=True)
    with connect() as c:return [dict(r) for r in c.execute('SELECT a.*,u.username FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100')]

register(app,connect,auth,allow,audit,hash_password,check_password)
from ppkt_api import initialize as initialize_ppkt,register as register_ppkt
initialize_ppkt(connect)
register_ppkt(app,connect,auth,audit)

app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')
@app.get('/')
def index():return FileResponse(BASE/'static'/'index.html',headers={'Cache-Control':'no-store'})
