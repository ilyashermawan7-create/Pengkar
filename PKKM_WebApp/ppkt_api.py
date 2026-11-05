"""PPK Tel-U case management. Case records are separate from activity/survey data."""
import datetime
import json
import re
import base64
import hashlib
from pathlib import Path
from fastapi.responses import Response
from ppkt_executive import faculty_label,executive_stats
from fastapi import Depends,HTTPException,Header
from pydantic import BaseModel,Field,ConfigDict,model_validator

class CaseRecord(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='forbid')
    year:int|None=Field(default=None,ge=1900,le=2200)
    reportDate:datetime.date|None=None
    caseNumber:str=Field(min_length=1,max_length=200)
    reporterInstitution:str=Field(default='',max_length=500)
    reporterStudyProgram:str=Field(default='',max_length=500)
    reporterFaculty:str=Field(default='',max_length=500)
    category:str=Field(default='',max_length=300)
    bap:bool|None=None
    assignmentLetter:bool|None=None
    facultyAction:bool|None=None
    directorateAction:bool|None=None
    reporterCounseling:bool|None=None
    status:str=Field(default='',max_length=1000)
    positionNotes:str=Field(default='',max_length=10000)
    reportedInstitution:str=Field(default='',max_length=500)
    reportedStudyProgram:str=Field(default='',max_length=500)
    reportedFaculty:str=Field(default='',max_length=500)
    reportedCounseling:bool|None=None
    notes:str=Field(default='',max_length=20000)
    @model_validator(mode='after')
    def check_year(self):
        if self.reportDate and self.year is None:self.year=self.reportDate.year
        if self.reportDate and self.year!=self.reportDate.year:raise ValueError('Tahun tidak sesuai tanggal laporan masuk')
        return self

class CaseImport(BaseModel):
    items:list[CaseRecord]=Field(min_length=1,max_length=10000)

def number_key(number):return re.sub(r'\s+','',number).casefold()
DEFAULT_LOGO=Path(__file__).parent/'static/images/logo-satgas-ppkpt.png'

def initialize(connect):
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS ppkt_cases(id INTEGER PRIMARY KEY,case_key TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS ppkt_branding(id INTEGER PRIMARY KEY CHECK(id=1),mime TEXT NOT NULL,image BLOB NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS ppkt_branding_defaults(digest TEXT PRIMARY KEY,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        if DEFAULT_LOGO.exists():
            image=DEFAULT_LOGO.read_bytes()
            digest=hashlib.sha256(image).hexdigest()
            first=c.execute('INSERT OR IGNORE INTO ppkt_branding_defaults(digest) VALUES(?)',(digest,)).rowcount
            if first:
                # Install this supplied official logo once, replacing any old substitute.
                # A later intentional upload remains intact on subsequent restarts.
                c.execute("INSERT INTO ppkt_branding VALUES(1,'image/png',?) ON CONFLICT(id) DO UPDATE SET mime=excluded.mime,image=excluded.image",(image,))


def bucket(status):
    value=' '.join(status.casefold().split())
    if not value:return 'Belum diisi'
    if value in ('tutup kasus','kasus ditutup','selesai'):return 'Ditutup'
    if value in ('tarik kasus','sk pencabutan kasus','kasus dicabut'):return 'Ditarik/dicabut'
    return 'Dalam proses'

def summary(records):
    result={'total':len(records),'closed':0,'withdrawn':0,'ongoing':0,'unknownStatus':0,'missingDate':0,'categories':{},'statuses':{},'years':{},'months':{},'workflow':{},'counseling':{}}
    fields={'Ditutup':'closed','Ditarik/dicabut':'withdrawn','Dalam proses':'ongoing','Belum diisi':'unknownStatus'}
    for item in records:
        result[fields[bucket(item.status)]]+=1
        for target,value in (('categories',item.category),('statuses',item.status),('years',str(item.year) if item.year else 'Belum diisi')):
            value=value or 'Belum diisi';result[target][value]=result[target].get(value,0)+1
        if item.reportDate:
            key=item.reportDate.strftime('%Y-%m');result['months'][key]=result['months'].get(key,0)+1
        else:result['missingDate']+=1
    for target,keys in (('workflow',('bap','assignmentLetter','facultyAction','directorateAction')),('counseling',('reporterCounseling','reportedCounseling'))):
        for field in keys:
            values=[getattr(item,field) for item in records]
            result[target][field]={'yes':sum(value is True for value in values),'no':sum(value is False for value in values),'unknown':sum(value is None for value in values)}
    result.update(executive_stats(records,bucket))
    return result

def register(app,connect,auth,audit):
    def read_access(user):
        if user['role'] not in ('admin','operator','viewer','ppkpt'):raise HTTPException(403,'Ringkasan kasus PPK Tel-U tidak tersedia untuk role ini')
    def admin_access(user):
        if user['role'] not in ('admin','ppkpt'):raise HTTPException(403,'Rincian dan impor kasus hanya tersedia untuk Super Admin dan Operator PPKPT')
    def selected(c,year,category,status,faculty=''):
        rows=[]
        for row in c.execute('SELECT id,payload FROM ppkt_cases ORDER BY id'):
            item=CaseRecord.model_validate_json(row['payload'])
            if year is not None and item.year!=year:continue
            if category and (item.category or 'Belum diisi')!=category:continue
            if status and bucket(item.status)!=status:continue
            if faculty and faculty_label(item)!=faculty:continue
            rows.append((row['id'],item))
        return rows
    @app.get('/api/ppkt/summary')
    def get_summary(year:int|None=None,category:str='',status:str='',faculty:str='',user=Depends(auth)):
        read_access(user)
        with connect() as c:
            all_rows=selected(c,None,'','')
            records=selected(c,year,category,status,faculty)
        return {**summary([item for _,item in records]),'availableYears':sorted({item.year for _,item in all_rows if item.year},reverse=True),'availableCategories':sorted({item.category or 'Belum diisi' for _,item in all_rows}),'availableFaculties':sorted({faculty_label(item) for _,item in all_rows})}
    @app.get('/api/ppkt/cases')
    def get_cases(year:int|None=None,category:str='',status:str='',faculty:str='',user=Depends(auth)):
        admin_access(user)
        with connect() as c:records=selected(c,year,category,status,faculty)
        return {'items':[dict(item.model_dump(mode='json'),id=ident) for ident,item in records]}
    @app.get('/api/ppkt/distribution')
    def case_distribution(year:int|None=None,category:str='',status:str='',faculty:str='',search:str='',page:int=1,size:int=10,user=Depends(auth)):
        admin_access(user)
        if page<1 or size not in (10,50,10000) or len(search)>200:raise HTTPException(422,'Parameter halaman tidak valid')
        with connect() as c:rows=selected(c,year,category,status,faculty)
        query=search.strip().casefold()
        items=[{'displayId':f"CASE-{item.year or 'NA'}-{ident:04d}",'year':item.year,'faculty':faculty_label(item),'studyProgram':item.reportedStudyProgram or 'Belum diisi','category':item.category or 'Belum diisi','status':item.status or 'Belum diisi','statusGroup':bucket(item.status),'counseling':item.reporterCounseling} for ident,item in rows if not query or query in faculty_label(item).casefold() or query in item.reportedStudyProgram.casefold()]
        return {'total':len(items),'items':items[(page-1)*size:page*size]}

    @app.get('/api/ppkt/logo')
    def get_logo(if_none_match:str|None=Header(None)):
        with connect() as c:
            row=c.execute('SELECT mime,image FROM ppkt_branding WHERE id=1').fetchone()
        if not row:raise HTTPException(404,'Logo belum diunggah')
        digest='"'+hashlib.sha256(row['image']).hexdigest()+'"'
        headers={'Cache-Control':'no-cache','ETag':digest,'X-Content-Type-Options':'nosniff'}
        if if_none_match==digest:return Response(status_code=304,headers=headers)
        return Response(content=row['image'],media_type=row['mime'],headers=headers)

    class LogoData(BaseModel):
        data:str=Field(max_length=750000)
    @app.put('/api/ppkt/logo')
    def upload_logo(data:LogoData,user=Depends(auth)):
        if user['role']!='admin':raise HTTPException(403,'Logo hanya dapat diubah Super Admin')
        try:
            prefix,encoded=data.data.split(',',1)
            image=base64.b64decode(encoded,validate=True)
        except (ValueError,TypeError):raise HTTPException(422,'Berkas logo tidak valid')
        mime='image/png' if image.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if image.startswith(b'\xff\xd8\xff') else 'image/webp' if image[:4]==b'RIFF' and image[8:12]==b'WEBP' else None
        if not mime or len(image)>500000:raise HTTPException(422,'Gunakan PNG, JPG, atau WebP maksimal 500 KB')
        with connect() as c:
            c.execute('INSERT INTO ppkt_branding VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET mime=excluded.mime,image=excluded.image',(mime,image))
            audit(c,user,'update_ppkt_logo','ppkt',None)
        return {'version':hashlib.sha256(image).hexdigest()}

    @app.post('/api/ppkt/cases',status_code=201)
    def create_case(data:CaseRecord,user=Depends(auth)):
        admin_access(user)
        import sqlite3
        try:
            with connect() as c:
                cur=c.execute('INSERT INTO ppkt_cases(case_key,payload,created_by) VALUES(?,?,?)',(number_key(data.caseNumber),json.dumps(data.model_dump(mode='json')),user['id']))
                audit(c,user,'create_ppkt_case','ppkt',cur.lastrowid)
                return {'id':cur.lastrowid}
        except sqlite3.IntegrityError:raise HTTPException(409,'Nomor kasus sudah terdaftar')
    @app.put('/api/ppkt/cases/{ident}')
    def edit_case(ident:int,data:CaseRecord,user=Depends(auth)):
        admin_access(user)
        import sqlite3
        try:
            with connect() as c:
                if not c.execute('SELECT 1 FROM ppkt_cases WHERE id=?',(ident,)).fetchone():raise HTTPException(404,'Kasus tidak ditemukan')
                c.execute('UPDATE ppkt_cases SET case_key=?,payload=? WHERE id=?',(number_key(data.caseNumber),json.dumps(data.model_dump(mode='json')),ident))
                audit(c,user,'update_ppkt_case','ppkt',ident)
        except sqlite3.IntegrityError:raise HTTPException(409,'Nomor kasus sudah terdaftar')
        return {'ok':True}

    @app.post('/api/ppkt/import')
    def import_cases(data:CaseImport,user=Depends(auth)):
        admin_access(user)
        unique={}
        for item in data.items:
            key=number_key(item.caseNumber)
            if key in unique and unique[key]!=item:raise HTTPException(422,'Nomor kasus berulang memiliki isi berbeda; periksa berkas sebelum impor')
            unique[key]=item
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            created=skipped=0
            for key,item in unique.items():
                if c.execute('SELECT 1 FROM ppkt_cases WHERE case_key=?',(key,)).fetchone():skipped+=1;continue
                c.execute('INSERT INTO ppkt_cases(case_key,payload,created_by) VALUES(?,?,?)',(key,json.dumps(item.model_dump(mode='json')),user['id']))
                created+=1
            audit(c,user,'import_ppkt_cases','ppkt',None)
        return {'created':created,'skipped':skipped+len(data.items)-len(unique)}
