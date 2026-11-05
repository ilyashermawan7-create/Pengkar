"""PPK Tel-U case management. Case records are separate from activity/survey data."""
import datetime
import json
import re
from fastapi import Depends,HTTPException
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
def initialize(connect):
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS ppkt_cases(id INTEGER PRIMARY KEY,case_key TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')

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
    return result

def register(app,connect,auth,audit):
    def read_access(user):
        if user['role'] not in ('admin','operator','viewer'):raise HTTPException(403,'Ringkasan kasus PPK Tel-U tidak tersedia untuk role ini')
    def admin_access(user):
        if user['role']!='admin':raise HTTPException(403,'Rincian dan impor kasus hanya tersedia untuk Super Admin')
    def selected(c,year,category,status):
        rows=[]
        for row in c.execute('SELECT id,payload FROM ppkt_cases ORDER BY id'):
            item=CaseRecord.model_validate_json(row['payload'])
            if year is not None and item.year!=year:continue
            if category and (item.category or 'Belum diisi')!=category:continue
            if status and bucket(item.status)!=status:continue
            rows.append((row['id'],item))
        return rows
    @app.get('/api/ppkt/summary')
    def get_summary(year:int|None=None,category:str='',status:str='',user=Depends(auth)):
        read_access(user)
        with connect() as c:
            all_rows=selected(c,None,'','')
            records=selected(c,year,category,status)
        return {**summary([item for _,item in records]),'availableYears':sorted({item.year for _,item in all_rows if item.year},reverse=True),'availableCategories':sorted({item.category or 'Belum diisi' for _,item in all_rows})}
    @app.get('/api/ppkt/cases')
    def get_cases(year:int|None=None,category:str='',status:str='',user=Depends(auth)):
        admin_access(user)
        with connect() as c:records=selected(c,year,category,status)
        return {'items':[dict(item.model_dump(mode='json'),id=ident) for ident,item in records]}
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
