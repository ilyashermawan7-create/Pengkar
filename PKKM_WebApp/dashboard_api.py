"""Dashboard API and additive migrations; existing SQLite records remain intact."""
import datetime
import json
import sqlite3
import hashlib
import unicodedata
import threading
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse,JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from dashboard_aggregate import dashboard_stats
from asrama_classification import canonical as dorm_category,suggest as suggest_dorm_category,is_dorm,categorize_legacy
from participant_matching import activity_index,match as match_pending_activity,group_key as pending_group_key

# Only one full dashboard snapshot is assembled/encoded at a time per worker.
SNAPSHOT_LOCK = threading.Lock()

def stream_snapshot(build):
    with SNAPSHOT_LOCK:
        payload=build()
        encoder=json.JSONEncoder(ensure_ascii=False,allow_nan=False,separators=(',',':'))
        parts=[]
        size=0
        for fragment in encoder.iterencode(payload):
            parts.append(fragment)
            size+=len(fragment)
            if size>=65536:
                yield ''.join(parts).encode('utf-8')
                parts=[]
                size=0
        if parts:yield ''.join(parts).encode('utf-8')

SURVEY_SCHEMA = json.loads((Path(__file__).parent/'survey_schema.json').read_text(encoding='utf-8'))

def normalized_name(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())

def average(values):
    available=[value for value in values if value is not None]
    return sum(available)/len(available) if available else None


def initialize(connect):
    with connect() as c:
        columns = {row['name'] for row in c.execute('PRAGMA table_info(users)')}
        if 'dashboard_role' not in columns and c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            filename = c.execute('PRAGMA database_list').fetchone()['file']
            if filename:
                backup = Path(filename).with_name(Path(filename).stem + '.before-dashboard-v2.sqlite3')
                if not backup.exists():
                    # A consistent SQLite backup before the first additive upgrade.
                    backup.touch(mode=0o600, exist_ok=False)
                    try:
                        with sqlite3.connect(backup) as destination:
                            c.backup(destination)
                    except Exception:
                        backup.unlink(missing_ok=True)
                        raise
        for name, default in [('email', ''), ('institution', ''), ('campus', 'Telkom University'), ('dashboard_role', '')]:
            if name not in columns:
                c.execute(f"ALTER TABLE users ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
        c.executescript('''
            CREATE TABLE IF NOT EXISTS activity_details (
                activity_id INTEGER PRIMARY KEY REFERENCES activities(id) ON DELETE CASCADE,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                nim TEXT PRIMARY KEY, nama TEXT NOT NULL, prodi TEXT NOT NULL,
                fakultas TEXT NOT NULL, kampus TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_participants (
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                nim TEXT NOT NULL REFERENCES students(nim),
                PRIMARY KEY(activity_id, nim)
            );
            CREATE TABLE IF NOT EXISTS survey_responses (
                id INTEGER PRIMARY KEY,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS student_directory (
                record_key TEXT PRIMARY KEY, nim TEXT NOT NULL DEFAULT '', nama TEXT NOT NULL DEFAULT '',
                prodi TEXT NOT NULL DEFAULT '', fakultas TEXT NOT NULL DEFAULT '', kampus TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS pending_surveys (
                record_key TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_unidentified_participants (
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                record_key TEXT NOT NULL REFERENCES student_directory(record_key),
                PRIMARY KEY(activity_id,record_key)
            );
            CREATE TABLE IF NOT EXISTS pending_participants (
                record_key TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), payload TEXT NOT NULL
            );
        ''')
        categorize_legacy(c)


class Input(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, str_strip_whitespace=True)


class Student(Input):
    nim: str = Field(min_length=6, max_length=30, pattern=r'^\d+$')
    nama: str = Field(default='', max_length=200)
    prodi: str = Field(default='', max_length=200)
    fakultas: str = Field(default='', max_length=200)
    kampus: str = Field(default='', max_length=200)


class Survey(Input):
    tanggalSurvey: datetime.date | None = None
    nim: str = Field(default='', max_length=30)
    nama: str = Field(default='', max_length=200)
    fakultas: str = Field(default='', max_length=200)
    kampus: str = Field(default='', max_length=200)
    skorMateri: float | None = Field(default=None, ge=1, le=5)
    skorNarasumber: float | None = Field(default=None, ge=1, le=5)
    skorFasilitas: float | None = Field(default=None, ge=1, le=5)
    skorDampakKarakter: float | None = Field(default=None, ge=1, le=5)
    answers: list[float | None] | None = Field(default=None, min_length=20, max_length=20)
    instrument: str = Field(default='', max_length=50)
    submittedAt: str = Field(default='', max_length=100)
    sourceKey: str = Field(default='', max_length=100)
    skorTotal: float | None = Field(default=None, ge=1, le=5)
    skorKepuasan: float | None = Field(default=None, ge=1, le=5)
    saran: str = Field(default='', max_length=5000)

    @model_validator(mode='after')
    def scores(self):
        if self.answers is not None:
            if any(answer is not None and not 1 <= answer <= 5 for answer in self.answers):
                raise ValueError('Jawaban yang terisi wajib berupa angka 1–5')
            for group in SURVEY_SCHEMA['groups']:
                setattr(self,group['field'],average(self.answers[i-1] for i in group['items']))
            self.skorTotal=average(self.answers)
            self.instrument=SURVEY_SCHEMA['version']
        else:
            values=[self.skorMateri,self.skorNarasumber,self.skorFasilitas,self.skorDampakKarakter]
            self.skorTotal=average(values)
            self.skorKepuasan=None
            self.instrument='legacy-4'
        return self


class DashboardActivity(Input):
    navigationGroup: Literal['pengkar','asrama','ppk-telu'] = 'pengkar'
    namaKegiatan: str = Field(default='', max_length=200)
    tanggal: datetime.date | None = None
    tahun: str = Field(default='',pattern=r'^(\d{4})?$',max_length=4)
    sourceKey: str = Field(default='',max_length=100)
    jumlahPeserta: int | None = Field(default=None, ge=0, le=10000000)
    linkEvident: str = Field(default='', max_length=2000)
    tempat: str = Field(default='', max_length=500)
    unitKerjasama: str = Field(default='', max_length=500)
    urusan: str = Field(default='Pengembangan karakter', max_length=200)
    program: Literal['Pengembangan Karakter', 'Asrama'] = 'Pengembangan Karakter'
    kategori: str = Field(default='', max_length=100)
    jenis: str = Field(default='', max_length=200)
    pembicara: str = Field(default='', max_length=500)
    honor: str = Field(default='', max_length=100)
    takPanitia: int | None = Field(default=None, ge=0, le=10000)
    takPeserta: int | None = Field(default=None, ge=0, le=10000)
    laporan: str = Field(default='', max_length=20000)
    targetSurveyKepuasan: float | None = Field(default=None, ge=1, le=5)
    evaluasiMateri: str = Field(default='', max_length=100)
    evaluasiNarasumber: str = Field(default='', max_length=100)
    evaluasiFasilitas: str = Field(default='', max_length=100)
    evaluasiDampak: str = Field(default='', max_length=100)
    catatanSurvey: str = Field(default='', max_length=10000)
    participants: list[Student] = Field(default_factory=list, max_length=10000)
    surveys: list[Survey] = Field(default_factory=list, max_length=10000)


class DashboardStatRequest(Input):
    activityIds: list[int] = Field(default_factory=list,max_length=10000)

class DormCategoryAssignment(Input):
    model_config = ConfigDict(allow_inf_nan=False,str_strip_whitespace=False)
    activityId: int = Field(gt=0)
    category: Literal['Adaptif','Spiritual','Akademik','Sosial']
    expectedCategory: str = Field(max_length=100)

class DormCategoryAssignments(Input):
    items: list[DormCategoryAssignment] = Field(min_length=1,max_length=10000)

class DashboardUser(Input):
    model_config = ConfigDict(allow_inf_nan=False, str_strip_whitespace=False)
    username: str = Field(min_length=3, max_length=60)
    email: str = Field(default='', max_length=254)
    nama: str = Field(min_length=2, max_length=120)
    role: Literal['admin', 'operator', 'verifier', 'pengkar', 'asrama', 'viewer']
    password: str = Field(min_length=12, max_length=512)


class Profile(Input):
    username: str = Field(min_length=3, max_length=60)
    nama: str = Field(min_length=2, max_length=120)
    email: str = Field(default='', max_length=254)
    instansi: str = Field(default='', max_length=300)
    kampus: str = Field(default='Telkom University', max_length=200)


class Password(Input):
    model_config = ConfigDict(str_strip_whitespace=False)
    current_password: str = Field(max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


class ActivityMigration(Input):
    items: list[DashboardActivity] = Field(min_length=1,max_length=10000)


class SurveyMigrationRow(Input):
    activityId: int | None = Field(default=None,gt=0)
    namaKegiatan: str = Field(default='',max_length=200)
    tanggalKegiatan: str = Field(default='',max_length=10)
    importKey: str = Field(default='',max_length=100)
    unresolved: str = Field(default='',max_length=1000)
    sourceRow: int = Field(default=0,ge=0)
    response: Survey


class SurveyMigration(Input):
    items: list[SurveyMigrationRow] = Field(min_length=1,max_length=10000)


class DirectoryStudent(Input):
    directoryId: str = Field(default='',max_length=120)
    nim: str = Field(default='',max_length=30,pattern=r'^(\d{6,30})?$')
    nama: str = Field(default='',max_length=200)
    prodi: str = Field(default='',max_length=200)
    fakultas: str = Field(default='',max_length=200)
    kampus: str = Field(default='',max_length=200)
    sourceKey: str = Field(default='',max_length=100)


class StudentMigration(Input):
    items: list[DirectoryStudent] = Field(min_length=1,max_length=10000)


class ResolveSurvey(Input):
    activityId: int = Field(gt=0)


class ParticipantMigrationRow(Input):
    activityId: int | None = Field(default=None,gt=0)
    namaKegiatan: str = Field(default='',max_length=200)
    tanggalKegiatan: str = Field(default='',max_length=10)
    sourceRow: int = Field(default=0,ge=0)
    importKey: str = Field(default='',max_length=100)
    unresolved: str = Field(default='',max_length=1000)
    student: DirectoryStudent


class ParticipantMigration(Input):
    items: list[ParticipantMigrationRow] = Field(min_length=1,max_length=10000)


class AutoConnectPending(Input):
    dry_run: bool = True
    limit: int = Field(default=1000,ge=1,le=1000)
    groupKey: str = Field(default='',max_length=64)
    activityId: int | None = Field(default=None,gt=0)


def register(app, connect, auth, allow, audit, hash_password, check_password):
    delegated_roles={'pengkar','asrama','viewer'}
    def manage_accounts(user,target_role=None):
        if user['role']=='admin':return
        if user['role']=='operator' and (target_role is None or target_role in delegated_roles):return
        raise HTTPException(403,'Operator hanya dapat mengelola Operator Pengkar, Operator Asrama, dan Viewer')

    def migration_access(user=Depends(auth)):
        if user['role']=='operator':raise HTTPException(403,'Menu migrasi tidak tersedia untuk Operator KKA')

    def visible(user, program):
        return user['role'] not in ('pengkar', 'asrama') or program == ('Asrama' if user['role'] == 'asrama' else 'Pengembangan Karakter')

    def profile(user):
        return dict(username=user['username'], nama=user['full_name'], role=user['role'],
                    email=user['email'], instansi=user['institution'], kampus=user['campus'])

    def converted(row, details, responses):
        data = dict(row)
        date = datetime.date.fromisoformat(data['tanggal']) if data['tanggal'] else None
        result = dict(id=data['id'], namaKegiatan=data['nama_kegiatan'], tanggal=data['tanggal'],
                      program=data['program'], kategori=data['kategori'], tempat=data['tempat'],
                      unitKerjasama=data['unit_kerjasama'], pembicara=data['pembicara'],
                      jumlahPeserta=data['jumlah_peserta'], laporan=data['laporan'],
                      linkEvident=data['link_eviden'], urusan=data['program'], jenis=data['kategori'],
                      honor='', takPanitia=None, takPeserta=None, targetSurveyKepuasan=None,
                      evaluasiMateri='', evaluasiNarasumber='', evaluasiFasilitas='', evaluasiDampak='', catatanSurvey='')
        extras = details.get(data['id'], {})
        for key in ('jenis','honor','takPanitia','takPeserta','targetSurveyKepuasan','evaluasiMateri',
                    'evaluasiNarasumber','evaluasiFasilitas','evaluasiDampak','catatanSurvey','urusan','jumlahPeserta','sourceKey','navigationGroup'):
            if key in extras:
                result[key] = extras[key]
        result.setdefault('navigationGroup','pengkar')
        result.update(id=data['id'], tahun=str(date.year) if date else extras.get('tahun',''), triwulan=f'TW{(date.month-1)//3+1}' if date else '')
        full = [r for r in responses if r.get('answers') is not None]
        scores = [r.get('skorTotal') for r in (full or responses) if r.get('skorTotal') is not None]
        legacy = [data[k] for k in ('skor_materi', 'skor_narasumber', 'skor_fasilitas', 'skor_dampak') if data.get(k) is not None]
        result['skorSurvey'] = round(sum(scores)/len(scores), 2) if scores else (round(sum(legacy)/len(legacy), 2) if legacy else result.get('targetSurveyKepuasan'))
        return result

    def build_snapshot(user,compact=False):
        with connect() as c:
            rows = c.execute('''SELECT a.*,e.skor_materi,e.skor_narasumber,e.skor_fasilitas,e.skor_dampak
                FROM activities a LEFT JOIN evaluations e ON e.activity_id=a.id ORDER BY a.tanggal DESC,a.id DESC''').fetchall()
            rows = [r for r in rows if visible(user, r['program'])]
            ids = {r['id'] for r in rows}
            details = {r['activity_id']: json.loads(r['payload']) for r in c.execute('SELECT * FROM activity_details') if r['activity_id'] in ids}
            if compact:
                activities=[converted(row,details,[]) for row in rows]
                scores={row['activity_id']:row for row in c.execute("""SELECT activity_id,
                    SUM(CASE WHEN json_array_length(payload,'$.answers')=20 THEN 1 ELSE 0 END) AS full_count,
                    AVG(CASE WHEN json_array_length(payload,'$.answers')=20 THEN json_extract(payload,'$.skorTotal') END) AS full_score,
                    AVG(json_extract(payload,'$.skorTotal')) AS legacy_score FROM survey_responses GROUP BY activity_id""") if row['activity_id'] in ids}
                for activity in activities:
                    score=scores.get(activity['id'])
                    if score:
                        value=score['full_score'] if score['full_count'] else score['legacy_score']
                        if value is not None:activity['skorSurvey']=round(value,2)
                users=[]
                if user['role'] in ('admin','operator'):
                    users=[dict(id=row['id'],username=row['username'],nama=row['full_name'],email=row['email'],role=row['dashboard_role'] or row['role'],status='Aktif' if row['active'] else 'Nonaktif') for row in c.execute('SELECT * FROM users ORDER BY id') if user['role']=='admin' or (row['dashboard_role'] or row['role']) in delegated_roles]
                fields=('id','namaKegiatan','tanggal','tahun','triwulan','program','kategori','urusan','jenis','navigationGroup','jumlahPeserta','skorSurvey')
                activities=[{key:item.get(key) for key in fields} for item in activities]
                return dict(compact=True,activities=activities,students=[],surveys=[],masterStudents=[],pendingSurveys=[],pendingParticipants=[],adminList=users,profile=profile(user))
            surveys = [dict(Survey.model_validate_json(r['payload']).model_dump(mode='json'), id=r['id'], activityId=r['activity_id']) for r in c.execute('SELECT * FROM survey_responses') if r['activity_id'] in ids]
            by_activity = {}
            for survey in surveys:
                by_activity.setdefault(survey['activityId'], []).append(survey)
            activities = [converted(r, details, by_activity.get(r['id'], [])) for r in rows]
            names = {a['id']: a['namaKegiatan'] for a in activities}
            for survey in surveys:
                survey['namaKegiatan'] = names[survey['activityId']]
            students = [dict(r) for r in c.execute('''SELECT s.*,p.activity_id AS activityId
                FROM activity_participants p JOIN students s ON s.nim=p.nim''') if r['activityId'] in ids]
            students.extend(dict(row,directoryId=row['record_key']) for row in c.execute('''SELECT d.*,p.activity_id AS activityId
                FROM activity_unidentified_participants p JOIN student_directory d ON d.record_key=p.record_key''') if row['activityId'] in ids)
            master=[]
            if user['role']=='admin':
                directory=[dict(r) for r in c.execute('SELECT * FROM student_directory ORDER BY nama,record_key')]
                known={row['nim'] for row in directory if row['nim']}
                master=[dict(row,directoryId=row['record_key']) for row in directory]
                master.extend(dict(row,directoryId='nim:'+row['nim']) for row in c.execute('SELECT * FROM students') if row['nim'] not in known)
            pending=[dict(id=row['record_key'],**json.loads(row['payload'])) for row in c.execute('SELECT * FROM pending_surveys WHERE user_id=?',(user['id'],))]
            pending_participants=[dict(id=row['record_key'],**json.loads(row['payload'])) for row in c.execute('SELECT * FROM pending_participants WHERE user_id=?',(user['id'],))]
            users = []
            if user['role'] in ('admin','operator'):
                users = [dict(id=r['id'], username=r['username'], nama=r['full_name'], email=r['email'],
                              role=r['dashboard_role'] or r['role'], status='Aktif' if r['active'] else 'Nonaktif')
                         for r in c.execute('SELECT * FROM users ORDER BY id') if user['role']=='admin' or (r['dashboard_role'] or r['role']) in delegated_roles]
            return dict(activities=activities, students=students, masterStudents=master,pendingSurveys=pending,pendingParticipants=pending_participants,surveys=surveys, adminList=users, profile=profile(user))

    @app.get('/api/dashboard')
    def snapshot(compact:bool=False,user=Depends(auth)):
        # Bypass FastAPI's recursive jsonable_encoder and whole-body JSON buffer.
        # Large participant imports previously produced multiple copies in RAM.
        if compact:return JSONResponse(build_snapshot(user,True),headers={'Cache-Control':'no-store'})
        return StreamingResponse(stream_snapshot(lambda:build_snapshot(user,compact)),media_type='application/json',headers={'Cache-Control':'no-store'})

    @app.get('/api/dashboard/search')
    def search_dashboard_students(query:str='',user=Depends(auth)):
        query=query.strip()
        if len(query)>200:raise HTTPException(422,'Pencarian maksimal 200 karakter')
        if not query:return {'activityIds':[]}
        with connect() as c:
            allowed={row['id'] for row in c.execute('SELECT id,program FROM activities') if visible(user,row['program'])}
            ids={row['activity_id'] for row in c.execute("SELECT p.activity_id FROM activity_participants p JOIN students s ON s.nim=p.nim WHERE instr(lower(s.nim),lower(?))>0 OR instr(lower(s.nama),lower(?))>0",(query,query)) if row['activity_id'] in allowed}
            ids.update(row['activity_id'] for row in c.execute("SELECT p.activity_id FROM activity_unidentified_participants p JOIN student_directory s ON s.record_key=p.record_key WHERE instr(lower(s.nim),lower(?))>0 OR instr(lower(s.nama),lower(?))>0",(query,query)) if row['activity_id'] in allowed)
        return {'activityIds':sorted(ids)}

    @app.post('/api/dashboard/stats')
    def get_dashboard_stats(data:DashboardStatRequest,user=Depends(auth)):
        with connect() as c:
            allowed={row['id'] for row in c.execute('SELECT id,program FROM activities') if visible(user,row['program'])}
            if not set(data.activityIds).issubset(allowed):raise HTTPException(403,'Kegiatan tidak tersedia atau di luar hak akses. Muat ulang dashboard')
            return dashboard_stats(c,data.activityIds)

    def write_surveys(c, ident, surveys, user, notes=''):
        previous = c.execute('SELECT count(*) FROM survey_responses WHERE activity_id=?', (ident,)).fetchone()[0]
        c.execute('DELETE FROM survey_responses WHERE activity_id=?', (ident,))
        for survey in surveys:
            c.execute('INSERT INTO survey_responses(activity_id,payload) VALUES(?,?)', (ident,json.dumps(survey.model_dump(mode='json'))))
        if surveys:
            measured=[s for s in surveys if s.answers is not None] or surveys
            means = [average(getattr(s,k) for s in measured) for k in ('skorMateri','skorNarasumber','skorFasilitas','skorDampakKarakter')]
            c.execute('''INSERT INTO evaluations(activity_id,jumlah_responden,skor_materi,skor_narasumber,skor_fasilitas,skor_dampak,temuan,updated_by)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(activity_id) DO UPDATE SET jumlah_responden=excluded.jumlah_responden,
                skor_materi=excluded.skor_materi,skor_narasumber=excluded.skor_narasumber,skor_fasilitas=excluded.skor_fasilitas,
                skor_dampak=excluded.skor_dampak,temuan=excluded.temuan,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP''',
                      (ident,len(surveys),*means,notes,user['id']))
            c.execute("UPDATE activities SET status='Dievaluasi' WHERE id=?", (ident,))
        elif previous:
            c.execute('DELETE FROM evaluations WHERE activity_id=?', (ident,))
            c.execute("UPDATE activities SET status='Terlaksana' WHERE id=?", (ident,))

    def save(data, user, ident=None, connection=None):
        allow(user, data.program)
        participants = {s.nim: s for s in data.participants}
        if participants and data.jumlahPeserta is not None and data.jumlahPeserta < len(participants):
            raise HTTPException(422, 'Jumlah peserta tidak boleh lebih kecil dari jumlah NIM unik pada berkas peserta.')
        if connection is None:
            with connect() as c:
                c.execute('BEGIN IMMEDIATE')
                return save(data,user,ident,connection=c)
        c=connection
        if ident is not None:
            old = c.execute('SELECT * FROM activities WHERE id=?', (ident,)).fetchone()
            if not old:
                raise HTTPException(404, 'Kegiatan tidak ditemukan')
            allow(user, old['program'])
        values = (data.namaKegiatan, data.tanggal.isoformat() if data.tanggal else '', data.program, data.kategori, data.tempat,
                  data.unitKerjasama, data.pembicara, data.jumlahPeserta or 0, data.laporan, data.linkEvident)
        if ident is None:
            cur = c.execute('''INSERT INTO activities(nama_kegiatan,tanggal,program,kategori,tempat,unit_kerjasama,
                pembicara,jumlah_peserta,laporan,link_eviden,status,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', values+('Terlaksana' if data.namaKegiatan and data.tanggal else 'Draft',user['id']))
            ident = cur.lastrowid
        else:
            c.execute('''UPDATE activities SET nama_kegiatan=?,tanggal=?,program=?,kategori=?,tempat=?,unit_kerjasama=?,
                pembicara=?,jumlah_peserta=?,laporan=?,link_eviden=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''', values+(ident,))
        payload = data.model_dump(mode='json', exclude={'participants','surveys'})
        c.execute('INSERT INTO activity_details VALUES(?,?) ON CONFLICT(activity_id) DO UPDATE SET payload=excluded.payload', (ident,json.dumps(payload)))
        c.execute('DELETE FROM activity_participants WHERE activity_id=?', (ident,))
        for student in participants.values():
            c.execute('''INSERT INTO students VALUES(?,?,?,?,?) ON CONFLICT(nim) DO UPDATE SET
                nama=CASE WHEN excluded.nama<>'' THEN excluded.nama ELSE students.nama END,
                prodi=CASE WHEN excluded.prodi<>'' THEN excluded.prodi ELSE students.prodi END,
                fakultas=CASE WHEN excluded.fakultas<>'' THEN excluded.fakultas ELSE students.fakultas END,
                kampus=CASE WHEN excluded.kampus<>'' THEN excluded.kampus ELSE students.kampus END''',
                      (student.nim, student.nama, student.prodi, student.fakultas, student.kampus))
            c.execute('INSERT INTO activity_participants VALUES(?,?)', (ident,student.nim))
        write_surveys(c, ident, data.surveys, user, data.catatanSurvey)
        audit(c,user,'save','activity',ident)
        return {'id':ident}

    @app.post('/api/dashboard/activities', status_code=201)
    def create(data: DashboardActivity, user=Depends(auth)):
        return save(data,user)

    @app.post('/api/migrate/students', dependencies=[Depends(migration_access)])
    def migrate_students(data: StudentMigration, user=Depends(auth)):
        if user['role'] not in ('admin','operator'):
            raise HTTPException(403,'Master mahasiswa hanya dikelola Super Admin atau Operator KKA')
        created=updated=skipped=0
        fields=('nim','nama','prodi','fakultas','kampus')
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            for student in data.items:
                values={field:getattr(student,field) for field in fields}
                if not any(values.values()):
                    skipped+=1
                    continue
                specified=c.execute('SELECT * FROM student_directory WHERE record_key=?',(student.directoryId,)).fetchone() if student.directoryId else None
                if student.directoryId and not specified:raise HTTPException(422,'ID Master tidak ditemukan; gunakan ID dari ekspor master aplikasi ini')
                record_key='nim:'+student.nim if student.nim else student.directoryId or 'source:'+(student.sourceKey or hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest())
                existing=c.execute('SELECT * FROM student_directory WHERE record_key=?',(record_key,)).fetchone()
                cached=c.execute('SELECT * FROM students WHERE nim=?',(student.nim,)).fetchone() if student.nim else None
                previous=existing or specified or cached
                merged={field:values[field] or next((row[field] for row in (existing,specified,cached) if row and row[field]),'') for field in fields}
                if previous and all(previous[field]==merged[field] for field in fields):skipped+=1
                elif previous:updated+=1
                else:created+=1
                c.execute('''INSERT INTO student_directory VALUES(?,?,?,?,?,?) ON CONFLICT(record_key) DO UPDATE SET
                    nim=excluded.nim,nama=excluded.nama,prodi=excluded.prodi,fakultas=excluded.fakultas,kampus=excluded.kampus''',
                    (record_key,*(merged[field] for field in fields)))
                if student.nim:
                    c.execute('''INSERT INTO students VALUES(?,?,?,?,?) ON CONFLICT(nim) DO UPDATE SET
                        nama=excluded.nama,prodi=excluded.prodi,fakultas=excluded.fakultas,kampus=excluded.kampus''',tuple(merged[field] for field in fields))
                if specified and specified['record_key']!=record_key:
                    for link in c.execute('SELECT activity_id FROM activity_unidentified_participants WHERE record_key=?',(specified['record_key'],)).fetchall():
                        c.execute('INSERT INTO activity_participants VALUES(?,?) ON CONFLICT DO NOTHING',(link['activity_id'],merged['nim']))
                    c.execute('DELETE FROM activity_unidentified_participants WHERE record_key=?',(specified['record_key'],))
                    c.execute('DELETE FROM student_directory WHERE record_key=?',(specified['record_key'],))
            audit(c,user,'migrate_students','migration',None)
        return {'created':created,'updated':updated,'skipped':skipped}

    def apply_participants(c,items,user):
        allow(user)
        added=skipped=pending_count=0
        touched=set()
        for item in items:
            values={key:getattr(item.student,key) for key in ('nim','nama','prodi','fakultas','kampus')}
            if not any(values.values()):
                skipped+=1
                continue
            if item.activityId is None:
                payload=item.model_dump(mode='json')
                record_key=hashlib.sha256((str(user['id'])+':'+(item.importKey or json.dumps(payload,sort_keys=True))).encode()).hexdigest()
                c.execute('INSERT INTO pending_participants VALUES(?,?,?) ON CONFLICT(record_key) DO NOTHING',(record_key,user['id'],json.dumps(payload)))
                pending_count+=1
                continue
            activity=c.execute('SELECT * FROM activities WHERE id=?',(item.activityId,)).fetchone()
            if not activity:raise HTTPException(422,f'Baris {item.sourceRow}: kegiatan tidak ditemukan')
            allow(user,activity['program'])
            if item.namaKegiatan and normalized_name(item.namaKegiatan)!=normalized_name(activity['nama_kegiatan']):
                raise HTTPException(422,f'Baris {item.sourceRow}: nama kegiatan tidak sesuai ID kegiatan')
            specified=c.execute('SELECT * FROM student_directory WHERE record_key=?',(item.student.directoryId,)).fetchone() if item.student.directoryId else None
            if item.student.directoryId and not specified:raise HTTPException(422,f'Baris {item.sourceRow}: ID Master tidak ditemukan')
            if specified:
                values={key:values[key] or specified[key] for key in values}
                item.student.nim=values['nim']
            if item.student.nim:
                cached=c.execute('SELECT * FROM students WHERE nim=?',(item.student.nim,)).fetchone()
                directory=c.execute('SELECT * FROM student_directory WHERE record_key=?',('nim:'+item.student.nim,)).fetchone()
                merged={key:values[key] or next((row[key] for row in (cached,directory) if row and row[key]),'') for key in values}
                c.execute('''INSERT INTO students VALUES(?,?,?,?,?) ON CONFLICT(nim) DO UPDATE SET
                    nama=excluded.nama,prodi=excluded.prodi,fakultas=excluded.fakultas,kampus=excluded.kampus''',tuple(merged.values()))
                result=c.execute('INSERT INTO activity_participants VALUES(?,?) ON CONFLICT DO NOTHING',(item.activityId,item.student.nim))
            else:
                source=item.student.sourceKey or item.importKey or hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
                record_key=specified['record_key'] if specified else 'source:'+source
                existing=c.execute('SELECT * FROM student_directory WHERE record_key=?',(record_key,)).fetchone()
                merged={key:values[key] or (existing[key] if existing else '') for key in values}
                c.execute('''INSERT INTO student_directory VALUES(?,?,?,?,?,?) ON CONFLICT(record_key) DO UPDATE SET
                    nama=excluded.nama,prodi=excluded.prodi,fakultas=excluded.fakultas,kampus=excluded.kampus''',(record_key,*merged.values()))
                result=c.execute('INSERT INTO activity_unidentified_participants VALUES(?,?) ON CONFLICT DO NOTHING',(item.activityId,record_key))
            if result.rowcount:added+=1
            else:skipped+=1
            touched.add(item.activityId)
        for ident in touched:
            count=c.execute('SELECT count(*) FROM activity_participants WHERE activity_id=?',(ident,)).fetchone()[0]
            count+=c.execute('SELECT count(*) FROM activity_unidentified_participants WHERE activity_id=?',(ident,)).fetchone()[0]
            current=c.execute('SELECT jumlah_peserta FROM activities WHERE id=?',(ident,)).fetchone()[0]
            count=max(count,current)
            c.execute('UPDATE activities SET jumlah_peserta=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(count,ident))
            details=c.execute('SELECT payload FROM activity_details WHERE activity_id=?',(ident,)).fetchone()
            payload=json.loads(details['payload']) if details else {}
            payload['jumlahPeserta']=count
            c.execute('INSERT INTO activity_details VALUES(?,?) ON CONFLICT(activity_id) DO UPDATE SET payload=excluded.payload',(ident,json.dumps(payload)))
        return {'created':added,'skipped':skipped,'pending':pending_count,'activities':len(touched)}

    @app.post('/api/migrate/participants', dependencies=[Depends(migration_access)])
    def migrate_participants(data: ParticipantMigration,user=Depends(auth)):
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            result=apply_participants(c,data.items,user)
            audit(c,user,'migrate_participants','migration',None)
        return result

    def connect_pending(data,user,kind):
        surveys=kind=='surveys'
        table='pending_surveys' if surveys else 'pending_participants'
        model=SurveyMigrationRow if surveys else ParticipantMigrationRow
        if surveys:
            if user['role']=='viewer':raise HTTPException(403,'Akses baca saja')
        else:allow(user)
        with connect() as c:
            if not data.dry_run:c.execute('BEGIN IMMEDIATE')
            allowed=[dict(row) for row in c.execute('SELECT id,nama_kegiatan,tanggal,program FROM activities') if visible(user,row['program'])]
            index=activity_index(allowed)
            records=[]
            groups={}
            summary=dict(total=0,matched=0,ambiguous=0,unmatched=0,date_conflict=0,blank=0,invalid=0)
            for row in c.execute(f'SELECT * FROM {table} WHERE user_id=? ORDER BY rowid',(user['id'],)):
                try:item=model.model_validate_json(row['payload'])
                except ValueError:
                    summary['total']+=1;summary['invalid']+=1
                    continue
                target,status=match_pending_activity(item,index)
                key=pending_group_key(row['record_key'],item)
                summary['total']+=1;summary[status]+=1
                if key not in groups:
                    groups[key]={'key':key,'name':item.namaKegiatan,'date':item.tanggalKegiatan,
                                 'count':0,'status':status,'targetId':target['id'] if target else None,
                                 'targetName':target['nama_kegiatan'] if target else '', 'canGroup':bool(item.namaKegiatan),'examples':[]}
                groups[key]['count']+=1
                identity=item.response if surveys else item.student
                example=identity.nama or identity.nim
                if example and len(groups[key]['examples'])<3:groups[key]['examples'].append(example)
                records.append((row['record_key'],item,key,target))
            if data.dry_run:
                return {'summary':summary,'groups':sorted(groups.values(),key=lambda group:-group['count'])}
            if bool(data.groupKey)!=bool(data.activityId):
                raise HTTPException(422,'Pilih kelompok data dan kegiatan tujuan bersamaan')
            forced=None
            if data.activityId:
                forced=next((activity for activity in allowed if activity['id']==data.activityId),None)
                if not forced:raise HTTPException(403,'Kegiatan tujuan tidak dapat diakses')
                if data.groupKey not in groups:raise HTTPException(409,'Kelompok sudah diproses atau berubah; periksa ulang daftar')
            eligible=[record for record in records if record[2]==data.groupKey] if forced else [record for record in records if record[3]]
            selected=eligible[:data.limit]
            if not selected:return {'processed':0,'created':0,'skipped':0,'remainingMatched':summary['matched'],'remainingGroup':len(eligible),'remaining':summary['total']}
            items=[]
            for record_id,item,key,target in selected:
                target=forced or target
                item.activityId=target['id']
                item.namaKegiatan=target['nama_kegiatan']
                items.append(item)
            result=apply_survey_migration(c,items,user) if surveys else apply_participants(c,items,user)
            c.executemany(f'DELETE FROM {table} WHERE record_key=? AND user_id=?',[(record[0],user['id']) for record in selected])
            audit(c,user,'bulk_connect_'+kind,'activity',forced['id'] if forced else None)
            matched_processed=sum(record[3] is not None for record in selected)
            return {**result,'processed':len(selected),'remainingMatched':summary['matched']-matched_processed,
                    'remainingGroup':len(eligible)-len(selected),'remaining':summary['total']-len(selected)}

    @app.post('/api/migrate/participants/pending/auto-connect', dependencies=[Depends(migration_access)])
    def auto_connect_participants(data: AutoConnectPending,user=Depends(auth)):
        return connect_pending(data,user,'participants')

    @app.post('/api/migrate/participants/pending/{record_key}/resolve', dependencies=[Depends(migration_access)])
    def resolve_pending_participants(record_key: str,data: ResolveSurvey,user=Depends(auth)):
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            record=c.execute('SELECT * FROM pending_participants WHERE record_key=? AND user_id=?',(record_key,user['id'])).fetchone()
            target=c.execute('SELECT * FROM activities WHERE id=?',(data.activityId,)).fetchone()
            if not record:raise HTTPException(404,'Peserta tertunda tidak ditemukan')
            if not target:raise HTTPException(422,'Kegiatan tidak ditemukan')
            item=ParticipantMigrationRow.model_validate_json(record['payload'])
            item.activityId=data.activityId
            item.namaKegiatan=target['nama_kegiatan']
            result=apply_participants(c,[item],user)
            c.execute('DELETE FROM pending_participants WHERE record_key=?',(record_key,))
            audit(c,user,'resolve_participant','activity',data.activityId)
        return result

    @app.post('/api/migrate/activities', dependencies=[Depends(migration_access)])
    def migrate_activities(data: ActivityMigration, user=Depends(auth)):
        for item in data.items:
            allow(user,item.program)
            if item.participants or item.surveys:
                raise HTTPException(422,'Impor kegiatan hanya berisi data kegiatan; gunakan impor peserta/survei terpisah.')
        created=skipped=0
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            details={row['activity_id']:json.loads(row['payload']) for row in c.execute('SELECT * FROM activity_details')}
            def activity_key(name,date,program,year,source):
                if name and (date or year):
                    return ('named',normalized_name(name),date,program,year)
                return ('source',source)
            keys=set()
            for row in c.execute('SELECT id,nama_kegiatan,tanggal,program FROM activities'):
                extra=details.get(row['id'],{})
                keys.add(activity_key(row['nama_kegiatan'],row['tanggal'],row['program'],row['tanggal'][:4] or extra.get('tahun',''),extra.get('sourceKey','existing:'+str(row['id']))))
            for item in data.items:
                date=item.tanggal.isoformat() if item.tanggal else ''
                source=item.sourceKey or hashlib.sha256(item.model_dump_json().encode()).hexdigest()
                item.sourceKey=source
                key=activity_key(item.namaKegiatan,date,item.program,date[:4] or item.tahun,source)
                if key in keys:
                    skipped+=1
                    continue
                save(item,user,connection=c)
                keys.add(key)
                created+=1
            audit(c,user,'migrate_activities','migration',None)
        return {'created':created,'skipped':skipped}

    def survey_key(response):
        record=response.model_dump(mode='json')
        # Metadata spelling changes do not create a second response for the same NIM.
        identity={k:record[k] for k in ('tanggalSurvey','submittedAt','nim','answers','saran')}
        if not response.nim:
            identity['nama']=normalized_name(response.nama)
            if not response.submittedAt:
                identity['sourceKey']=response.sourceKey
        if response.answers is None:
            identity['scores']=[response.skorMateri,response.skorNarasumber,response.skorFasilitas,response.skorDampakKarakter]
        return hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def apply_survey_migration(c,items,user):
        if user['role']=='viewer':raise HTTPException(403,'Akses baca saja')
        created=skipped=pending_count=0
        grouped={}
        for item in items:
            if item.activityId is None:
                payload=item.model_dump(mode='json')
                record_key=hashlib.sha256((str(user['id'])+':'+(item.importKey or json.dumps(payload,sort_keys=True))).encode()).hexdigest()
                c.execute('INSERT INTO pending_surveys VALUES(?,?,?) ON CONFLICT(record_key) DO NOTHING',(record_key,user['id'],json.dumps(payload)))
                pending_count+=1
                continue
            row=c.execute('SELECT nama_kegiatan,program FROM activities WHERE id=?',(item.activityId,)).fetchone()
            if not row or not visible(user,row['program']):
                raise HTTPException(422,f'Baris {item.sourceRow}: kegiatan tidak ditemukan atau tidak dapat diakses')
            if item.namaKegiatan and normalized_name(item.namaKegiatan)!=normalized_name(row['nama_kegiatan']):
                raise HTTPException(422,f'Baris {item.sourceRow}: nama kegiatan tidak sesuai ID kegiatan')
            grouped.setdefault(item.activityId,[]).append(item.response)
        for ident, imported in grouped.items():
            existing=[Survey.model_validate_json(row['payload']) for row in c.execute('SELECT payload FROM survey_responses WHERE activity_id=?',(ident,))]
            keys={survey_key(response) for response in existing}
            additions=[]
            for response in imported:
                fingerprint=survey_key(response)
                if fingerprint in keys:
                    skipped+=1
                    continue
                additions.append(response)
                keys.add(fingerprint)
                created+=1
            if additions:
                write_surveys(c,ident,existing+additions,user)
        return {'created':created,'skipped':skipped,'pending':pending_count,'activities':len(grouped)}

    @app.post('/api/migrate/surveys', dependencies=[Depends(migration_access)])
    def migrate_surveys(data: SurveyMigration,user=Depends(auth)):
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            result=apply_survey_migration(c,data.items,user)
            audit(c,user,'migrate_surveys','migration',None)
        return result

    @app.post('/api/migrate/surveys/pending/auto-connect', dependencies=[Depends(migration_access)])
    def auto_connect_surveys(data: AutoConnectPending,user=Depends(auth)):
        return connect_pending(data,user,'surveys')

    @app.post('/api/migrate/surveys/pending/{record_key}/resolve', dependencies=[Depends(migration_access)])
    def resolve_pending(record_key: str, data: ResolveSurvey, user=Depends(auth)):
        if user['role']=='viewer':raise HTTPException(403,'Akses baca saja')
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            pending=c.execute('SELECT * FROM pending_surveys WHERE record_key=? AND user_id=?',(record_key,user['id'])).fetchone()
            target=c.execute('SELECT * FROM activities WHERE id=?',(data.activityId,)).fetchone()
            if not pending:raise HTTPException(404,'Data tertunda tidak ditemukan')
            if not target or not visible(user,target['program']):raise HTTPException(403,'Kegiatan tidak dapat diakses')
            response=SurveyMigrationRow.model_validate_json(pending['payload']).response
            existing=[Survey.model_validate_json(row['payload']) for row in c.execute('SELECT payload FROM survey_responses WHERE activity_id=?',(data.activityId,))]
            duplicate=survey_key(response) in {survey_key(item) for item in existing}
            if not duplicate:write_surveys(c,data.activityId,existing+[response],user)
            c.execute('DELETE FROM pending_surveys WHERE record_key=?',(record_key,))
            audit(c,user,'resolve_survey','activity',data.activityId)
        return {'created':0 if duplicate else 1,'skipped':1 if duplicate else 0}

    @app.put('/api/dashboard/activities/{ident}')
    def update(ident: int, data: DashboardActivity, user=Depends(auth)):
        return save(data,user,ident)

    @app.put('/api/dashboard/activities/{ident}/surveys')
    def replace_surveys(ident: int, data: list[Survey], user=Depends(auth)):
        if len(data) > 10000:
            raise HTTPException(422, 'Maksimal 10.000 respons per kegiatan')
        if user['role'] == 'viewer':
            raise HTTPException(403, 'Akses baca saja')
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT program FROM activities WHERE id=?', (ident,)).fetchone()
            if not row:
                raise HTTPException(404, 'Kegiatan tidak ditemukan')
            if not visible(user,row['program']):
                raise HTTPException(403, 'Tidak berwenang pada program ini')
            write_surveys(c, ident, data, user)
            audit(c,user,'import_survey','activity',ident)
        return {'ok':True}

    def dorm_records(c,user):
        if user['role'] not in ('admin','asrama'):
            raise HTTPException(403,'Kategorisasi data lama Asrama hanya untuk Super Admin dan Operator Asrama')
        records=[]
        for row in c.execute('SELECT a.*,d.payload AS details FROM activities a LEFT JOIN activity_details d ON d.activity_id=a.id ORDER BY a.nama_kegiatan,a.id'):
            details=json.loads(row['details']) if row['details'] else {}
            if not visible(user,row['program']) or not is_dorm(row,details):continue
            current=dorm_category(row['kategori'])
            suggestion,reason=(current,'Kategori sudah diisi; ejaan dapat diseragamkan') if current else suggest_dorm_category(row['nama_kegiatan'],details.get('jenis',''),row['laporan'])
            records.append({'id':row['id'],'name':row['nama_kegiatan'],'date':row['tanggal'],'current':row['kategori'],
                            'suggestion':suggestion,'reason':reason,'complete':row['kategori'] in ('Adaptif','Spiritual','Akademik','Sosial')})
        return records

    @app.get('/api/dashboard/asrama/categories')
    def preview_dorm_categories(user=Depends(auth)):
        with connect() as c:records=dorm_records(c,user)
        return {'items':records,'total':len(records),'complete':sum(row['complete'] for row in records)}

    @app.post('/api/dashboard/asrama/categories')
    def apply_dorm_categories(data:DormCategoryAssignments,user=Depends(auth)):
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            allowed={row['id']:row for row in dorm_records(c,user)}
            if len({item.activityId for item in data.items})!=len(data.items):raise HTTPException(422,'ID kegiatan berulang dalam permintaan')
            # Validate the entire batch before updating any record.
            for item in data.items:
                row=allowed.get(item.activityId)
                if not row:raise HTTPException(403,'Kegiatan bukan Asrama atau di luar hak akses')
                if row['current']!=item.expectedCategory:raise HTTPException(409,'Kategori berubah sejak diperiksa. Muat ulang daftar terlebih dahulu')
                if row['complete'] and row['current']!=item.category:raise HTTPException(409,'Kategori yang sudah lengkap tidak ditimpa melalui kategorisasi data lama')
            c.execute('CREATE TABLE IF NOT EXISTS asrama_category_history(id INTEGER PRIMARY KEY,activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,old_category TEXT NOT NULL,new_category TEXT NOT NULL,changed_by INTEGER,at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
            updated=0
            for item in data.items:
                row=allowed[item.activityId]
                if row['current']==item.category:continue
                c.execute('INSERT INTO asrama_category_history(activity_id,old_category,new_category,changed_by) VALUES(?,?,?,?)',(item.activityId,row['current'],item.category,user['id']))
                c.execute('UPDATE activities SET kategori=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(item.category,item.activityId))
                audit(c,user,'categorize_asrama','activity',item.activityId)
                updated+=1
        return {'updated':updated}

    @app.post('/api/dashboard/users', status_code=201)
    def create_user(data: DashboardUser, user=Depends(auth)):
        manage_accounts(user,data.role)
        role = {'operator':'pengkar', 'verifier':'viewer'}.get(data.role,data.role)
        try:
            with connect() as c:
                cur = c.execute('''INSERT INTO users(username,password_hash,full_name,role,email,dashboard_role)
                    VALUES(?,?,?,?,?,?)''', (data.username,hash_password(data.password),data.nama,role,data.email,data.role if data.role in ('operator','verifier') else ''))
                audit(c,user,'create','user',cur.lastrowid)
                return {'id':cur.lastrowid}
        except sqlite3.IntegrityError:
            raise HTTPException(409,'Username sudah digunakan')

    @app.delete('/api/dashboard/users/{ident}')
    def deactivate_user(ident: int, user=Depends(auth)):
        manage_accounts(user)
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            target = c.execute('SELECT * FROM users WHERE id=? AND active=1', (ident,)).fetchone()
            if not target:
                raise HTTPException(404,'Akun aktif tidak ditemukan')
            manage_accounts(user,target['dashboard_role'] or target['role'])
            if ident == user['id']:
                raise HTTPException(409,'Tidak dapat menonaktifkan akun yang sedang digunakan')
            if target['role'] == 'admin' and c.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
                raise HTTPException(409,'Administrator terakhir harus tetap aktif')
            c.execute('UPDATE users SET active=0 WHERE id=?', (ident,))
            c.execute('DELETE FROM sessions WHERE user_id=?', (ident,))
            audit(c,user,'deactivate','user',ident)
        return {'ok':True}

    @app.put('/api/profile')
    def update_profile(data: Profile, user=Depends(auth)):
        try:
            with connect() as c:
                c.execute('UPDATE users SET username=?,full_name=?,email=?,institution=?,campus=? WHERE id=?',
                          (data.username,data.nama,data.email,data.instansi,data.kampus,user['id']))
                audit(c,user,'update','profile',user['id'])
        except sqlite3.IntegrityError:
            raise HTTPException(409,'Username sudah digunakan')
        return {'ok':True}

    @app.put('/api/profile/password')
    def change_password(data: Password, user=Depends(auth)):
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            stored = c.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()[0]
            if not check_password(data.current_password,stored):
                raise HTTPException(403,'Password saat ini tidak sesuai')
            c.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(data.new_password),user['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
            audit(c,user,'change_password','user',user['id'])
        return {'ok':True}
