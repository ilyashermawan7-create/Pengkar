"""Dashboard API and additive migrations; existing SQLite records remain intact."""
import datetime
import json
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field


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
        ''')


class Input(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, str_strip_whitespace=True)


class Student(Input):
    nim: str = Field(min_length=6, max_length=30, pattern=r'^\d+$')
    nama: str = Field(min_length=1, max_length=200)
    prodi: str = Field(default='', max_length=200)
    fakultas: str = Field(default='', max_length=200)
    kampus: str = Field(default='', max_length=200)


class Survey(Input):
    tanggalSurvey: datetime.date
    nim: str = Field(default='', max_length=30)
    nama: str = Field(default='', max_length=200)
    fakultas: str = Field(default='', max_length=200)
    kampus: str = Field(default='', max_length=200)
    skorMateri: float = Field(ge=1, le=5)
    skorNarasumber: float = Field(ge=1, le=5)
    skorFasilitas: float = Field(ge=1, le=5)
    skorDampakKarakter: float = Field(ge=1, le=5)
    saran: str = Field(default='', max_length=5000)


class DashboardActivity(Input):
    namaKegiatan: str = Field(min_length=3, max_length=200)
    tanggal: datetime.date
    jumlahPeserta: int = Field(default=0, ge=0, le=10000000)
    linkEvident: str = Field(default='', max_length=2000)
    tempat: str = Field(default='', max_length=500)
    unitKerjasama: str = Field(default='', max_length=500)
    urusan: str = Field(default='Pengembangan karakter', max_length=200)
    program: Literal['Pengembangan Karakter', 'Asrama'] = 'Pengembangan Karakter'
    kategori: str = Field(min_length=1, max_length=100)
    jenis: str = Field(default='', max_length=200)
    pembicara: str = Field(default='', max_length=500)
    honor: str = Field(default='', max_length=100)
    takPanitia: int = Field(default=10, ge=0, le=10000)
    takPeserta: int = Field(default=5, ge=0, le=10000)
    laporan: str = Field(default='', max_length=20000)
    targetSurveyKepuasan: float | None = Field(default=None, ge=1, le=5)
    evaluasiMateri: str = Field(default='', max_length=100)
    evaluasiNarasumber: str = Field(default='', max_length=100)
    evaluasiFasilitas: str = Field(default='', max_length=100)
    evaluasiDampak: str = Field(default='', max_length=100)
    catatanSurvey: str = Field(default='', max_length=10000)
    participants: list[Student] = Field(default_factory=list, max_length=10000)
    surveys: list[Survey] = Field(default_factory=list, max_length=10000)


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


def register(app, connect, auth, allow, audit, hash_password, check_password):
    def visible(user, program):
        return user['role'] not in ('pengkar', 'asrama') or program == ('Asrama' if user['role'] == 'asrama' else 'Pengembangan Karakter')

    def profile(user):
        return dict(username=user['username'], nama=user['full_name'], role=user['role'],
                    email=user['email'], instansi=user['institution'], kampus=user['campus'])

    def converted(row, details, responses):
        data = dict(row)
        date = datetime.date.fromisoformat(data['tanggal'])
        result = dict(id=data['id'], namaKegiatan=data['nama_kegiatan'], tanggal=data['tanggal'],
                      program=data['program'], kategori=data['kategori'], tempat=data['tempat'],
                      unitKerjasama=data['unit_kerjasama'], pembicara=data['pembicara'],
                      jumlahPeserta=data['jumlah_peserta'], laporan=data['laporan'],
                      linkEvident=data['link_eviden'], urusan=data['program'], jenis=data['kategori'],
                      honor='', takPanitia=10, takPeserta=5, targetSurveyKepuasan=None,
                      evaluasiMateri='', evaluasiNarasumber='', evaluasiFasilitas='', evaluasiDampak='', catatanSurvey='')
        extras = details.get(data['id'], {})
        for key in ('jenis','honor','takPanitia','takPeserta','targetSurveyKepuasan','evaluasiMateri',
                    'evaluasiNarasumber','evaluasiFasilitas','evaluasiDampak','catatanSurvey','urusan'):
            if key in extras:
                result[key] = extras[key]
        result.update(id=data['id'], tahun=str(date.year), triwulan=f'TW{(date.month-1)//3+1}')
        scores = [r[k] for r in responses for k in ('skorMateri', 'skorNarasumber', 'skorFasilitas', 'skorDampakKarakter')]
        legacy = [data[k] for k in ('skor_materi', 'skor_narasumber', 'skor_fasilitas', 'skor_dampak') if data.get(k) is not None]
        result['skorSurvey'] = round(sum(scores)/len(scores), 2) if scores else (round(sum(legacy)/len(legacy), 2) if legacy else result.get('targetSurveyKepuasan'))
        return result

    @app.get('/api/dashboard')
    def snapshot(user=Depends(auth)):
        with connect() as c:
            rows = c.execute('''SELECT a.*,e.skor_materi,e.skor_narasumber,e.skor_fasilitas,e.skor_dampak
                FROM activities a LEFT JOIN evaluations e ON e.activity_id=a.id ORDER BY a.tanggal DESC,a.id DESC''').fetchall()
            rows = [r for r in rows if visible(user, r['program'])]
            ids = {r['id'] for r in rows}
            details = {r['activity_id']: json.loads(r['payload']) for r in c.execute('SELECT * FROM activity_details') if r['activity_id'] in ids}
            surveys = [dict(json.loads(r['payload']), id=r['id'], activityId=r['activity_id']) for r in c.execute('SELECT * FROM survey_responses') if r['activity_id'] in ids]
            by_activity = {}
            for survey in surveys:
                by_activity.setdefault(survey['activityId'], []).append(survey)
            activities = [converted(r, details, by_activity.get(r['id'], [])) for r in rows]
            names = {a['id']: a['namaKegiatan'] for a in activities}
            for survey in surveys:
                survey['namaKegiatan'] = names[survey['activityId']]
            students = [dict(r) for r in c.execute('''SELECT s.*,p.activity_id AS activityId
                FROM activity_participants p JOIN students s ON s.nim=p.nim''') if r['activityId'] in ids]
            users = []
            if user['role'] == 'admin':
                users = [dict(id=r['id'], username=r['username'], nama=r['full_name'], email=r['email'],
                              role=r['dashboard_role'] or r['role'], status='Aktif' if r['active'] else 'Nonaktif')
                         for r in c.execute('SELECT * FROM users ORDER BY id')]
            return dict(activities=activities, students=students, surveys=surveys, adminList=users, profile=profile(user))

    def write_surveys(c, ident, surveys, user, notes=''):
        previous = c.execute('SELECT count(*) FROM survey_responses WHERE activity_id=?', (ident,)).fetchone()[0]
        c.execute('DELETE FROM survey_responses WHERE activity_id=?', (ident,))
        for survey in surveys:
            c.execute('INSERT INTO survey_responses(activity_id,payload) VALUES(?,?)', (ident,json.dumps(survey.model_dump(mode='json'))))
        if surveys:
            means = [sum(getattr(s,k) for s in surveys)/len(surveys) for k in ('skorMateri','skorNarasumber','skorFasilitas','skorDampakKarakter')]
            c.execute('''INSERT INTO evaluations(activity_id,jumlah_responden,skor_materi,skor_narasumber,skor_fasilitas,skor_dampak,temuan,updated_by)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(activity_id) DO UPDATE SET jumlah_responden=excluded.jumlah_responden,
                skor_materi=excluded.skor_materi,skor_narasumber=excluded.skor_narasumber,skor_fasilitas=excluded.skor_fasilitas,
                skor_dampak=excluded.skor_dampak,temuan=excluded.temuan,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP''',
                      (ident,len(surveys),*means,notes,user['id']))
            c.execute("UPDATE activities SET status='Dievaluasi' WHERE id=?", (ident,))
        elif previous:
            c.execute('DELETE FROM evaluations WHERE activity_id=?', (ident,))
            c.execute("UPDATE activities SET status='Terlaksana' WHERE id=?", (ident,))

    def save(data, user, ident=None):
        allow(user, data.program)
        participants = {s.nim: s for s in data.participants}
        if participants and data.jumlahPeserta != len(participants):
            raise HTTPException(422, 'Jumlah peserta harus sama dengan jumlah NIM unik pada berkas peserta.')
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if ident is not None:
                old = c.execute('SELECT * FROM activities WHERE id=?', (ident,)).fetchone()
                if not old:
                    raise HTTPException(404, 'Kegiatan tidak ditemukan')
                allow(user, old['program'])
            values = (data.namaKegiatan, data.tanggal.isoformat(), data.program, data.kategori, data.tempat,
                      data.unitKerjasama, data.pembicara, data.jumlahPeserta, data.laporan, data.linkEvident)
            if ident is None:
                cur = c.execute('''INSERT INTO activities(nama_kegiatan,tanggal,program,kategori,tempat,unit_kerjasama,
                    pembicara,jumlah_peserta,laporan,link_eviden,status,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', values+('Terlaksana',user['id']))
                ident = cur.lastrowid
            else:
                c.execute('''UPDATE activities SET nama_kegiatan=?,tanggal=?,program=?,kategori=?,tempat=?,unit_kerjasama=?,
                    pembicara=?,jumlah_peserta=?,laporan=?,link_eviden=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''', values+(ident,))
            payload = data.model_dump(mode='json', exclude={'participants','surveys'})
            c.execute('INSERT INTO activity_details VALUES(?,?) ON CONFLICT(activity_id) DO UPDATE SET payload=excluded.payload', (ident,json.dumps(payload)))
            c.execute('DELETE FROM activity_participants WHERE activity_id=?', (ident,))
            for student in participants.values():
                c.execute('''INSERT INTO students VALUES(?,?,?,?,?) ON CONFLICT(nim) DO UPDATE SET
                    nama=excluded.nama,
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

    @app.post('/api/dashboard/users', status_code=201)
    def create_user(data: DashboardUser, user=Depends(auth)):
        allow(user, admin=True)
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
        allow(user, admin=True)
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            target = c.execute('SELECT * FROM users WHERE id=? AND active=1', (ident,)).fetchone()
            if not target:
                raise HTTPException(404,'Akun aktif tidak ditemukan')
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
