"""Run with: python -m unittest discover -s tests -v (temporary database only)."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_temp = tempfile.TemporaryDirectory(prefix='pkkm-tests-')
os.environ['PKKM_DB_PATH'] = str(Path(_temp.name) / 'test.sqlite3')
os.environ.pop('PKKM_ADMIN_USER', None)
os.environ.pop('PKKM_ADMIN_PASSWORD', None)

from fastapi.testclient import TestClient
import server
from dashboard_api import initialize


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        with server.connect() as c:
            for table in ('survey_responses','activity_participants','activity_details','students',
                          'evaluations','activities','audit','sessions','users'):
                c.execute(f'DELETE FROM {table}')
            c.execute('INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)',
                      ('testadmin',server.hash_password('Test-password-only-2026'),'Test Admin','admin'))
        self.headers = self.login('testadmin')

    def login(self, username, password='Test-password-only-2026'):
        response = self.client.post('/api/login',json={'username':username,'password':password})
        self.assertEqual(response.status_code,200,response.text)
        return {'Authorization':'Bearer '+response.json()['token']}

    def snapshot(self, headers=None):
        response = self.client.get('/api/dashboard',headers=headers or self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def activity(self, **changes):
        return {'namaKegiatan':'Kegiatan uji','tanggal':'2026-11-04','kategori':'Pengembangan Karakter',
                'program':'Pengembangan Karakter','jumlahPeserta':1,'honor':'Rp 250.000',
                'takPanitia':15,'takPeserta':7,'jenis':'Seminar',
                'participants':[{'nim':'123456789012','nama':'Peserta Uji','fakultas':'FIF','kampus':'Bandung'}],
                'surveys':[{'tanggalSurvey':'2026-11-04','nim':'123456789012','skorMateri':4,
                            'skorNarasumber':5,'skorFasilitas':3,'skorDampakKarakter':4}], **changes}

    def create(self, data=None, headers=None):
        response = self.client.post('/api/dashboard/activities',json=data or self.activity(),headers=headers or self.headers)
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['id']

    def new_user(self, username, role):
        response = self.client.post('/api/dashboard/users',headers=self.headers,json={
            'username':username,'nama':'Test '+username,'email':username+'@example.test',
            'role':role,'password':'Test-password-only-2026'})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['id'], self.login(username)

    def test_login_required_and_no_demo_data(self):
        homepage=self.client.get('/')
        self.assertEqual(homepage.headers.get('cache-control'),'no-store')
        self.assertIn('/static/app.js?v=',homepage.text)
        self.assertEqual(self.client.get('/api/dashboard').status_code,401)
        data = self.snapshot()
        self.assertEqual(data['activities'],[])
        self.assertEqual(data['students'],[])
        self.assertEqual(data['surveys'],[])
        self.assertNotIn('password_hash',str(data))

    def test_activity_participants_survey_and_legacy_apis(self):
        ident = self.create()
        data = self.snapshot()
        self.assertEqual(data['activities'][0]['id'],ident)
        self.assertEqual(data['activities'][0]['honor'],'Rp 250.000')
        self.assertEqual(data['activities'][0]['triwulan'],'TW4')
        self.assertEqual(data['activities'][0]['skorSurvey'],4)
        self.assertEqual(data['students'][0]['activityId'],ident)
        self.assertEqual(data['surveys'][0]['namaKegiatan'],'Kegiatan uji')
        summary = self.client.get('/api/summary',headers=self.headers).json()
        self.assertEqual(summary['rerata_dampak'],4)
        self.assertIn('Kegiatan uji',self.client.get('/api/report.csv',headers=self.headers).text)
        updated = self.activity(namaKegiatan='Kegiatan diperbarui',surveys=[])
        response = self.client.put(f'/api/dashboard/activities/{ident}',json=updated,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.snapshot()['surveys'],[])
        self.assertIsNone(self.snapshot()['activities'][0]['skorSurvey'])
        response = self.client.delete(f'/api/activities/{ident}',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.snapshot()['activities'],[])
        self.assertEqual(self.snapshot()['students'],[])

    def test_invalid_import_does_not_partially_save(self):
        for data in (self.activity(jumlahPeserta=2),self.activity(surveys=[{
            'tanggalSurvey':'2026-11-04','skorMateri':6,'skorNarasumber':4,
            'skorFasilitas':4,'skorDampakKarakter':4}]), self.activity(tanggal='2026-02-30')):
            response = self.client.post('/api/dashboard/activities',headers=self.headers,json=data)
            self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(self.snapshot()['activities'],[])

    def test_reimport_without_optional_columns_preserves_student_details(self):
        self.create(self.activity(participants=[{'nim':'123456789012','nama':'Peserta Uji',
            'prodi':'Informatika','fakultas':'FIF','kampus':'Bandung'}]))
        self.create(self.activity(namaKegiatan='Kegiatan kedua',participants=[{
            'nim':'123456789012','nama':'Peserta Uji'}]))
        data=self.snapshot()
        self.assertEqual(len(data['students']),2)
        self.assertEqual(len({row['nim'] for row in data['students']}),1)
        for student in data['students']:
            self.assertEqual(student['prodi'],'Informatika')
            self.assertEqual(student['fakultas'],'FIF')
            self.assertEqual(student['kampus'],'Bandung')

    def test_operator_and_program_access(self):
        _, operator = self.new_user('operator','operator')
        _, asrama = self.new_user('asrama','asrama')
        pengkar_id = self.create(headers=operator)
        asrama_id = self.create(self.activity(program='Asrama'),headers=operator)
        self.assertEqual([a['id'] for a in self.snapshot(asrama)['activities']],[asrama_id])
        legacy = self.client.get('/api/activities',headers=asrama).json()
        self.assertEqual([a['id'] for a in legacy],[asrama_id])
        response = self.client.put(f'/api/dashboard/activities/{pengkar_id}',json=self.activity(program='Asrama'),headers=asrama)
        self.assertEqual(response.status_code,403)
        response = self.client.post('/api/dashboard/users',headers=operator,json={
            'username':'escalate','nama':'Bad User','role':'admin','password':'Test-password-only-2026'})
        self.assertEqual(response.status_code,403)

    def test_verifier_can_only_change_surveys_and_viewer_is_read_only(self):
        ident = self.create()
        _, verifier = self.new_user('verifier','verifier')
        _, viewer = self.new_user('viewer','viewer')
        self.assertEqual(self.client.post('/api/dashboard/activities',headers=verifier,json=self.activity()).status_code,403)
        self.assertEqual(self.client.put(f'/api/dashboard/activities/{ident}/surveys',headers=verifier,json=[]).status_code,200)
        self.assertEqual(self.client.put(f'/api/dashboard/activities/{ident}/surveys',headers=viewer,json=[]).status_code,403)
        self.assertEqual(self.snapshot(verifier)['adminList'],[])

    def test_account_deactivation_preserves_data_and_revokes_sessions(self):
        ident, user_headers = self.new_user('secondadmin','admin')
        self.create(headers=user_headers)
        self.assertEqual(self.client.delete('/api/dashboard/users/1',headers=self.headers).status_code,409)
        response = self.client.delete(f'/api/dashboard/users/{ident}',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/dashboard',headers=user_headers).status_code,401)
        self.assertEqual(len(self.snapshot()['activities']),1)

    def test_profile_and_password_change(self):
        data = {'username':'renamed','nama':'Nama Baru','email':'new@example.test','instansi':'Unit Uji','kampus':'Bandung'}
        response = self.client.put('/api/profile',headers=self.headers,json=data)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.snapshot()['profile']['username'],'renamed')
        password = {'current_password':'wrong','new_password':'New-test-password-2026'}
        self.assertEqual(self.client.put('/api/profile/password',headers=self.headers,json=password).status_code,403)
        password['current_password']='Test-password-only-2026'
        self.assertEqual(self.client.put('/api/profile/password',headers=self.headers,json=password).status_code,200)
        self.assertEqual(self.client.get('/api/dashboard',headers=self.headers).status_code,401)
        self.login('renamed','New-test-password-2026')

    def test_additive_migration_is_repeatable(self):
        path = Path(_temp.name)/'legacy.sqlite3'
        path.unlink(missing_ok=True)
        def connect():
            c = sqlite3.connect(path)
            c.row_factory = sqlite3.Row
            return c
        with connect() as c:
            c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,password_hash TEXT,full_name TEXT,role TEXT,active INTEGER)')
            c.execute("INSERT INTO users VALUES(42,'original','unchanged-hash','Original Admin','admin',1)")
        initialize(connect)
        initialize(connect)
        backup = path.with_name('legacy.before-dashboard-v2.sqlite3')
        self.assertTrue(backup.is_file())
        with sqlite3.connect(backup) as c:
            self.assertEqual(c.execute('SELECT username FROM users WHERE id=42').fetchone()[0],'original')
        with connect() as c:
            row = c.execute('SELECT * FROM users WHERE id=42').fetchone()
            self.assertEqual(row['password_hash'],'unchanged-hash')
            self.assertEqual(row['username'],'original')
            self.assertEqual(row['dashboard_role'],'')

    def test_legacy_activity_remains_visible(self):
        with server.connect() as c:
            c.execute("INSERT INTO activities(nama_kegiatan,tanggal,program,kategori,jumlah_peserta) VALUES('Kegiatan lama','2024-02-21','Pengembangan Karakter','Konseling',127)")
        data = self.snapshot()
        self.assertEqual(data['activities'][0]['namaKegiatan'],'Kegiatan lama')
        self.assertEqual(data['activities'][0]['jumlahPeserta'],127)
        self.assertEqual(data['activities'][0]['triwulan'],'TW1')
        self.assertIsNone(data['activities'][0]['skorSurvey'])


if __name__ == '__main__':
    unittest.main()
