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
            for table in ('ppkt_branding','ppkt_cases','pending_participants','activity_unidentified_participants','pending_surveys','student_directory','survey_responses','activity_participants','activity_details','students',
                          'evaluations','activities','audit','sessions','users'):
                c.execute(f'DELETE FROM {table}')
            c.execute('INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)',
                      ('testadmin',server.hash_password('Test-password-only-2026'),'Test Admin','admin'))
        self.headers = self.login('testadmin')

    def test_dashboard_stream_preserves_json_and_protects_authenticated_data(self):
        response=self.client.get('/api/dashboard',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertIn('application/json',response.headers['content-type'])
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.json()['students'],[])
        self.assertEqual(self.client.get('/api/dashboard').status_code,401)
        from dashboard_api import stream_snapshot
        import json
        payload={'students':[{'nama':'Mahasiswa — Uji 中文','nim':str(i).zfill(12)} for i in range(2000)],'missing':None}
        chunks=list(stream_snapshot(lambda:payload))
        self.assertGreater(len(chunks),1)
        self.assertEqual(json.loads(b''.join(chunks)),payload)

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
        for data in (self.activity(jumlahPeserta=0),self.activity(surveys=[{
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

    def test_compact_dashboard_omits_individual_records_and_statistics_match_full_data(self):
        first=self.create(self.activity(surveys=[{'nim':'123456789012','answers':[4]*20}]))
        second=self.create(self.activity(namaKegiatan='Second',participants=[{'nim':'123456789012','nama':'Peserta Uji','fakultas':'FIF','kampus':'Bandung'}],surveys=[{'answers':[None,2]+[None]*18}]))
        full=self.snapshot()
        compact=self.client.get('/api/dashboard?compact=true',headers=self.headers)
        self.assertEqual(compact.status_code,200)
        data=compact.json();self.assertTrue(data['compact'])
        for key in ('students','surveys','masterStudents','pendingParticipants','pendingSurveys'):self.assertEqual(data[key],[])
        self.assertNotIn('Peserta Uji',compact.text)
        self.assertEqual([row['skorSurvey'] for row in data['activities']],[row['skorSurvey'] for row in full['activities']])
        result=self.client.post('/api/dashboard/stats',headers=self.headers,json={'activityIds':[first,second]}).json()
        self.assertEqual(result['uniqueNim'],1)
        self.assertEqual(result['faculties'],[['FIF',1]])
        self.assertEqual(result['surveys']['responses'],2)
        self.assertEqual(result['surveys']['items'][0],{'sum':4,'count':1})
        self.assertEqual(result['surveys']['items'][1],{'sum':6,'count':2})
        self.assertEqual(self.client.post('/api/dashboard/stats',headers=self.headers,json={'activityIds':[]}).json()['uniqueNim'],0)

    def test_compact_statistics_and_search_keep_program_permissions(self):
        first=self.create()
        second=self.create(self.activity(program='Asrama'))
        _,asrama=self.new_user('compactasrama','asrama')
        response=self.client.get('/api/dashboard/search?query=123456',headers=asrama)
        self.assertEqual(response.json()['activityIds'],[second])
        self.assertEqual(self.client.post('/api/dashboard/stats',headers=asrama,json={'activityIds':[first]}).status_code,403)
        self.assertEqual(self.client.get('/api/dashboard/search?query=Peserta',headers=self.headers).json()['activityIds'],[first,second])
        self.assertEqual(self.client.post('/api/dashboard/stats',json={'activityIds':[first]}).status_code,401)

    def test_ppkt_executive_summary_faculty_filters_and_projection(self):
        items=[{'caseNumber':'SOURCE-PRIVATE-1','year':2024,'category':'Kekerasan Seksual','status':'Kesimpulan dan Rekomendasi Sanksi','reportedFaculty':'Fakultas Ekonomi dan Bisnis','reportedInstitution':'Universitas Telkom','reportedStudyProgram':'Program Uji','notes':'Narasi tidak untuk dashboard'},
               {'caseNumber':'SOURCE-PRIVATE-2','year':2025,'category':'Psikis','status':'Dengar Keterangan','reportedFaculty':'FEB'},
               {'caseNumber':'SOURCE-PRIVATE-3','year':2025,'status':'Tutup Kasus','reportedFaculty':'FPTK','reportedInstitution':'Universitas Lain'}]
        self.assertEqual(self.client.post('/api/ppkt/import',headers=self.headers,json={'items':items}).status_code,200)
        data=self.client.get('/api/ppkt/summary',headers=self.headers).json()
        self.assertEqual(data['recommendations'],1);self.assertEqual(data['activeInvestigation'],1)
        self.assertEqual(data['reportedFaculties'],{'FEB':2,'Eksternal':1})
        self.assertEqual(data['sexualYears'],{'2024':1})
        self.assertEqual(self.client.get('/api/ppkt/summary?faculty=FEB',headers=self.headers).json()['total'],2)
        distribution=self.client.get('/api/ppkt/distribution?faculty=FEB&search=Program',headers=self.headers).json()
        self.assertEqual(distribution['total'],1)
        self.assertNotIn('SOURCE-PRIVATE',str(distribution));self.assertNotIn('Narasi',str(distribution))
        self.assertEqual(distribution['items'][0]['studyProgram'],'Program Uji')
        _,viewer=self.new_user('distributionviewer','viewer')
        self.assertEqual(self.client.get('/api/ppkt/distribution',headers=viewer).status_code,403)

    def test_official_ppkt_logo_is_installed_once_without_resetting_later_uploads(self):
        from ppkt_api import initialize as initialize_ppkt,DEFAULT_LOGO
        with tempfile.TemporaryDirectory(prefix='ppkt-logo-') as directory:
            database=Path(directory)/'branding.sqlite3'
            def connect():
                c=sqlite3.connect(database);c.row_factory=sqlite3.Row;return c
            # Simulate a previously configured substitute logo.
            with connect() as c:
                c.execute('CREATE TABLE ppkt_branding(id INTEGER PRIMARY KEY,mime TEXT NOT NULL,image BLOB NOT NULL)')
                c.execute("INSERT INTO ppkt_branding VALUES(1,'image/png',?)",(b'old-logo',))
            initialize_ppkt(connect)
            with connect() as c:self.assertEqual(c.execute('SELECT image FROM ppkt_branding WHERE id=1').fetchone()[0],DEFAULT_LOGO.read_bytes())
            with connect() as c:c.execute('UPDATE ppkt_branding SET image=? WHERE id=1',(b'later-intentional-upload',))
            initialize_ppkt(connect)
            with connect() as c:self.assertEqual(c.execute('SELECT image FROM ppkt_branding WHERE id=1').fetchone()[0],b'later-intentional-upload')

    def test_ppkt_logo_upload_is_admin_only_and_survives_api_reads(self):
        import base64
        image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1XcAAAAASUVORK5CYII=')
        body={'data':'data:image/png;base64,'+base64.b64encode(image).decode()}
        _,viewer=self.new_user('logoviewer','viewer')
        self.assertEqual(self.client.put('/api/ppkt/logo',headers=viewer,json=body).status_code,403)
        self.assertEqual(self.client.put('/api/ppkt/logo',headers=self.headers,json={'data':'data:image/svg+xml;base64,PHN2Zz4='}).status_code,422)
        self.assertEqual(self.client.put('/api/ppkt/logo',headers=self.headers,json=body).status_code,200)
        response=self.client.get('/api/ppkt/logo')
        self.assertEqual(response.status_code,200);self.assertEqual(response.content,image)
        self.assertEqual(response.headers['content-type'],'image/png')
        cached=self.client.get('/api/ppkt/logo',headers={'If-None-Match':response.headers['etag']})
        self.assertEqual(cached.status_code,304)
        self.assertEqual(cached.content,b'')

    def test_ppkt_import_summary_duplicates_and_missing_fields(self):
        items=[{'caseNumber':'TEST-1','year':2024,'reportDate':'2024-11-05','category':'Psikis','status':'Tutup Kasus','bap':True,'reporterCounseling':False},
               {'caseNumber':'TEST-2','year':2025,'bap':False},
               {'caseNumber':'TEST-3','year':2025,'status':'SK Pencabutan kasus'},
               {'caseNumber':'TEST-4','year':2025,'status':'Dengar Keterangan'}]
        response=self.client.post('/api/ppkt/import',headers=self.headers,json={'items':items})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['created'],4)
        self.assertEqual(self.client.post('/api/ppkt/import',headers=self.headers,json={'items':items}).json()['skipped'],4)
        data=self.client.get('/api/ppkt/summary',headers=self.headers).json()
        self.assertEqual([data[key] for key in ('total','closed','withdrawn','ongoing','unknownStatus','missingDate')],[4,1,1,1,1,3])
        self.assertEqual(data['workflow']['bap'],{'yes':1,'no':1,'unknown':2})
        self.assertNotIn('TEST-1',str(data))
        self.assertEqual(self.client.get('/api/ppkt/summary?year=2024',headers=self.headers).json()['total'],1)
        self.assertEqual(self.client.get('/api/ppkt/summary?status=Dalam+proses',headers=self.headers).json()['total'],1)
        self.assertEqual(self.snapshot()['activities'],[])

    def test_ppkt_permissions_separate_summary_from_sensitive_case_data(self):
        for role in ('operator','viewer','pengkar','asrama','verifier'):
            _,headers=self.new_user('ppkt'+role,role)
            self.assertEqual(self.client.get('/api/ppkt/summary',headers=headers).status_code,200 if role in ('operator','viewer') else 403)
            self.assertEqual(self.client.get('/api/ppkt/cases',headers=headers).status_code,403)
            self.assertEqual(self.client.post('/api/ppkt/import',headers=headers,json={'items':[{'caseNumber':'TEST'}]}).status_code,403)
            self.assertEqual(self.client.post('/api/ppkt/cases',headers=headers,json={'caseNumber':'TEST'}).status_code,403)
        self.assertEqual(self.client.get('/api/ppkt/summary').status_code,401)

    def test_ppkt_case_edit_and_validation_preserve_exact_source_status(self):
        result=self.client.post('/api/ppkt/cases',headers=self.headers,json={'caseNumber':'CASE-1','year':2024,'status':'Dengar Keterangan','notes':'Catatan asli'})
        self.assertEqual(result.status_code,201,result.text)
        ident=result.json()['id']
        self.assertEqual(self.client.post('/api/ppkt/cases',headers=self.headers,json={'caseNumber':'case-1'}).status_code,409)
        self.assertEqual(self.client.put('/api/ppkt/cases/'+str(ident),headers=self.headers,json={'caseNumber':'CASE-1','year':2024,'status':'Tutup Kasus','notes':'Catatan tetap tersimpan'}).status_code,200)
        data=self.client.get('/api/ppkt/cases',headers=self.headers).json()['items'][0]
        self.assertEqual(data['notes'],'Catatan tetap tersimpan')
        self.assertEqual(self.client.get('/api/ppkt/summary',headers=self.headers).json()['closed'],1)
        self.assertEqual(self.client.post('/api/ppkt/import',headers=self.headers,json={'items':[{'caseNumber':'X','year':2024,'reportDate':'2025-01-01'}]}).status_code,422)

    def test_startup_categorizes_only_clear_dorm_records_once_with_history(self):
        target=self.create(self.activity(namaKegiatan='Kegiatan Iftar SR',program='Asrama',kategori='Pengkar Asrama'))
        ambiguous=self.create(self.activity(namaKegiatan='Dorm Class',program='Asrama',kategori='Pengkar Asrama'))
        correct=self.create(self.activity(namaKegiatan='Olahraga sudah ditinjau',program='Asrama',kategori='Adaptif'))
        before=self.snapshot()
        initialize(server.connect)
        initialize(server.connect)
        after=self.snapshot()
        categories={row['id']:row['kategori'] for row in after['activities']}
        self.assertEqual(categories[target],'Spiritual')
        self.assertEqual(categories[ambiguous],'Pengkar Asrama')
        self.assertEqual(categories[correct],'Adaptif')
        self.assertEqual(after['students'],before['students'])
        self.assertEqual(after['surveys'],before['surveys'])
        with server.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM asrama_category_history WHERE activity_id=?',(target,)).fetchone()[0],1)
            self.assertEqual(c.execute('SELECT old_category FROM asrama_category_history WHERE activity_id=?',(target,)).fetchone()[0],'Pengkar Asrama')

    def test_dorm_category_preview_uses_conservative_rules_and_keeps_correct_categories(self):
        fixtures=[('Check-in Asrama','Adaptif'),('Kegiatan Iftar SR','Spiritual'),('Workshop Strategi Belajar','Akademik'),('Dorm Olympic','Sosial'),('Dorm Class',None),('Iftar dan Olahraga',None)]
        expected={}
        for name,category in fixtures:
            ident=self.create(self.activity(namaKegiatan=name,program='Asrama',kategori='Pengkar Asrama'))
            expected[ident]=category
        kept=self.create(self.activity(namaKegiatan='Olahraga sudah ditinjau',program='Asrama',kategori='Spiritual'))
        other=self.create(self.activity(namaKegiatan='Webinar umum'))
        preview=self.client.get('/api/dashboard/asrama/categories',headers=self.headers).json()
        items={row['id']:row for row in preview['items']}
        self.assertNotIn(other,items)
        for ident,category in expected.items():self.assertEqual(items[ident]['suggestion'],category)
        self.assertTrue(items[kept]['complete'])
        self.assertEqual(items[kept]['suggestion'],'Spiritual')
        with server.connect() as c:
            self.assertEqual(c.execute('SELECT kategori FROM activities WHERE id=?',(next(iter(expected)),)).fetchone()['kategori'],'Pengkar Asrama')

    def test_dorm_category_batch_updates_only_category_with_history_and_preserves_responses(self):
        ident=self.create(self.activity(namaKegiatan='Kegiatan Iftar SR',program='Asrama',kategori='Spritual'))
        before=self.snapshot()
        body={'items':[{'activityId':ident,'expectedCategory':'Spritual','category':'Spiritual'}]}
        response=self.client.post('/api/dashboard/asrama/categories',headers=self.headers,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['updated'],1)
        after=self.snapshot()
        self.assertEqual(after['students'],before['students'])
        self.assertEqual(after['surveys'],before['surveys'])
        self.assertEqual(after['activities'][0]['kategori'],'Spiritual')
        with server.connect() as c:
            history=c.execute('SELECT * FROM asrama_category_history WHERE activity_id=?',(ident,)).fetchone()
            self.assertEqual((history['old_category'],history['new_category']),('Spritual','Spiritual'))
        body['items'][0]['expectedCategory']='Spiritual'
        self.assertEqual(self.client.post('/api/dashboard/asrama/categories',headers=self.headers,json=body).json()['updated'],0)

    def test_dorm_category_batch_rejects_stale_or_correct_categories_atomically(self):
        first=self.create(self.activity(namaKegiatan='First',program='Asrama',kategori='Lama'))
        second=self.create(self.activity(namaKegiatan='Second',program='Asrama',kategori='Sosial'))
        body={'items':[{'activityId':first,'expectedCategory':'Lama','category':'Adaptif'},{'activityId':second,'expectedCategory':'Lama','category':'Akademik'}]}
        response=self.client.post('/api/dashboard/asrama/categories',headers=self.headers,json=body)
        self.assertEqual(response.status_code,409)
        self.assertEqual(next(row for row in self.snapshot()['activities'] if row['id']==first)['kategori'],'Lama')
        body['items'][1]['expectedCategory']='Sosial'
        self.assertEqual(self.client.post('/api/dashboard/asrama/categories',headers=self.headers,json=body).status_code,409)
        body['items']=[body['items'][0],body['items'][0]]
        self.assertEqual(self.client.post('/api/dashboard/asrama/categories',headers=self.headers,json=body).status_code,422)

    def test_dorm_category_permissions_and_program_scope(self):
        target=self.create(self.activity(namaKegiatan='Iftar',program='Asrama',kategori='Lama'))
        other=self.create(self.activity(namaKegiatan='SR Camp',kategori='Lama'))
        _,asrama=self.new_user('categoryasrama','asrama')
        preview=self.client.get('/api/dashboard/asrama/categories',headers=asrama).json()
        self.assertEqual([row['id'] for row in preview['items']],[target])
        response=self.client.post('/api/dashboard/asrama/categories',headers=asrama,json={'items':[{'activityId':other,'expectedCategory':'Lama','category':'Sosial'}]})
        self.assertEqual(response.status_code,403)
        for role in ('operator','viewer','verifier','pengkar'):
            _,headers=self.new_user('category'+role,role)
            self.assertEqual(self.client.get('/api/dashboard/asrama/categories',headers=headers).status_code,403)
            self.assertEqual(self.client.post('/api/dashboard/asrama/categories',headers=headers,json={'items':[{'activityId':target,'expectedCategory':'Lama','category':'Spiritual'}]}).status_code,403)

    def test_navigation_groups_preserve_legacy_data_and_round_trip(self):
        import json
        legacy=self.create()
        with server.connect() as c:
            record=c.execute('SELECT payload FROM activity_details WHERE activity_id=?',(legacy,)).fetchone()
            payload=json.loads(record['payload']);payload.pop('navigationGroup',None)
            c.execute('UPDATE activity_details SET payload=? WHERE activity_id=?',(json.dumps(payload),legacy))
        asrama=self.create(self.activity(namaKegiatan='Grup Asrama',program='Asrama',navigationGroup='asrama'))
        ppk=self.create(self.activity(namaKegiatan='Grup PPK Tel-U',navigationGroup='ppk-telu'))
        records={row['id']:row for row in self.snapshot()['activities']}
        self.assertEqual(records[legacy]['navigationGroup'],'pengkar')
        self.assertEqual(records[asrama]['navigationGroup'],'asrama')
        self.assertEqual(records[ppk]['navigationGroup'],'ppk-telu')
        response=self.client.put('/api/dashboard/activities/'+str(ppk),headers=self.headers,json=self.activity(navigationGroup='ppk-telu',namaKegiatan='PPK edited'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(next(row for row in self.snapshot()['activities'] if row['id']==ppk)['navigationGroup'],'ppk-telu')
        response=self.client.post('/api/dashboard/activities',headers=self.headers,json=self.activity(navigationGroup='invalid'))
        self.assertEqual(response.status_code,422)
        _,scoped=self.new_user('groupasrama','asrama')
        self.assertEqual([row['id'] for row in self.snapshot(scoped)['activities']],[asrama])

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

    def test_operator_can_manage_only_delegated_account_roles(self):
        operator_id,operator=self.new_user('restrictedoperator','operator')
        for role in ('pengkar','asrama','viewer'):
            response=self.client.post('/api/dashboard/users',headers=operator,json={'username':'delegated'+role,'nama':'Delegate','role':role,'password':'Test-password-only-2026'})
            self.assertEqual(response.status_code,201,response.text)
            self.assertEqual(self.client.delete('/api/dashboard/users/'+str(response.json()['id']),headers=operator).status_code,200)
        for role in ('admin','operator','verifier'):
            response=self.client.post('/api/dashboard/users',headers=operator,json={'username':'forbidden'+role,'nama':'Forbidden','role':role,'password':'Test-password-only-2026'})
            self.assertEqual(response.status_code,403)
        protected_id,_=self.new_user('protectedoperator','operator')
        verifier_id,_=self.new_user('protectedverifier','verifier')
        for ident in (1,operator_id,protected_id,verifier_id):
            self.assertEqual(self.client.delete('/api/dashboard/users/'+str(ident),headers=operator).status_code,403)
        snapshot=self.snapshot(operator)
        self.assertTrue(all(row['role'] in ('pengkar','asrama','viewer') for row in snapshot['adminList']))
        self.assertEqual(snapshot['masterStudents'],[])

    def test_operator_cannot_bypass_hidden_migration_menu(self):
        _,operator=self.new_user('nomigration','operator')
        for endpoint in ('students','activities','participants','surveys','participants/pending/auto-connect','surveys/pending/auto-connect'):
            response=self.client.post('/api/migrate/'+endpoint,headers=operator,json={'items':[]})
            self.assertEqual(response.status_code,403,response.text)

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

    def test_satisfaction_answers_are_preserved_and_scores_recomputed(self):
        answers=[1,2,3,4,5]*4
        response={'tanggalSurvey':'2026-11-04','nim':'123456789012','answers':answers,'skorTotal':5,'saran':'Topik berikutnya'}
        self.create(self.activity(surveys=[response]))
        data=self.snapshot()
        survey=data['surveys'][0]
        self.assertEqual(survey['answers'],answers)
        self.assertEqual(survey['instrument'],'kepuasan-20-v1')
        self.assertEqual(survey['skorTotal'],3)
        self.assertEqual(survey['skorMateri'],2)
        self.assertEqual(survey['skorNarasumber'],4.5)
        self.assertEqual(survey['skorKepuasan'],1.5)
        self.assertEqual(data['activities'][0]['skorSurvey'],3)

    def test_satisfaction_missing_or_out_of_range_answers_are_rejected(self):
        for answers in ([4]*19,[4]*19+[6]):
            response=self.client.post('/api/dashboard/activities',headers=self.headers,json=self.activity(surveys=[{
                'tanggalSurvey':'2026-11-04','answers':answers}]))
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.snapshot()['activities'],[])

    def test_bulk_activity_migration_is_idempotent_and_keeps_existing_data(self):
        first=self.activity(participants=[],surveys=[])
        second=self.activity(namaKegiatan='Kegiatan kedua',participants=[],surveys=[])
        result=self.client.post('/api/migrate/activities',headers=self.headers,json={'items':[first,second]})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json(),{'created':2,'skipped':0})
        repeated={**first,'namaKegiatan':'  KEGIATAN   UJI  ','jumlahPeserta':999}
        result=self.client.post('/api/migrate/activities',headers=self.headers,json={'items':[repeated,second]})
        self.assertEqual(result.json(),{'created':0,'skipped':2})
        self.assertEqual(len(self.snapshot()['activities']),2)
        self.assertTrue(all(a['jumlahPeserta']==1 for a in self.snapshot()['activities']))

    def test_migration_does_not_partially_import_unauthorized_program(self):
        _,headers=self.new_user('pengkaruser','pengkar')
        items=[self.activity(participants=[],surveys=[]),self.activity(program='Asrama',participants=[],surveys=[])]
        response=self.client.post('/api/migrate/activities',headers=headers,json={'items':items})
        self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(self.snapshot()['activities'],[])

    def test_bulk_survey_migration_appends_matches_names_and_skips_duplicates(self):
        first=self.create()
        second=self.create(self.activity(namaKegiatan='Kegiatan kedua',surveys=[]))
        base={'tanggalSurvey':'2026-11-04','answers':[3]*20,'nim':'123456789012','saran':'Saran Topik'}
        items=[{'activityId':first,'namaKegiatan':'Kegiatan uji','sourceRow':2,'response':base},
               {'activityId':second,'namaKegiatan':'Kegiatan kedua','sourceRow':3,'response':base}]
        result=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['created'],2)
        data=self.snapshot()
        self.assertEqual(len(data['surveys']),3)  # Keeps the existing legacy response.
        self.assertEqual(next(a for a in data['activities'] if a['id']==first)['skorSurvey'],3)
        result=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(result.json()['created'],0)
        self.assertEqual(result.json()['skipped'],2)
        self.assertEqual(len(self.snapshot()['surveys']),3)

    def test_migration_wrong_activity_name_rolls_back_whole_request(self):
        ident=self.create(self.activity(surveys=[]))
        response={'tanggalSurvey':'2026-11-04','answers':[4]*20}
        items=[{'activityId':ident,'namaKegiatan':'Kegiatan uji','response':response},
               {'activityId':ident,'namaKegiatan':'Kegiatan yang salah','sourceRow':3,'response':response}]
        result=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(result.status_code,422)
        self.assertEqual(self.snapshot()['surveys'],[])

    def test_verifier_can_migrate_surveys_but_not_activities(self):
        ident=self.create(self.activity(surveys=[]))
        _,headers=self.new_user('surveyverifier','verifier')
        result=self.client.post('/api/migrate/activities',headers=headers,json={'items':[self.activity(participants=[],surveys=[])]})
        self.assertEqual(result.status_code,403)
        result=self.client.post('/api/migrate/surveys',headers=headers,json={'items':[{
            'activityId':ident,'response':{'tanggalSurvey':'2026-11-04','answers':[5]*20}}]})
        self.assertEqual(result.status_code,200,result.text)

    def test_distinct_submission_timestamps_are_not_collapsed(self):
        ident=self.create(self.activity(surveys=[]))
        items=[{'activityId':ident,'response':{'tanggalSurvey':'2026-11-04','nim':'123456789012',
                'submittedAt':timestamp,'answers':[4]*20}} for timestamp in ('2026-11-04T10:00:00','2026-11-04T11:00:00')]
        result=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(result.json()['created'],2)
        self.assertEqual(len(self.snapshot()['surveys']),2)

    def test_identical_anonymous_responses_with_distinct_source_rows_are_preserved(self):
        ident=self.create(self.activity(surveys=[]))
        items=[{'activityId':ident,'response':{'tanggalSurvey':'2026-11-04',
                'sourceKey':key,'answers':[4]*20}} for key in ('file-hash:2','file-hash:3')]
        result=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(result.json()['created'],2)
        result=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(result.json()['skipped'],2)
        self.assertEqual(len(self.snapshot()['surveys']),2)

    def test_master_import_without_activity_or_nim_keeps_incomplete_records(self):
        items=[{'nim':'123456789012','nama':'Mahasiswa Master','prodi':'Informatika'},
               {'nama':'Nama Tanpa NIM','sourceKey':'source:2'},
               {'nim':'000000000001','nama':'','fakultas':'FIF'}]
        response=self.client.post('/api/migrate/students',headers=self.headers,json={'items':items})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['created'],3)
        data=self.snapshot()
        self.assertEqual(len(data['masterStudents']),3)
        self.assertEqual(data['students'],[])
        self.assertEqual(data['activities'],[])
        self.assertEqual(next(s for s in data['masterStudents'] if s['nama']=='Nama Tanpa NIM')['nim'],'')
        repeated=self.client.post('/api/migrate/students',headers=self.headers,json={'items':items})
        self.assertEqual(repeated.json()['skipped'],3)

    def test_master_reimport_preserves_known_values_and_can_complete_missing_nim(self):
        self.client.post('/api/migrate/students',headers=self.headers,json={'items':[{'nama':'Belum Ada NIM','sourceKey':'row2','fakultas':'FIF'}]})
        row=self.snapshot()['masterStudents'][0]
        response=self.client.post('/api/migrate/students',headers=self.headers,json={'items':[{
            'directoryId':row['directoryId'],'nim':'123456789012','nama':'','prodi':'Informatika'}]})
        self.assertEqual(response.status_code,200,response.text)
        data=self.snapshot()['masterStudents']
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['nim'],'123456789012')
        self.assertEqual(data[0]['nama'],'Belum Ada NIM')
        self.assertEqual(data[0]['fakultas'],'FIF')

    def test_master_import_is_not_available_to_viewer_or_scoped_operator(self):
        _,headers=self.new_user('viewer-master','viewer')
        response=self.client.post('/api/migrate/students',headers=headers,json={'items':[{'nama':'Uji'}]})
        self.assertEqual(response.status_code,403)
        _,headers=self.new_user('pengkar-master','pengkar')
        response=self.client.post('/api/migrate/students',headers=headers,json={'items':[{'nama':'Uji'}]})
        self.assertEqual(response.status_code,403)

    def test_partial_survey_values_are_null_and_excluded_from_averages(self):
        ident=self.create(self.activity(surveys=[{'answers':[4,None,2]+[None]*17}]))
        data=self.snapshot()
        self.assertEqual(data['surveys'][0]['skorTotal'],3)
        self.assertEqual(data['surveys'][0]['skorMateri'],3)
        self.assertIsNone(data['surveys'][0]['skorNarasumber'])
        self.assertIsNone(data['surveys'][0]['tanggalSurvey'])
        self.assertEqual(data['activities'][0]['skorSurvey'],3)
        self.assertEqual(self.client.get('/api/summary',headers=self.headers).status_code,200)
        response=self.client.put(f'/api/dashboard/activities/{ident}/surveys',headers=self.headers,json=[{'answers':[None]*20}])
        self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(self.snapshot()['surveys'][0]['skorTotal'])
        self.assertIsNone(self.snapshot()['activities'][0]['skorSurvey'])

    def test_year_only_activity_import_does_not_invent_date_or_counts(self):
        items=[{'namaKegiatan':'Arsip Tahun Saja','tahun':'2024','sourceKey':'year-row2'}]
        response=self.client.post('/api/migrate/activities',headers=self.headers,json={'items':items})
        self.assertEqual(response.status_code,200,response.text)
        row=self.snapshot()['activities'][0]
        self.assertEqual(row['tanggal'],'')
        self.assertEqual(row['tahun'],'2024')
        self.assertEqual(row['triwulan'],'')
        self.assertIsNone(row['jumlahPeserta'])
        self.assertIsNone(row['takPanitia'])
        self.assertEqual(self.client.get('/api/summary?year=2024',headers=self.headers).json()['total'],1)
        repeated=self.client.post('/api/migrate/activities',headers=self.headers,json={'items':items})
        self.assertEqual(repeated.json()['skipped'],1)

    def test_unmatched_survey_is_saved_and_can_be_linked_later(self):
        items=[{'sourceRow':2,'importKey':'pending-row2','response':{'answers':[None,5]+[None]*18}}]
        response=self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['pending'],1)
        self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        self.assertEqual(len(self.snapshot()['pendingSurveys']),1)
        ident=self.create(self.activity(surveys=[]))
        pending=self.snapshot()['pendingSurveys'][0]
        response=self.client.post(f"/api/migrate/surveys/pending/{pending['id']}/resolve",headers=self.headers,json={'activityId':ident})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.snapshot()['pendingSurveys'],[])
        self.assertEqual(self.snapshot()['surveys'][0]['activityId'],ident)
        self.assertEqual(self.snapshot()['surveys'][0]['skorTotal'],5)

    def test_participant_migration_adds_without_replacing_existing_and_is_idempotent(self):
        ident=self.create(self.activity(jumlahPeserta=50,surveys=[]))
        items=[{'activityId':ident,'namaKegiatan':'Kegiatan uji','student':{'nim':'000000000002','nama':'Peserta Kedua'}},
               {'activityId':ident,'student':{'nim':'000000000002','nama':'Peserta Kedua'}}]
        result=self.client.post('/api/migrate/participants',headers=self.headers,json={'items':items})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['created'],1)
        self.assertEqual(result.json()['skipped'],1)
        data=self.snapshot()
        self.assertEqual(len(data['students']),2)
        self.assertEqual(data['activities'][0]['jumlahPeserta'],50)
        result=self.client.post('/api/migrate/participants',headers=self.headers,json={'items':items})
        self.assertEqual(result.json()['created'],0)
        self.assertEqual(result.json()['skipped'],2)

    def test_participant_without_nim_is_retained_and_can_receive_nim_via_master(self):
        ident=self.create(self.activity(participants=[],jumlahPeserta=None,surveys=[]))
        items=[{'activityId':ident,'importKey':'file:2','student':{'nama':'Tanpa NIM','sourceKey':'file:2'}}]
        result=self.client.post('/api/migrate/participants',headers=self.headers,json={'items':items})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['created'],1)
        data=self.snapshot()
        self.assertEqual(data['students'][0]['nim'],'')
        self.assertEqual(data['activities'][0]['jumlahPeserta'],1)
        record=data['students'][0]['directoryId']
        result=self.client.post('/api/migrate/students',headers=self.headers,json={'items':[{'directoryId':record,'nim':'000000000002'}]})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.snapshot()['students'][0]['nim'],'000000000002')
        self.assertEqual(self.snapshot()['students'][0]['nama'],'Tanpa NIM')

    def test_participant_migration_checks_program_and_rolls_back_whole_batch(self):
        ident=self.create(self.activity(participants=[],surveys=[]))
        other=self.create(self.activity(program='Asrama',participants=[],surveys=[]))
        _,headers=self.new_user('participant-pengkar','pengkar')
        items=[{'activityId':activity,'student':{'nim':'000000000003','nama':'Uji'}} for activity in (ident,other)]
        result=self.client.post('/api/migrate/participants',headers=headers,json={'items':items})
        self.assertEqual(result.status_code,403,result.text)
        self.assertEqual(self.snapshot()['students'],[])

    def test_unmatched_participant_can_be_saved_and_linked_later(self):
        items=[{'importKey':'participant:2','student':{'nim':'000000000004','nama':'Belum Cocok'}}]
        result=self.client.post('/api/migrate/participants',headers=self.headers,json={'items':items})
        self.assertEqual(result.json()['pending'],1)
        self.client.post('/api/migrate/participants',headers=self.headers,json={'items':items})
        data=self.snapshot()
        self.assertEqual(len(data['pendingParticipants']),1)
        self.assertEqual(data['students'],[])
        ident=self.create(self.activity(participants=[],surveys=[]))
        record=data['pendingParticipants'][0]['id']
        result=self.client.post(f'/api/migrate/participants/pending/{record}/resolve',headers=self.headers,json={'activityId':ident})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.snapshot()['pendingParticipants'],[])
        self.assertEqual(self.snapshot()['students'][0]['nim'],'000000000004')

    def test_viewer_and_survey_verifier_cannot_import_participants(self):
        ident=self.create(self.activity(participants=[],surveys=[]))
        for username,role in [('participants-viewer','viewer'),('participants-verifier','verifier')]:
            _,headers=self.new_user(username,role)
            result=self.client.post('/api/migrate/participants',headers=headers,json={'items':[{'activityId':ident,'student':{'nama':'Uji'}}]})
            self.assertEqual(result.status_code,403,result.text)

    def test_auto_connect_normalizes_titles_and_preview_does_not_write(self):
        ident=self.create(self.activity(namaKegiatan='Webinar Mental — Social Media & Self-worth',participants=[],surveys=[]))
        source=' webinar MENTAL : social media and self worth '
        staged=[{'namaKegiatan':source,'importKey':'auto:'+str(i),'student':{'nim':str(100000000000+i),'nama':'Auto '+str(i)}} for i in range(5)]
        self.client.post('/api/migrate/participants',headers=self.headers,json={'items':staged})
        preview=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={})
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['summary']['matched'],5)
        self.assertEqual(self.snapshot()['students'],[])
        result=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={'dry_run':False,'limit':2})
        self.assertEqual(result.json()['processed'],2)
        self.assertEqual(result.json()['remainingMatched'],3)
        self.assertEqual(len(self.snapshot()['pendingParticipants']),3)
        result=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={'dry_run':False})
        self.assertEqual(result.json()['processed'],3)
        data=self.snapshot()
        self.assertEqual(data['pendingParticipants'],[])
        self.assertEqual({s['activityId'] for s in data['students']},{ident})
        self.assertEqual(len(data['students']),5)

    def test_auto_connect_does_not_guess_same_name_on_different_dates_or_conflicting_dates(self):
        self.create(self.activity(namaKegiatan='Nama Sama',tanggal='2026-11-04',participants=[],surveys=[]))
        self.create(self.activity(namaKegiatan='Nama Sama',tanggal='2026-11-05',participants=[],surveys=[]))
        staged=[{'namaKegiatan':'Nama Sama','importKey':'ambiguous','student':{'nama':'Uji'}},
                {'namaKegiatan':'Nama Sama','tanggalKegiatan':'2026-11-06','importKey':'conflict','student':{'nama':'Uji'}}]
        self.client.post('/api/migrate/participants',headers=self.headers,json={'items':staged})
        response=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={'dry_run':False})
        self.assertEqual(response.json()['processed'],0)
        data=self.snapshot()
        self.assertEqual(len(data['pendingParticipants']),2)
        self.assertEqual(data['students'],[])
        preview=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={}).json()
        self.assertEqual(preview['summary']['ambiguous'],1)
        self.assertEqual(preview['summary']['date_conflict'],1)

    def test_auto_connect_uses_exact_date_to_disambiguate(self):
        self.create(self.activity(namaKegiatan='Nama Sama',tanggal='2026-11-04',participants=[],surveys=[]))
        target=self.create(self.activity(namaKegiatan='Nama Sama',tanggal='2026-11-05',participants=[],surveys=[]))
        self.client.post('/api/migrate/participants',headers=self.headers,json={'items':[{'namaKegiatan':'nama sama',
            'tanggalKegiatan':'2026-11-05','student':{'nim':'000000000006'}}]})
        response=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={'dry_run':False})
        self.assertEqual(response.json()['created'],1)
        self.assertEqual(self.snapshot()['students'][0]['activityId'],target)

    def test_group_connect_resolves_whole_named_group_without_mixing_other_group(self):
        target=self.create(self.activity(participants=[],surveys=[]))
        staged=[{'namaKegiatan':'Nama File Lama','importKey':str(i),'student':{'nim':str(100000000000+i)}} for i in range(4)]
        staged.append({'namaKegiatan':'Kelompok Lain','importKey':'other','student':{'nama':'Lain'}})
        self.client.post('/api/migrate/participants',headers=self.headers,json={'items':staged})
        preview=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={}).json()
        group=next(group for group in preview['groups'] if group['name']=='Nama File Lama')
        response=self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={
            'dry_run':False,'groupKey':group['key'],'activityId':target})
        self.assertEqual(response.json()['processed'],4)
        self.assertEqual(len(self.snapshot()['students']),4)
        self.assertEqual(len(self.snapshot()['pendingParticipants']),1)

    def test_auto_connect_is_limited_to_current_user_and_allowed_program(self):
        target=self.create(self.activity(program='Asrama',participants=[],surveys=[]))
        self.client.post('/api/migrate/participants',headers=self.headers,json={'items':[{
            'namaKegiatan':'Kegiatan uji','student':{'nama':'Admin Pending'}}]})
        _,headers=self.new_user('match-pengkar','pengkar')
        self.client.post('/api/migrate/participants',headers=headers,json={'items':[{'namaKegiatan':'Kegiatan uji',
            'student':{'nama':'Scoped Pending'}}]})
        preview=self.client.post('/api/migrate/participants/pending/auto-connect',headers=headers,json={}).json()
        self.assertEqual(preview['summary']['total'],1)
        self.assertEqual(preview['summary']['matched'],0)
        group=preview['groups'][0]
        response=self.client.post('/api/migrate/participants/pending/auto-connect',headers=headers,json={
            'dry_run':False,'groupKey':group['key'],'activityId':target})
        self.assertEqual(response.status_code,403)
        self.assertEqual(len(self.snapshot()['pendingParticipants']),1)
        self.assertEqual(len(self.snapshot(headers)['pendingParticipants']),1)

    def test_auto_connect_rejects_readonly_roles_and_invalid_batch_limits(self):
        for username,role in [('match-viewer','viewer'),('match-verifier','verifier')]:
            _,headers=self.new_user(username,role)
            self.assertEqual(self.client.post('/api/migrate/participants/pending/auto-connect',headers=headers,json={}).status_code,403)
        self.assertEqual(self.client.post('/api/migrate/participants/pending/auto-connect',headers=self.headers,json={'limit':1001}).status_code,422)

    def test_survey_auto_connect_preserves_existing_answers_and_skips_duplicates(self):
        target=self.create(self.activity(namaKegiatan='Survei — Mental & Karakter'))
        answers=[None,5]+[None]*18
        response={'tanggalSurvey':'2026-11-05','nim':'000000000011','answers':answers,'saran':'Pertanyaan asli tetap'}
        staged=[{'namaKegiatan':'survei: mental and karakter','importKey':str(i),'response':response} for i in range(2)]
        self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':staged})
        preview=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=self.headers,json={})
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['summary']['matched'],2)
        self.assertEqual(len(self.snapshot()['surveys']),1)
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=self.headers,json={'dry_run':False})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['processed'],2)
        self.assertEqual(result.json()['created'],1)
        self.assertEqual(result.json()['skipped'],1)
        data=self.snapshot()
        self.assertEqual(data['pendingSurveys'],[])
        self.assertEqual(len(data['surveys']),2)
        saved=next(row for row in data['surveys'] if row['nim']=='000000000011')
        self.assertEqual(saved['answers'],answers)
        self.assertEqual(saved['saran'],'Pertanyaan asli tetap')
        self.assertEqual(saved['tanggalSurvey'],'2026-11-05')
        self.assertEqual(saved['activityId'],target)

    def test_survey_auto_connect_keeps_ambiguous_and_conflicting_activity_dates(self):
        first=self.create(self.activity(namaKegiatan='Survei Sama',tanggal='2026-11-04',surveys=[]))
        second=self.create(self.activity(namaKegiatan='Survei Sama',tanggal='2026-11-05',surveys=[]))
        base={'tanggalSurvey':'2026-11-04','answers':[4]*20}
        items=[{'namaKegiatan':'Survei Sama','importKey':'ambiguous','response':base},
               {'namaKegiatan':'Survei Sama','tanggalKegiatan':'2026-11-05','importKey':'matched','response':base},
               {'namaKegiatan':'Survei Sama','tanggalKegiatan':'2026-11-06','importKey':'conflict','response':base}]
        self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':items})
        preview=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=self.headers,json={}).json()
        self.assertEqual(preview['summary']['matched'],1)
        self.assertEqual(preview['summary']['ambiguous'],1)
        self.assertEqual(preview['summary']['date_conflict'],1)
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=self.headers,json={'dry_run':False})
        self.assertEqual(result.json()['processed'],1)
        self.assertEqual(self.snapshot()['surveys'][0]['activityId'],second)
        self.assertEqual(len(self.snapshot()['pendingSurveys']),2)

    def test_survey_group_connect_supports_verifier_and_batch_progress(self):
        target=self.create(self.activity(surveys=[]))
        _,headers=self.new_user('auto-survey-verifier','verifier')
        items=[{'namaKegiatan':'Judul Survey Lama','importKey':str(i),'response':{
            'nim':str(900000000000+i),'answers':[3]*20}} for i in range(3)]
        self.client.post('/api/migrate/surveys',headers=headers,json={'items':items})
        plan=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=headers,json={}).json()
        group=plan['groups'][0]['key']
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=headers,json={
            'dry_run':False,'groupKey':group,'activityId':target,'limit':2})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['processed'],2)
        self.assertEqual(result.json()['remainingGroup'],1)
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=headers,json={
            'dry_run':False,'groupKey':group,'activityId':target})
        self.assertEqual(result.json()['processed'],1)
        self.assertEqual(len(self.snapshot()['surveys']),3)
        self.assertEqual(self.snapshot(headers)['pendingSurveys'],[])

    def test_survey_auto_connect_restricts_current_user_and_program(self):
        target=self.create(self.activity(program='Asrama',surveys=[]))
        item={'namaKegiatan':'Kegiatan uji','response':{'answers':[4]*20}}
        self.client.post('/api/migrate/surveys',headers=self.headers,json={'items':[item]})
        _,headers=self.new_user('auto-survey-pengkar','pengkar')
        self.client.post('/api/migrate/surveys',headers=headers,json={'items':[item]})
        plan=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=headers,json={}).json()
        self.assertEqual(plan['summary']['total'],1)
        self.assertEqual(plan['summary']['matched'],0)
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=headers,json={
            'dry_run':False,'groupKey':plan['groups'][0]['key'],'activityId':target})
        self.assertEqual(result.status_code,403)
        self.assertEqual(len(self.snapshot()['pendingSurveys']),1)
        self.assertEqual(len(self.snapshot(headers)['pendingSurveys']),1)

    def test_survey_auto_connect_denies_viewers_and_invalid_batch_sizes(self):
        _,headers=self.new_user('survey-auto-viewer','viewer')
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=headers,json={})
        self.assertEqual(result.status_code,403)
        result=self.client.post('/api/migrate/surveys/pending/auto-connect',headers=self.headers,json={'limit':1001})
        self.assertEqual(result.status_code,422)


if __name__ == '__main__':
    unittest.main()
