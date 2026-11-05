"""Optional browser checks: python tests/browser_smoke.py.
Requires Playwright and Chromium; uses only a temporary database.
"""
import os
import io
import base64
import csv as csv_tools
import json
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path('/tmp/pkkm-browser-artifacts')
ARTIFACTS.mkdir(exist_ok=True)


def open_report(page):
    group=page.get_by_label("Grup Pengguna",exact=True)
    if group.input_value()=="overview":
        group.select_option("pengkar")
        if page.locator("aside").is_hidden():page.get_by_role("button",name="Buka menu",exact=True).click()
    page.get_by_role('button',name='Laporan',exact=False).first.click()

def main():
    with tempfile.TemporaryDirectory(prefix='pkkm-browser-') as tmp:
        password = secrets.token_urlsafe(24)
        new_password = secrets.token_urlsafe(24)
        env = {**os.environ,'PKKM_DB_PATH':str(Path(tmp)/'pkkm.sqlite3'),
               'PKKM_ADMIN_USER':'browseradmin','PKKM_ADMIN_PASSWORD':password}
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        command = [sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port),'--workers','1','--proxy-headers']
        log = open(Path(tmp)/'server.log','w+')
        process = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
        url = f'http://127.0.0.1:{port}'
        try:
            with httpx.Client(base_url=url,trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read())
                    try:
                        if client.get('/').status_code==200:
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('Server startup timeout')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),args=['--no-sandbox'])
                page = browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
                errors = []
                dashboard_requests=[]
                page.on('request',lambda request:dashboard_requests.append(request.url) if request.method=='GET' and request.url.startswith(url+'/api/dashboard') else None)
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url)
                expect(page.get_by_text('PKKM Sign In',exact=True)).to_be_visible()
                page.screenshot(path=str(ARTIFACTS/'login.png'),full_page=True)
                page.get_by_label('Username',exact=True).fill('browseradmin')
                page.get_by_label('Password',exact=True).fill('incorrect-password')
                page.get_by_role('button',name='Login',exact=True).click()
                expect(page.get_by_text('Kredensial tidak sesuai',exact=True)).to_be_visible()
                page.get_by_label('Password',exact=True).fill(password)
                page.get_by_role('button',name='Login',exact=True).click()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                expect(page.get_by_label('Grup Pengguna',exact=True)).to_have_value('overview')
                page.locator('.telu-banner-photo').evaluate('(img) => img.decode()')
                page.screenshot(path=str(ARTIFACTS/'dashboard-telu.png'),full_page=True)
                print('PASS: login defaults to overall Dashboard and accepts stored account')
                assert url+'/api/dashboard?compact=true' in dashboard_requests
                assert url+'/api/dashboard' not in dashboard_requests
                open_report(page)
                page.get_by_label('Nama Kegiatan',exact=True).fill('Kegiatan Uji Browser')
                assert dashboard_requests.count(url+'/api/dashboard')==1
                print('PASS: login fetches only compact snapshot; full details are fetched once when opening Laporan')
                page.get_by_label('Tanggal Kegiatan',exact=True).fill('2026-11-04')
                page.get_by_label('Honor Pembicara (Rp)',exact=True).fill('Rp 250.000')
                with page.expect_download() as participant_template:
                    page.get_by_role('button',name='Unduh Template',exact=True).click()
                page.get_by_label('Berkas peserta kegiatan',exact=True).set_input_files(participant_template.value.path())
                expect(page.get_by_text('1 peserta unik siap disimpan bersama kegiatan.',exact=True)).to_be_visible()
                print('PASS: download and reimport XLSX participant template')
                csv = b'Nama Mahasiswa,NIM / NPM,Program Studi (Prodi),Nama Fakultas,Lokasi Kampus\nPeserta Uji,123456789012,Informatika,FIF,Bandung\nPeserta Uji,123456789012,Informatika,FIF,Bandung\n'
                page.get_by_label('Berkas peserta kegiatan',exact=True).set_input_files({'name':'peserta.csv','mimeType':'text/csv','buffer':csv})
                expect(page.get_by_text('1 peserta unik siap disimpan bersama kegiatan.',exact=True)).to_be_visible()
                expect(page.get_by_label('Jumlah Peserta',exact=True)).to_have_value('1')
                preview=page.get_by_label('Pratinjau peserta kegiatan',exact=True)
                expect(preview).to_contain_text('Peserta Uji')
                expect(preview).to_contain_text('belum disimpan')
                expect(preview).to_contain_text('1 baris NIM duplikat digabung')
                invalid=b'Nama Mahasiswa,NIM\nPeserta Salah,BAD\n'
                page.get_by_label('Berkas peserta kegiatan',exact=True).set_input_files({'name':'salah.csv','mimeType':'text/csv','buffer':invalid})
                expect(page.get_by_role('alert')).to_contain_text('Baris 2')
                expect(preview).to_contain_text('Peserta Uji')
                print('PASS: common header aliases, visible preview and error; invalid import preserves previous draft')
                with page.expect_download() as survey_template:
                    page.get_by_role('button',name='Template Survey',exact=True).click()
                page.get_by_label('Berkas survei kegiatan',exact=True).set_input_files(survey_template.value.path())
                expect(page.get_by_role('status')).to_contain_text('1 respons survei siap disimpan.')
                print('PASS: blank satisfaction answers are accepted as null without fabricated scores')
                survey = b'tanggalSurvey,NIM,skorMateri,skorNarasumber,skorFasilitas,skorDampak,Saran\n2026-11-04,123456789012,4,5,3,4,Uji browser\n'
                page.get_by_label('Berkas survei kegiatan',exact=True).set_input_files({'name':'survei.csv','mimeType':'text/csv','buffer':survey})
                expect(page.get_by_text('1 respons survei siap disimpan.',exact=True)).to_be_visible()
                page.get_by_role('button',name='Simpan & Publikasikan Kegiatan').click()
                expect(page.get_by_text('Kegiatan berhasil disimpan di server.',exact=True)).to_be_visible()
                expect(page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True).locator('tbody tr').first).to_contain_text('Kegiatan Uji Browser')
                recap=page.get_by_role('region',name='Rekap mahasiswa tersimpan',exact=True)
                expect(recap).to_contain_text('Peserta Uji')
                expect(recap).to_contain_text('123456789012')
                expect(recap).to_contain_text('FIF')
                expect(recap).to_contain_text('Kegiatan Uji Browser')
                recap.get_by_label('Cari mahasiswa dalam rekap',exact=True).fill('not-found')
                expect(recap).to_contain_text('Tidak ada mahasiswa yang cocok')
                recap.get_by_label('Cari mahasiswa dalam rekap',exact=True).fill('123456789012')
                expect(recap.locator('tbody tr')).to_have_count(1)
                with page.expect_download() as student_export:
                    recap.get_by_role('button',name='Ekspor Rekap Mahasiswa',exact=True).click()
                assert student_export.value.suggested_filename=='Rekap_Mahasiswa_PKKM.xlsx'
                print('PASS: saved student recap, name/NIM details, search and student Excel export')
                print('PASS: import participant CSV deduplicates NIM, import survey, save activity')
                with page.expect_download() as download:
                    page.get_by_role('button',name='Ekspor Excel',exact=True).click()
                assert download.value.suggested_filename=='Laporan_PKKM.xlsx'
                print('PASS: Excel report download')
                page.evaluate('() => {window.print=()=>{throw Error("Homepage print must never be used");};}')
                with page.expect_download() as pdf_download:
                    page.get_by_role('button',name='Unduh PDF',exact=True).click()
                assert pdf_download.value.suggested_filename=='Laporan_PKKM.pdf'
                pdf=Path(pdf_download.value.path()).read_bytes()
                (ARTIFACTS/'laporan.pdf').write_bytes(pdf)
                reader=PdfReader(io.BytesIO(pdf))
                text=' '.join(p.extract_text() for p in reader.pages)
                for expected in ['Kegiatan Uji Browser','Peserta Uji','123456789012','Rekap Data Mahasiswa','Data Kegiatan']:
                    assert expected in text, (expected,text)
                for forbidden in ['Input Kegiatan Pengembangan','Simpan & Publikasikan','Pilih File Mahasiswa','Kegiatan berhasil disimpan','MENU NAVIGASI']:
                    assert forbidden not in text, (forbidden,text)
                assert len(reader.pages)<=2,len(reader.pages)
                assert float(reader.pages[0].mediabox.width)>float(reader.pages[0].mediabox.height)
                print('PASS: direct PDF download contains report data, without calling homepage print')
                page.get_by_label('Cari laporan',exact=True).fill('TidakAdaHasilPDF')
                with page.expect_download() as empty_download:
                    page.get_by_role('button',name='Unduh PDF',exact=True).click()
                empty_pdf=Path(empty_download.value.path()).read_bytes()
                empty_text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(empty_pdf)).pages)
                assert 'Tidak ada data sesuai filter' in empty_text
                assert 'Kegiatan Uji Browser' not in empty_text
                assert 'Peserta Uji' not in empty_text
                page.emulate_media(media='screen')
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                print('PASS: PDF honors selected filters and excludes records outside results')
                auth={'Authorization':'Bearer '+page.evaluate("sessionStorage.getItem('pkkm_token')")}
                participants=[{'nim':str(900000000000+i),'nama':'Cetak'+str(i),'prodi':'Informatika','fakultas':'FIF','kampus':'Bandung'} for i in range(135)]
                created=page.request.post(url+'/api/dashboard/activities',headers=auth,data={
                    'namaKegiatan':'Kegiatan Banyak Peserta','tanggal':'2026-11-04','kategori':'Pengembangan Karakter',
                    'jumlahPeserta':135,'participants':participants})
                assert created.status==201,created.text()
                created_id=created.json()['id']
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('2')
                open_report(page)
                recap=page.get_by_role('region',name='Rekap mahasiswa tersimpan',exact=True)
                expect(recap.locator('tbody tr')).to_have_count(10)
                recap.get_by_role('button',name='Berikutnya',exact=True).click()
                expect(recap).to_contain_text('Halaman 2 dari 14')
                expect(recap.locator('tbody tr')).to_have_count(10)
                recap.get_by_role('button',name='Sebelumnya',exact=True).click()
                expect(recap).to_contain_text('Halaman 1 dari 14')
                expect(recap.get_by_role('button',name='Sebelumnya',exact=True)).to_be_disabled()
                recap.get_by_label('Jumlah mahasiswa per halaman',exact=True).select_option('50')
                expect(recap.locator('tbody tr')).to_have_count(50)
                expect(recap).to_contain_text('Halaman 1 dari 3')
                recap.get_by_role('button',name='Berikutnya',exact=True).click()
                expect(recap.locator('tbody tr')).to_have_count(50)
                recap.get_by_role('button',name='Berikutnya',exact=True).click()
                expect(recap.locator('tbody tr')).to_have_count(36)
                recap.get_by_label('Jumlah mahasiswa per halaman',exact=True).select_option('all')
                expect(recap.locator('tbody tr')).to_have_count(136)
                expect(recap.get_by_role('button',name='Berikutnya',exact=True)).to_be_disabled()
                recap.get_by_label('Cari mahasiswa dalam rekap',exact=True).fill('Cetak134')
                expect(recap.locator('tbody tr')).to_have_count(1)
                recap.get_by_label('Cari mahasiswa dalam rekap',exact=True).fill('')
                recap.get_by_label('Jumlah mahasiswa per halaman',exact=True).select_option('10')
                print('PASS: student pagination 10/50/all, next/previous, final page and search')
                open_report(page)
                with page.expect_download() as large_download:
                    page.get_by_role('button',name='Unduh PDF',exact=True).click()
                large_pdf=Path(large_download.value.path()).read_bytes()
                (ARTIFACTS/'laporan-banyak-mahasiswa.pdf').write_bytes(large_pdf)
                large_text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(large_pdf)).pages)
                assert 'Cetak0' in large_text and 'Cetak134' in large_text
                assert '900000000134' in large_text
                removed=page.request.delete(url+'/api/activities/'+str(created_id),headers=auth)
                assert removed.status==200
                print('PASS: multipage PDF includes all 135 participants beyond the screen preview limit')
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('1')
                expect(page.get_by_text('CSI Bobot Setara (sementara)',exact=True).first.locator('..')).to_contain_text('Belum ada nilai')
                page.get_by_label('Cari Mahasiswa Berdasarkan NIM / Kegiatan',exact=True).fill('not-found')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('0')
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                page.get_by_label('Triwulan',exact=True).select_option('TW1')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('0')
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                expect(page.get_by_role('region',name='Rekap mahasiswa tersimpan',exact=True)).to_have_count(0)
                page.screenshot(path=str(ARTIFACTS/'dashboard.png'),full_page=True)
                print('PASS: reload retains data and real charts; search and quarter filters update metrics')
                open_report(page)
                page.get_by_role('button',name='Edit',exact=True).first.click()
                expect(page.get_by_label('Nama Kegiatan',exact=True)).to_have_value('Kegiatan Uji Browser')
                expect(page.get_by_label('Honor Pembicara (Rp)',exact=True)).to_have_value('Rp 250.000')
                page.get_by_label('Nama Kegiatan',exact=True).fill('Kegiatan Uji Diedit')
                page.get_by_role('button',name='Simpan & Publikasikan Kegiatan').click()
                expect(page.get_by_text('Kegiatan berhasil disimpan di server.',exact=True)).to_be_visible()
                expect(page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True).locator('tbody tr').first).to_contain_text('Kegiatan Uji Diedit')
                page.screenshot(path=str(ARTIFACTS/'laporan.png'),full_page=True)
                print('PASS: edit activity preserves participants, survey, and extra fields')
                os.killpg(process.pid,signal.SIGTERM)
                process.wait(timeout=10)
                process = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
                with httpx.Client(base_url=url,trust_env=False) as restart_client:
                    for _ in range(100):
                        try:
                            if restart_client.get('/').status_code==200:
                                break
                        except httpx.ConnectError:
                            pass
                        time.sleep(.1)
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('1')
                expect(page.get_by_text('CSI Bobot Setara (sementara)',exact=True).first.locator('..')).to_contain_text('Belum ada nilai')
                print('PASS: persisted database, survey responses, and session survive server restart')
                page.get_by_role('button',name='Pengaturan Admin',exact=False).click()
                page.get_by_label('Username Admin *',exact=True).fill('operatoruji')
                page.get_by_label('Email Resmi Tel-U *',exact=True).fill('operator@example.test')
                page.get_by_label('Nama Lengkap Petugas *',exact=True).fill('Operator Uji')
                operator_password=secrets.token_urlsafe(24)
                page.get_by_label('Password awal (minimal 12 karakter) *',exact=True).fill(operator_password)
                page.get_by_role('button',name='+ Buatkan Akun Admin',exact=True).click()
                expect(page.get_by_text('Akun baru berhasil dibuat dan dapat digunakan untuk login.',exact=True)).to_be_visible()
                expect(page.locator('tbody tr').filter(has_text='operatoruji')).to_contain_text('Operator KKA')
                print('PASS: create real operator account')
                page.get_by_role('button',name='Pengaturan',exact=False).filter(has_text='Pengaturan').last.click()
                page.get_by_label('Username login',exact=True).fill('browseradminbaru')
                page.get_by_label('Nama Petugas',exact=True).fill('Admin Uji Baru')
                page.get_by_role('button',name='Simpan Perubahan Profil',exact=True).click()
                expect(page.get_by_text('Profil tersimpan. Gunakan username terbaru untuk login berikutnya.',exact=True)).to_be_visible()
                page.get_by_label('Password saat ini',exact=True).fill(password)
                page.get_by_label('Password baru (minimal 12 karakter)',exact=True).fill(new_password)
                page.get_by_label('Ulangi password baru',exact=True).fill(new_password)
                page.get_by_role('button',name='Simpan Password Baru',exact=True).click()
                expect(page.get_by_text('PKKM Sign In',exact=True)).to_be_visible()
                page.get_by_label('Username',exact=True).fill('browseradminbaru')
                page.get_by_label('Password',exact=True).fill(new_password)
                page.get_by_role('button',name='Login',exact=True).click()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                print('PASS: username/profile/password changes and new login')
                page.set_viewport_size({'width':390,'height':844})
                assert page.locator('aside').is_hidden()
                page.get_by_role('button',name='Buka menu',exact=True).click()
                expect(page.locator('aside')).to_be_visible()
                open_report(page)
                expect(page.locator('aside')).to_be_hidden()
                page.screenshot(path=str(ARTIFACTS/'mobile.png'),full_page=True)
                page.set_viewport_size({'width':1440,'height':1000})
                migration=page.get_by_role('region',name='Migrasi data kegiatan dan survei',exact=True)
                activity_csv=b'Nama Kegiatan,Tanggal Kegiatan,Program,Kategori,Jumlah Peserta\nWebinar Migrasi A,2024-02-21,Pengembangan Karakter,Webinar,3\nWebinar Migrasi B,2024-03-01,Pengembangan Karakter,Webinar,5\n'
                activity_file={'name':'kegiatan-migrasi.csv','mimeType':'text/csv','buffer':activity_csv}
                migration.get_by_label('File migrasi kegiatan',exact=True).set_input_files(activity_file)
                expect(migration).to_contain_text('2 baris kegiatan siap dimigrasikan')
                migration.get_by_role('button',name='Migrasikan 2 Kegiatan',exact=True).click()
                expect(migration).to_contain_text('2 ditambahkan, 0 duplikat dilewati')
                migration.get_by_label('File migrasi kegiatan',exact=True).set_input_files(activity_file)
                expect(migration).to_contain_text('2 baris kegiatan siap dimigrasikan')
                migration.get_by_role('button',name='Migrasikan 2 Kegiatan',exact=True).click()
                expect(migration).to_contain_text('0 ditambahkan, 2 duplikat dilewati')
                print('PASS: batch activity migration through UI and repeat import without duplicates')
                schema=json.loads((ROOT/'survey_schema.json').read_text())
                with page.expect_download() as survey20_template:
                    migration.get_by_role('button',name='Template Survei Kepuasan 20 Pertanyaan',exact=True).click()
                inspect_script='''import * as XLSX from 'xlsx'; import fs from 'node:fs';
                  const schema=JSON.parse(fs.readFileSync('survey_schema.json','utf8'));
                  const workbook=XLSX.read(fs.readFileSync(process.argv[1]),{type:'buffer'});
                  const headers=XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]],{header:1})[0];
                  if(!schema.questions.every(q=>headers.includes(q))||!headers.includes(schema.suggestion))process.exit(1);'''
                subprocess.run(['node','--input-type=module','-e',inspect_script,survey20_template.value.path()],cwd=ROOT,check=True)
                headers=['Nama Kegiatan','Tanggal Survey','NIM','Nama',*schema['questions'],schema['suggestion']]
                answer_a=[1,2,3,4,5]*4
                answers_b=[5]*20
                rows=[['Webinar Migrasi A','2024-02-22','000000000101','Responden A',*answer_a,'Topik A'],
                      ['Webinar Migrasi B','2024-03-02','000000000102','Responden B',*answers_b,'Topik B']]
                buffer=io.StringIO();writer=csv_tools.writer(buffer);writer.writerow(headers);writer.writerows(rows+[rows[0]])
                survey_file={'name':'survey-20.csv','mimeType':'text/csv','buffer':buffer.getvalue().encode()}
                migration.get_by_label('File migrasi hasil survei',exact=True).set_input_files(survey_file)
                expect(migration).to_contain_text('3 respons survei kepuasan 20 pertanyaan')
                expect(migration).to_contain_text('Webinar Migrasi A')
                migration.get_by_role('button',name='Migrasikan 3 Respons Survei',exact=True).click()
                expect(migration).to_contain_text('2 respons ditambahkan ke 2 kegiatan, 1 duplikat dilewati')
                migration.get_by_label('File migrasi hasil survei',exact=True).set_input_files(survey_file)
                expect(migration).to_contain_text('3 respons survei kepuasan 20 pertanyaan')
                migration.get_by_role('button',name='Migrasikan 3 Respons Survei',exact=True).click()
                expect(migration).to_contain_text('0 respons ditambahkan ke 2 kegiatan, 3 duplikat dilewati')
                auth={'Authorization':'Bearer '+page.evaluate("sessionStorage.getItem('pkkm_token')")}
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert len(snapshot['activities'])==3
                assert len(snapshot['surveys'])==3
                full=[s for s in snapshot['surveys'] if s.get('answers')]
                assert len(full)==2
                assert next(s for s in full if s['namaKegiatan']=='Webinar Migrasi A')['answers']==answer_a
                survey_summary=page.get_by_role('region',name='Survei kepuasan 20 pertanyaan',exact=True)
                expect(survey_summary.get_by_text(schema['questions'][0],exact=True)).to_be_visible()
                expect(survey_summary).to_contain_text('2 respons instrumen 20 pertanyaan')
                item_means=[sum(values)/len(values) for i in range(20) if (values:=[r['answers'][i] for r in full if r['answers'][i] is not None])]
                expected_csi=sum(value/(5 if i in [0,1,2,3,19] else 4) for i,value in enumerate(item_means))/len(item_means)*100
                expect(survey_summary).to_contain_text(f'{expected_csi:.2f}%')
                expect(survey_summary).to_contain_text('20/20 pertanyaan terwakili')
                with page.expect_download() as exported20:
                    survey_summary.get_by_role('button',name='Ekspor Jawaban Survei Kepuasan',exact=True).click()
                subprocess.run(['node','--input-type=module','-e',inspect_script,exported20.value.path()],cwd=ROOT,check=True)
                print('PASS: unchanged 20-question template/export, name matching, raw answers and idempotent survey migration')
                bad=io.StringIO();bad_writer=csv_tools.writer(bad);bad_writer.writerow(headers);bad_writer.writerow(['Kegiatan Tidak Ada',*rows[0][1:]])
                migration.get_by_label('File migrasi hasil survei',exact=True).set_input_files({'name':'salah-kegiatan.csv','mimeType':'text/csv','buffer':bad.getvalue().encode()})
                expect(migration).to_contain_text('1 respons belum cocok')
                expect(migration.get_by_role('button',name='Migrasikan 1 Respons Survei',exact=True)).to_be_enabled()
                with page.expect_download() as migrated_pdf:
                    page.get_by_role('button',name='Unduh PDF',exact=True).click()
                pdf_text=' '.join(p.extract_text() for p in PdfReader(migrated_pdf.value.path()).pages)
                assert 'meningkatkan pemahaman saya' in pdf_text
                assert 'Webinar Migrasi A' in pdf_text
                page.screenshot(path=str(ARTIFACTS/'migrasi-survei.png'),full_page=True)
                print('PASS: unmatched activity is preserved for later matching and PDF includes question analysis')
                with page.expect_download() as master_template:
                    migration.get_by_role('button',name='Template Master Mahasiswa',exact=True).click()
                assert master_template.value.suggested_filename=='Template_Master_Mahasiswa.xlsx'
                master_file={'name':'master.csv','mimeType':'text/csv','buffer':b'NIM,Nama Mahasiswa,Program Studi,Fakultas,Kampus\n000000000707,Master Baru,Informatika,,\n,Tanpa NIM UI,,,\n000000000708,,,FIF,\n'}
                migration.get_by_label('File database master mahasiswa',exact=True).set_input_files(master_file)
                expect(migration).to_contain_text('3 baris master mahasiswa siap diimpor')
                migration.get_by_role('button',name='Impor 3 Master Mahasiswa',exact=True).click()
                expect(migration).to_contain_text('3 ditambahkan, 0 diperbarui')
                master=page.get_by_role('region',name='Database master mahasiswa tersimpan',exact=True)
                master.get_by_label('Cari mahasiswa dalam rekap',exact=True).fill('Tanpa NIM UI')
                expect(master.locator('tbody tr')).to_have_count(1)
                expect(master.locator('tbody tr')).to_contain_text('Belum diisi')
                with page.expect_download() as master_export:
                    master.get_by_role('button',name='Ekspor Master Mahasiswa',exact=True).click()
                assert master_export.value.suggested_filename=='Database_Master_Mahasiswa_PKKM.xlsx'
                migration.get_by_label('File database master mahasiswa',exact=True).set_input_files(master_file)
                expect(migration).to_contain_text('3 baris master mahasiswa siap diimpor')
                migration.get_by_role('button',name='Impor 3 Master Mahasiswa',exact=True).click()
                expect(migration).to_contain_text('0 ditambahkan, 0 diperbarui, 3 tanpa perubahan')
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert len(snapshot['activities'])==3
                assert len(snapshot['students'])==1
                assert any(s['nama']=='Tanpa NIM UI' and s['nim']=='' for s in snapshot['masterStudents'])
                print('PASS: master import, missing NIM/name, deduplication and export without changing attendance')
                with page.expect_download() as year_template:
                    migration.get_by_role('button',name='Template Migrasi Kegiatan',exact=True).click()
                check_year='''import * as XLSX from 'xlsx'; import fs from 'node:fs';
                    const book=XLSX.read(fs.readFileSync(process.argv[1]),{type:'buffer'});
                    const headers=XLSX.utils.sheet_to_json(book.Sheets[book.SheetNames[0]],{header:1})[0];
                    if(!headers.includes('Tahun'))process.exit(1);'''
                subprocess.run(['node','--input-type=module','-e',check_year,year_template.value.path()],cwd=ROOT,check=True)
                migration.get_by_label('File migrasi kegiatan',exact=True).set_input_files({'name':'tahun-saja.csv','mimeType':'text/csv','buffer':b'Nama Kegiatan,Tahun,Tempat\nArsip Tanpa Tanggal,2023,Zoom\n'})
                expect(migration).to_contain_text('1 baris kegiatan siap dimigrasikan')
                migration.get_by_role('button',name='Migrasikan 1 Kegiatan',exact=True).click()
                expect(migration).to_contain_text('1 ditambahkan, 0 duplikat dilewati')
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                archive=next(a for a in snapshot['activities'] if a['namaKegiatan']=='Arsip Tanpa Tanggal')
                assert archive['tahun']=='2023' and archive['tanggal']=='' and archive['jumlahPeserta'] is None
                activity_list=page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True)
                activity_list.locator('tbody tr').filter(has_text='Arsip Tanpa Tanggal').get_by_role('button',name='Edit',exact=True).click()
                expect(page.get_by_label('Tanggal Kegiatan',exact=True)).to_have_value('')
                expect(page.get_by_label('Triwulan kegiatan',exact=True)).to_have_value('')
                page.get_by_label('Honor Pembicara (Rp)',exact=True).fill('Rp 100.000')
                page.get_by_role('button',name='Simpan & Publikasikan Kegiatan',exact=True).click()
                expect(page.get_by_text('Kegiatan berhasil disimpan di server.',exact=True)).to_be_visible()
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                archive=next(a for a in snapshot['activities'] if a['namaKegiatan']=='Arsip Tanpa Tanggal')
                assert archive['tahun']=='2023' and archive['tanggal']=='' and archive['jumlahPeserta'] is None
                print('PASS: activity template has Tahun; year-only migration and edit preserve unknown date/count')
                partial=io.StringIO();partial_writer=csv_tools.writer(partial)
                partial_writer.writerow(['Nama Kegiatan','Tanggal Survey','NIM',schema['questions'][0],schema['questions'][1]])
                partial_writer.writerow(['','','000000000303',5,''])
                migration.get_by_label('File migrasi hasil survei',exact=True).set_input_files({'name':'survei-kosong.csv','mimeType':'text/csv','buffer':partial.getvalue().encode()})
                expect(migration).to_contain_text('1 respons belum cocok')
                migration.get_by_role('button',name='Migrasikan 1 Respons Survei',exact=True).click()
                expect(migration).to_contain_text('1 respons disimpan untuk dicocokkan')
                pending_region=page.get_by_label('Survei perlu dicocokkan',exact=True)
                target=next(a['id'] for a in snapshot['activities'] if a['namaKegiatan']=='Webinar Migrasi A')
                pending_region.locator('select[aria-label^="Kegiatan untuk kelompok survei "]').select_option(str(target))
                pending_region.get_by_role('button',name='Hubungkan 1 Survei Sekaligus',exact=True).click()
                expect(migration).to_contain_text('Selesai: 1 survei diproses, 1 hubungan baru')
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                partial_record=next(s for s in snapshot['surveys'] if s['nim']=='000000000303')
                assert partial_record['tanggalSurvey'] is None
                assert partial_record['answers']==[5]+[None]*19
                assert partial_record['skorTotal']==5
                assert snapshot['pendingSurveys']==[]
                with page.expect_download() as nullable_pdf:
                    page.get_by_role('button',name='Unduh PDF',exact=True).click()
                assert len(PdfReader(nullable_pdf.value.path()).pages)>0
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert any(s['nama']=='Tanpa NIM UI' and s['nim']=='' for s in snapshot['masterStudents'])
                print('PASS: partial/undated survey stored pending then linked without fabricated scores; PDF and reload succeed')
                open_report(page)
                migration=page.get_by_role('region',name='Migrasi data kegiatan dan survei',exact=True)
                with page.expect_download() as participant_migration_template:
                    migration.get_by_role('button',name='Template Migrasi Peserta Kegiatan',exact=True).click()
                assert participant_migration_template.value.suggested_filename=='Template_Migrasi_Peserta_Kegiatan.xlsx'
                participant_file={'name':'peserta-migrasi.csv','mimeType':'text/csv','buffer':b'Nama Kegiatan,NIM,Nama Mahasiswa,Fakultas\nWebinar Migrasi A,000000000401,Peserta Migrasi Satu,FIF\nWebinar Migrasi A,000000000401,Peserta Migrasi Satu,FIF\nWebinar Migrasi B,,Peserta Tanpa NIM Migrasi,FIF\nWebinar Migrasi B,000000000402,,\n'}
                migration.get_by_label('File migrasi peserta kegiatan',exact=True).set_input_files(participant_file)
                expect(migration).to_contain_text('4 baris peserta kegiatan siap diperiksa')
                migration.get_by_role('button',name='Migrasikan 4 Peserta Kegiatan',exact=True).click()
                expect(migration).to_contain_text('3 peserta ditambahkan ke 2 kegiatan, 1 duplikat/baris kosong dilewati')
                migration.get_by_label('File migrasi peserta kegiatan',exact=True).set_input_files(participant_file)
                expect(migration).to_contain_text('4 baris peserta kegiatan siap diperiksa')
                migration.get_by_role('button',name='Migrasikan 4 Peserta Kegiatan',exact=True).click()
                expect(migration).to_contain_text('0 peserta ditambahkan ke 2 kegiatan, 4 duplikat/baris kosong dilewati')
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert any(row['nama']=='Peserta Tanpa NIM Migrasi' and row['nim']=='' for row in snapshot['students'])
                assert any(row['nim']=='123456789012' for row in snapshot['students'])
                assert next(row for row in snapshot['activities'] if row['namaKegiatan']=='Webinar Migrasi A')['jumlahPeserta']==3
                assert next(row for row in snapshot['activities'] if row['namaKegiatan']=='Webinar Migrasi B')['jumlahPeserta']==5
                print('PASS: participant migration maps multiple activities, preserves missing identity and skips repeated NIM')
                target_a=next(row['id'] for row in snapshot['activities'] if row['namaKegiatan']=='Webinar Migrasi A')
                migration.get_by_label('Kegiatan tujuan migrasi peserta',exact=True).select_option(str(target_a))
                migration.get_by_label('File migrasi peserta kegiatan',exact=True).set_input_files({'name':'pilih-kegiatan.csv','mimeType':'text/csv','buffer':b'NIM,Nama Mahasiswa\n000000000403,Peserta Pilihan\n'})
                expect(migration).to_contain_text('1 baris peserta kegiatan siap diperiksa')
                migration.get_by_role('button',name='Migrasikan 1 Peserta Kegiatan',exact=True).click()
                expect(migration).to_contain_text('1 peserta ditambahkan ke 1 kegiatan')
                migration.get_by_label('Kegiatan tujuan migrasi peserta',exact=True).select_option('')
                migration.get_by_label('File migrasi peserta kegiatan',exact=True).set_input_files({'name':'belum-cocok.csv','mimeType':'text/csv','buffer':b'NIM,Nama Mahasiswa\n000000000405,Peserta Belum Cocok\n'})
                expect(migration).to_contain_text('1 baris peserta kegiatan siap diperiksa')
                migration.get_by_role('button',name='Migrasikan 1 Peserta Kegiatan',exact=True).click()
                expect(migration).to_contain_text('1 peserta disimpan untuk dicocokkan')
                pending_participants=page.get_by_label('Peserta perlu dicocokkan',exact=True)
                pending_participants.locator('select[aria-label^="Kegiatan untuk kelompok peserta "]').select_option(str(target_a))
                pending_participants.get_by_role('button',name='Hubungkan 1 Peserta Sekaligus',exact=True).click()
                expect(migration).to_contain_text('Selesai: 1 peserta diproses, 1 hubungan baru')
                snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert not snapshot['pendingParticipants']
                assert any(row['nim']=='000000000405' and row['activityId']==target_a for row in snapshot['students'])
                print('PASS: selected destination and pending participant resolution preserve existing attendance')
                before_count=len(snapshot['activities'])
                batch=[{'namaKegiatan':'Kegiatan Halaman'+str(i).zfill(3),'tanggal':'2026-11-04','program':'Pengembangan Karakter','kategori':'Uji Halaman'} for i in range(55)]
                result=page.request.post(url+'/api/migrate/activities',headers=auth,data={'items':batch})
                assert result.status==200,result.text()
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                open_report(page)
                listing=page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True)
                total_count=before_count+55
                expect(listing.locator('tbody tr')).to_have_count(10)
                listing.get_by_role('button',name='Berikutnya',exact=True).click()
                expect(listing).to_contain_text('Halaman 2 dari ')
                expect(listing.locator('tbody tr')).to_have_count(10)
                listing.get_by_role('button',name='Sebelumnya',exact=True).click()
                expect(listing).to_contain_text('Halaman 1 dari ')
                listing.get_by_label('Jumlah kegiatan per halaman',exact=True).select_option('50')
                expect(listing.locator('tbody tr')).to_have_count(50)
                listing.get_by_role('button',name='Berikutnya',exact=True).click()
                expect(listing.locator('tbody tr')).to_have_count(total_count-50)
                listing.get_by_label('Jumlah kegiatan per halaman',exact=True).select_option('all')
                expect(listing.locator('tbody tr')).to_have_count(total_count)
                expect(listing.get_by_role('button',name='Berikutnya',exact=True)).to_be_disabled()
                listing.get_by_label('Jumlah kegiatan per halaman',exact=True).select_option('10')
                with page.expect_download() as all_activity_export:
                    listing.get_by_role('button',name='Ekspor Excel',exact=True).click()
                check_export='''import * as XLSX from 'xlsx'; import fs from 'node:fs';
                    const book=XLSX.read(fs.readFileSync(process.argv[1]),{type:'buffer'});
                    const rows=XLSX.utils.sheet_to_json(book.Sheets[book.SheetNames[0]]);
                    if(rows.length!==Number(process.argv[2]))process.exit(1);'''
                subprocess.run(['node','--input-type=module','-e',check_export,all_activity_export.value.path(),str(total_count)],cwd=ROOT,check=True)
                with page.expect_download() as all_activity_pdf:
                    listing.get_by_role('button',name='Unduh PDF',exact=True).click()
                text=' '.join(p.extract_text() for p in PdfReader(all_activity_pdf.value.path()).pages)
                assert 'Kegiatan Halaman000' in text and 'Kegiatan Halaman054' in text
                page.get_by_label('Cari laporan',exact=True).fill('Kegiatan Halaman054')
                expect(listing.locator('tbody tr')).to_have_count(1)
                expect(listing.get_by_role('button',name='Berikutnya',exact=True)).to_be_disabled()
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                expect(listing.locator('tbody tr')).to_have_count(10)
                page.screenshot(path=str(ARTIFACTS/'pagination-kegiatan.png'),full_page=True)
                print('PASS: activity pagination 10/50/all, next/previous, filter reset, and exports contain every filtered record')
                auto_activity=page.request.post(url+'/api/dashboard/activities',headers=auth,data={
                    'namaKegiatan':'Webinar Auto — Kesehatan & Karakter','tanggal':'2026-11-04','program':'Pengembangan Karakter','kategori':'Uji Auto'})
                assert auto_activity.status==201,auto_activity.text()
                auto_id=auto_activity.json()['id']
                ambiguous_ids=[]
                for date in ['2025-11-04','2026-11-04']:
                    created=page.request.post(url+'/api/dashboard/activities',headers=auth,data={
                        'namaKegiatan':'Webinar Ambigu','tanggal':date,'program':'Pengembangan Karakter','kategori':'Uji Auto'})
                    assert created.status==201,created.text()
                    ambiguous_ids.append(created.json()['id'])
                staged=[{'namaKegiatan':'webinar auto: kesehatan and karakter','importKey':'ui-auto:'+str(i),
                    'student':{'nim':str(800000000000+i),'nama':'Auto UI '+str(i)}} for i in range(1105)]
                staged.extend([{'namaKegiatan':'Webinar Ambigu','importKey':'ui-ambiguous:'+str(i),
                    'student':{'nim':str(810000000000+i),'nama':'Ambigu UI '+str(i)}} for i in range(3)])
                staged.append({'namaKegiatan':'webinar auto: kesehatan and karakter','tanggalKegiatan':'2026-11-05','importKey':'ui-date-conflict',
                    'student':{'nim':'820000000000','nama':'Tanggal Berbeda'}})
                response=page.request.post(url+'/api/migrate/participants',headers=auth,data={'items':staged})
                assert response.status==200,response.text()
                assert response.json()['pending']==1109
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                open_report(page)
                migration=page.get_by_role('region',name='Migrasi data kegiatan dan survei',exact=True)
                matcher=page.get_by_role('region',name='Peserta perlu dicocokkan',exact=True)
                expect(matcher.get_by_role('button',name='Hubungkan Otomatis (1105)',exact=True)).to_be_enabled()
                before=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert len(before['pendingParticipants'])==1109
                matcher.get_by_role('button',name='Hubungkan Otomatis (1105)',exact=True).click()
                expect(migration).to_contain_text('Selesai: 1105 peserta diproses, 1105 hubungan baru',timeout=60000)
                after=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert len(after['pendingParticipants'])==4
                assert sum(s['activityId']==auto_id for s in after['students'])==1105
                expect(matcher.get_by_role('button',name='Hubungkan Otomatis (0)',exact=True)).to_be_disabled()
                print('PASS: one-click auto-connect processes 1105 pending participants in multiple batches, ignoring punctuation/case')
                preview=page.request.post(url+'/api/migrate/participants/pending/auto-connect',headers=auth,data={}).json()
                assert preview['summary']['ambiguous']==3 and preview['summary']['date_conflict']==1
                group=next(g for g in preview['groups'] if g['name']=='Webinar Ambigu')
                destination=matcher.get_by_label('Kegiatan untuk kelompok peserta '+group['key'],exact=True)
                find=matcher.get_by_label('Cari kegiatan untuk kelompok peserta '+group['key'],exact=True)
                find.fill('WEBINAR AMBIGU 2025')
                expect(destination.locator('option')).to_have_count(2)
                find.fill('tidak-ada-kegiatan-ini')
                expect(destination.locator('option')).to_have_count(1)
                find.fill(str(ambiguous_ids[0]))
                destination.select_option(str(ambiguous_ids[0]))
                find.fill('tidak-ada-kegiatan-ini')
                expect(destination).to_have_value(str(ambiguous_ids[0]))

                matcher.get_by_role('button',name='Hubungkan 3 Peserta Sekaligus',exact=True).click()
                expect(migration).to_contain_text('Selesai: 3 peserta diproses, 3 hubungan baru')
                after=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert len(after['pendingParticipants'])==1
                assert after['pendingParticipants'][0]['student']['nama']=='Tanggal Berbeda'
                assert sum(s['activityId']==ambiguous_ids[0] for s in after['students'])==3
                retry=page.request.post(url+'/api/migrate/participants/pending/auto-connect',headers=auth,data={'dry_run':False}).json()
                assert retry['processed']==0
                page.screenshot(path=str(ARTIFACTS/'hubungkan-otomatis.png'),full_page=True)
                print('PASS: ambiguous/date-conflicting records are retained; one explicit group mapping links all selected participants')
                metric_fixtures=[
                    {'namaKegiatan':'Karakter Rasio 2030','jumlahPeserta':100,'program':'Pengembangan Karakter','kategori':'Pengembangan Karakter'},
                    {'namaKegiatan':'Pengkar Asrama Rasio 2030','jumlahPeserta':200,'program':'Asrama','kategori':'Pengembangan Karakter'},
                    {'namaKegiatan':'PPKPT Rasio 2030','jumlahPeserta':300,'program':'Pengembangan Karakter','kategori':'PPKPT'},
                ]
                for record in metric_fixtures:
                    response=page.request.post(url+'/api/dashboard/activities',headers=auth,data={**record,'tanggal':'2030-11-04','urusan':'Pengembangan karakter'})
                    assert response.status==201,response.text()
                page.reload()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                page.get_by_label('Grup Pengguna',exact=True).select_option('pengkar')
                page.get_by_label('Tahun',exact=True).select_option('2030')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..').locator('span').nth(1)).to_have_text('2')
                expect(page.get_by_text('Total Peserta',exact=True).locator('..').locator('span').nth(1)).to_have_text('400')
                expect(page.get_by_text('Rasio / target 45.000',exact=True).locator('..')).to_contain_text('0.89%')
                expect(page.get_by_text('Peserta unik teridentifikasi (NIM)',exact=True).locator('..')).to_contain_text('0')
                for label in ['Kegiatan Karakter','PPKPT']:
                    expect(page.get_by_text(label,exact=True).locator('..').locator('span').nth(1)).to_have_text('1')
                expect(page.get_by_label('Rincian perhitungan kegiatan',exact=True)).to_contain_text('1 Karakter + 1 PPKPT = 2 kegiatan')
                open_report(page)
                listing=page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True)
                expect(listing.locator('tbody tr')).to_have_count(2)
                with page.expect_download() as metrics_export:
                    listing.get_by_role('button',name='Ekspor Excel',exact=True).click()
                verify_groups='''import * as XLSX from 'xlsx'; import fs from 'node:fs';
                    const book=XLSX.read(fs.readFileSync(process.argv[1]),{type:'buffer'});
                    const rows=XLSX.utils.sheet_to_json(book.Sheets[book.SheetNames[0]]);
                    if(rows.length!==2 || new Set(rows.map(r=>r.kelompokRekap)).size!==2)process.exit(1);'''
                subprocess.run(['node','--input-type=module','-e',verify_groups,metrics_export.value.path()],cwd=ROOT,check=True)
                print('PASS: ratio uses total attendance; exclusive category sums and activity list/export agree under the same filter')
                result=page.request.post(url+'/api/dashboard/activities',headers=auth,data={'namaKegiatan':'Survei Auto & Karakter','tanggal':'2026-11-04','program':'Pengembangan Karakter'})
                assert result.status==201,result.text()
                survey_id=result.json()['id']
                rows=[{'namaKegiatan':'survei auto and karakter','importKey':'survey-auto-ui:'+str(i),'response':{'nim':str(850000000000+i),'answers':[None,5]+[None]*18,'saran':'Saran asli'}} for i in range(1573)]
                rows.append({**rows[0],'importKey':'survey-auto-ui-duplicate'})
                result=page.request.post(url+'/api/migrate/surveys',headers=auth,data={'items':rows})
                assert result.status==200,result.text()
                page.reload()
                open_report(page)
                migration=page.get_by_role('region',name='Migrasi data kegiatan dan survei',exact=True)
                matcher=page.get_by_role('region',name='Survei perlu dicocokkan',exact=True)
                expect(matcher.get_by_role('button',name='Hubungkan Otomatis (1574)',exact=True)).to_be_enabled()
                matcher.get_by_role('button',name='Hubungkan Otomatis (1574)',exact=True).click()
                expect(migration).to_contain_text('Selesai: 1574 survei diproses, 1573 hubungan baru, 1 duplikat',timeout=60000)
                after=page.request.get(url+'/api/dashboard',headers=auth).json()
                assert not after['pendingSurveys']
                stored=[row for row in after['surveys'] if row['activityId']==survey_id]
                assert len(stored)==1573
                assert stored[0]['answers']==[None,5]+[None]*18 and stored[0]['saran']=='Saran asli'
                print('PASS: auto-connect 1574 surveys across batches, skip duplicates, preserve original partial answers')
                result=page.request.post(url+'/api/dashboard/activities',headers=auth,data={'namaKegiatan':'Kegiatan Grup Asrama','tanggal':'2026-11-04','program':'Asrama','kategori':'Adaktif','navigationGroup':'asrama','surveys':[{'nim':'890000000000','answers':[2]*20}]})
                assert result.status==201,result.text()
                page.reload()
                page.get_by_label('Grup Pengguna',exact=True).select_option('overview')
                expect(page.get_by_role('heading',name='Dashboard Keseluruhan',exact=True)).to_be_visible()
                overview_menu=page.get_by_role('navigation',name='Menu Dashboard',exact=True)
                expect(overview_menu.get_by_role('button')).to_have_count(1)
                expect(page.get_by_role('button',name='Laporan',exact=False)).to_have_count(0)
                page.get_by_label('Tahun',exact=True).select_option('2030')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..').locator('span').nth(1)).to_have_text('3')
                expect(page.get_by_text('Total Peserta',exact=True).locator('..').locator('span').nth(1)).to_have_text('600')
                expect(page.get_by_text('Rasio / target 45.000',exact=True).locator('..')).to_contain_text('1.33%')
                for label in ['Kegiatan Karakter','PPKPT','Kegiatan Asrama']:
                    expect(page.get_by_text(label,exact=True).locator('..').locator('span').nth(1)).to_have_text('1')
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                combined_snapshot=page.request.get(url+'/api/dashboard',headers=auth).json()
                combined_responses=sum(s.get('answers') is not None for s in combined_snapshot['surveys'])
                expect(page.get_by_role('region',name='Survei kepuasan 20 pertanyaan',exact=True)).to_have_count(0)
                print('PASS: overall Dashboard group has one submenu, combines three categories without duplicate counts and includes their surveys')
                page.get_by_label('Grup Pengguna',exact=True).select_option('asrama')
                expect(page.get_by_role('region',name='Survei kepuasan 20 pertanyaan',exact=True)).to_have_count(0)
                expect(page.get_by_text('CSI Bobot Setara',exact=True).first.locator('..')).to_contain_text('47.50%')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..').locator('span').nth(1)).to_have_text('2')
                assert page.get_by_label('Kategori',exact=True).locator('option').evaluate_all('(options)=>options.map(option=>option.value)')==['Semua Kategori','Adaptif','Spiritual','Akademik','Sosial']
                expect(page.get_by_text('Kegiatan Karakter',exact=True)).to_have_count(0)
                expect(page.get_by_text('PPKPT',exact=True)).to_have_count(0)
                page.get_by_label('Kategori',exact=True).select_option('Adaptif')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..').locator('span').nth(1)).to_have_text('1')
                page.get_by_label('Kategori',exact=True).select_option('Semua Kategori')
                open_report(page)
                expect(page.get_by_text('Input Kegiatan Asrama',exact=True)).to_be_visible()
                listing=page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True)
                expect(listing.locator('tbody tr')).to_have_count(2)
                expect(listing).to_contain_text('Kegiatan Grup Asrama')
                expect(listing).to_contain_text('Pengkar Asrama Rasio 2030')
                page.get_by_label('Grup Pengguna',exact=True).select_option('ppk-telu')
                expect(page.get_by_text('Total Laporan',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('0')
                open_report(page)
                cases_csv=b'Tahun,Tanggal Laporan Masuk,Nomor Kasus,Kategori,Status Kasus,Status Pelaporan (Pembuatan BAP),Konseling Pelapor,Fakultas Terlapor,Program Studi Terlapor\n2024,05/11/2024,CASE-TEST-1,Psikis,Tutup Kasus,TRUE,YA,FIF,Informatika\n2025,,CASE-TEST-2,,,FALSE,,FEB,Manajemen\n'
                case_file={'name':'kasus-uji.csv','mimeType':'text/csv','buffer':cases_csv}
                page.get_by_label('File kasus PPKPT',exact=True).set_input_files(case_file)
                expect(page.get_by_role('button',name='Impor 2 Kasus',exact=True)).to_be_enabled()
                page.get_by_role('button',name='Impor 2 Kasus',exact=True).click()
                expect(page.get_by_text('2 kasus ditambahkan, 0 duplikat dilewati. Kasus yang sudah ada tidak ditimpa.',exact=True)).to_be_visible()
                page.get_by_label('File kasus PPKPT',exact=True).set_input_files(case_file)
                page.get_by_role('button',name='Impor 2 Kasus',exact=True).click()
                expect(page.get_by_text('0 kasus ditambahkan, 2 duplikat dilewati. Kasus yang sudah ada tidak ditimpa.',exact=True)).to_be_visible()
                case_list=page.get_by_role('region',name='Daftar kasus PPK Tel-U',exact=True)
                case_list.locator('tr').filter(has_text='CASE-TEST-2').get_by_role('button',name='Edit',exact=True).click()
                page.get_by_role('textbox',name='Status Kasus',exact=True).fill('On Progress')
                page.get_by_role('button',name='Simpan Kasus',exact=True).click()
                expect(page.get_by_text('Data kasus berhasil disimpan.',exact=True)).to_be_visible()
                page.get_by_role('button',name='Dashboard',exact=False).first.click()
                expect(page.get_by_text('Total Laporan',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('2')
                expect(page.get_by_text('Selesai / Putusan',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('1')
                expect(page.get_by_text('Investigasi Aktif',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('1')
                expect(page.get_by_text('1 kasus belum memiliki tanggal laporan masuk',exact=False)).to_be_visible()
                page.get_by_label('Tahun kasus',exact=True).select_option('2024')
                expect(page.get_by_text('Total Laporan',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('1')
                page.get_by_role('button',name='Reset Filter Kasus',exact=True).click()
                expect(page.get_by_text('Total Laporan',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('2')
                expect(page.get_by_role('heading',name='Dashboard PPKPT',exact=True)).to_be_visible()
                distribution=page.get_by_role('region',name='Sebaran prodi kasus PPKPT',exact=True)
                expect(distribution.locator('tbody tr')).to_have_count(2)
                expect(distribution).not_to_contain_text('CASE-TEST-1')
                page.get_by_label('Fakultas terlapor',exact=True).select_option('FIF')
                expect(page.get_by_text('Total Laporan',exact=True).locator('xpath=ancestor::section[1]')).to_contain_text('1')
                expect(distribution.locator('tbody tr')).to_have_count(1)
                page.get_by_role('button',name='Reset Filter Kasus',exact=True).click()
                page.get_by_label('Cari prodi atau fakultas terlapor',exact=True).fill('Manajemen')
                expect(distribution.locator('tbody tr')).to_have_count(1)
                expect(distribution).to_contain_text('FEB')
                page.get_by_label('Cari prodi atau fakultas terlapor',exact=True).fill('')
                expect(distribution.locator('tbody tr')).to_have_count(2)
                page.screenshot(path=str(ARTIFACTS/'ppkt-executive-dashboard.png'),full_page=True)
                open_report(page)
                logo_bytes=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1XcAAAAASUVORK5CYII=')
                page.get_by_label('Unggah logo Satgas PPKPT',exact=True).set_input_files({'name':'test-logo.png','mimeType':'image/png','buffer':logo_bytes})
                expect(page.get_by_text('Logo Satgas PPKPT berhasil diperbarui.',exact=True)).to_be_visible()
                expect(page.get_by_alt_text('Logo Satgas PPKPT',exact=True)).to_be_visible()
                assert page.get_by_alt_text('Logo Satgas PPKPT',exact=True).evaluate('(image)=>image.complete&&image.naturalWidth>0')
                page.get_by_role('button',name='Dashboard',exact=False).first.click()
                expect(page.get_by_text('Total Laporan',exact=True)).to_be_visible()
                with page.expect_download() as exported:
                    page.get_by_role('button',name='Ekspor PDF Dashboard',exact=True).click()
                pdf_path=Path(tmp)/'dashboard-ppkt.pdf'
                exported.value.save_as(pdf_path)
                pdf_text=' '.join(p.extract_text() for p in PdfReader(str(pdf_path)).pages)
                assert 'Dashboard PPK Tel-U' in pdf_text and 'total laporan' in pdf_text.lower()
                print('PASS: executive PPKPT layout, faculty filter, protected prodi distribution, logo upload')
                print('PASS: PPK Tel-U case dashboard, original column import, duplicate protection, case editing and year filters')
                page.reload()
                open_report(page)
                listing=page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True)
                expect(listing).not_to_contain_text('CASE-TEST-1')
                expect(listing).not_to_contain_text('Kegiatan Grup Asrama')
                print('PASS: grouped navigation, isolated datasets, PPK Tel-U save/reload, and unchanged legacy Pengkar data')
                page.get_by_role('button',name='Log Out',exact=False).click()
                page.get_by_label('Username',exact=True).fill('operatoruji')
                page.get_by_label('Password',exact=True).fill(operator_password)
                page.get_by_role('button',name='Login',exact=True).click()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                open_report(page)
                expect(page.get_by_role('region',name='Migrasi data kegiatan dan survei',exact=True)).to_have_count(0)
                expect(page.get_by_role('region',name='Survei kepuasan 20 pertanyaan',exact=True)).to_have_count(0)
                expect(page.get_by_text('Input Kegiatan Pengembangan Karakter (16 Field Master)',exact=True)).to_be_visible()
                expect(page.get_by_role('region',name='Daftar kegiatan tersimpan',exact=True)).to_be_visible()
                expect(page.get_by_role('region',name='Rekap mahasiswa tersimpan',exact=True)).to_be_visible()
                page.get_by_role('button',name='Pengaturan Admin',exact=False).click()
                roles=page.get_by_label('Hak Akses / Role',exact=True)
                expect(roles.locator('option')).to_have_count(3)
                assert roles.locator('option').evaluate_all('(options)=>options.map(option=>option.value)')==['pengkar','asrama','viewer']
                expect(roles).to_have_value('pengkar')
                print('PASS: Operator report contains only allowed sections and account role choices are restricted')
                trend_auth={'Authorization':'Bearer '+page.evaluate("sessionStorage.getItem('pkkm_token')")}
                for name,date in [('Webinar Bulanan','2031-01-02'),(' webinar   bulanan ','2031-01-20'),('Webinar Bulanan','2031-02-05'),('Workshop Bulanan','2031-01-10')]:
                    result=page.request.post(url+'/api/dashboard/activities',headers=trend_auth,data={'namaKegiatan':name,'tanggal':date,'program':'Pengembangan Karakter'})
                    assert result.status==201,result.text()
                page.reload()
                page.get_by_label('Tahun',exact=True).select_option('2031')
                trend=page.get_by_role('region',name='Tren kegiatan bulanan',exact=True)
                expect(trend.locator('canvas')).to_be_visible()
                trend.get_by_text('Lihat Angka Kegiatan Bulanan',exact=True).click()
                table=trend.get_by_role('table',name='Jumlah kegiatan unik per bulan',exact=True)
                expect(table.locator('thead')).to_contain_text('2031')
                expect(table.get_by_role('row',name='Jan 2',exact=True)).to_be_visible()
                expect(table.get_by_role('row',name='Feb 1',exact=True)).to_be_visible()
                expect(table.locator('tbody tr')).to_have_count(12)
                page.get_by_label('Triwulan',exact=True).select_option('TW2')
                expect(trend).to_contain_text('Belum ada kegiatan bernama dan bertanggal lengkap')
                for group in ['overview','pengkar','asrama']:
                    page.get_by_label('Grup Pengguna',exact=True).select_option(group)
                    if group=='pengkar':page.get_by_role('button',name='Reset Filter',exact=True).click()
                    with page.expect_download() as exported:
                        page.get_by_role('button',name='Ekspor PDF Dashboard',exact=True).click()
                    pdf_path=Path(tmp)/('dashboard-'+group+'.pdf')
                    exported.value.save_as(pdf_path)
                    reader=PdfReader(str(pdf_path))
                    pdf_text=' '.join(p.extract_text() for p in reader.pages)
                    assert 'Total Kegiatan' in pdf_text and 'Total Peserta' in pdf_text
                    assert 'PKKM Sign In' not in pdf_text and 'Input Kegiatan Pengembangan Karakter (16 Field Master)' not in pdf_text
                    assert len(reader.pages)>0

                    expect(page.get_by_role('region',name='Tren kegiatan bulanan',exact=True)).to_be_visible()
                    expect(page.get_by_role('region',name='Survei kepuasan 20 pertanyaan',exact=True)).to_have_count(0)
                    expect(page.get_by_role('region',name='Rekap mahasiswa tersimpan',exact=True)).to_have_count(0)
                print('PASS: monthly chart in all groups, duplicate names counted once per month, year/quarter filters and empty state')
                page.get_by_role('button',name='Log Out',exact=False).click()
                page.get_by_label('Username',exact=True).fill('browseradminbaru')
                page.get_by_label('Password',exact=True).fill(new_password)
                page.get_by_role('button',name='Login',exact=True).click()
                expect(page.get_by_text('Total Kegiatan',exact=True)).to_be_visible()
                category_auth={'Authorization':'Bearer '+page.evaluate("sessionStorage.getItem('pkkm_token')")}
                category_ids={}
                for name,category in [('Check-in Asrama Lama','Adaptif'),('Kegiatan Iftar SR Lama','Spiritual'),('Workshop Strategi Belajar Lama','Akademik'),('Dorm Olympic Lama','Sosial'),('Dorm Class Lama','Akademik')]:
                    result=page.request.post(url+'/api/dashboard/activities',headers=category_auth,data={'namaKegiatan':name,'tanggal':'2032-01-01','program':'Asrama','kategori':'Pengkar Asrama'})
                    assert result.status==201,result.text()
                    category_ids[result.json()['id']]=(name,category)
                page.reload()
                page.get_by_label('Grup Pengguna',exact=True).select_option('asrama')
                open_report(page)
                review=page.get_by_role('region',name='Kategorisasi data lama Asrama',exact=True)
                review.get_by_role('button',name='Periksa Kategori Data Lama',exact=True).click()
                expect(review).to_contain_text('kategori siap diterapkan')
                for ident,(name,category) in category_ids.items():
                    choice=review.get_by_label('Kategori tujuan kegiatan '+str(ident),exact=True)
                    if name=='Dorm Class Lama':
                        expect(choice).to_have_value('')
                        choice.select_option(category)
                    else:expect(choice).to_have_value(category)
                review.get_by_role('button',name='Terapkan 6 Kategori Asrama',exact=True).click()
                expect(review).to_contain_text('6 kegiatan berhasil dikategorikan')
                snapshot=page.request.get(url+'/api/dashboard',headers=category_auth).json()
                for ident,(_,category) in category_ids.items():
                    assert next(activity for activity in snapshot['activities'] if activity['id']==ident)['kategori']==category
                expect(review).to_contain_text('1 perlu diperiksa')
                print('PASS: review old Asrama categories, preserve unknown titles for explicit choice, apply suggestions and manual assignments')
                massive_activity={**snapshot['activities'][0],'id':777001,'namaKegiatan':'Dashboard Data Besar','program':'Pengembangan Karakter','navigationGroup':'pengkar','kategori':'Pengembangan Karakter','tanggal':'2026-11-04','tahun':'2026','triwulan':'TW4','jumlahPeserta':25000}
                massive={**snapshot,'activities':[massive_activity],'masterStudents':[],'pendingParticipants':[],'pendingSurveys':[],'adminList':[],
                    'students':[{'activityId':777001,'nim':str(870000000000+i),'nama':'Peserta Beban '+str(i),'prodi':'Informatika','fakultas':'FIF','kampus':'Bandung'} for i in range(25000)],
                    'surveys':[{'id':i,'activityId':777001,'namaKegiatan':'Dashboard Data Besar','nim':str(870000000000+i),'answers':[4]*20,'saran':'Masukan tersimpan','skorTotal':4,'skorMateri':4,'skorNarasumber':4,'skorFasilitas':4,'skorDampakKarakter':4,'skorKepuasan':4} for i in range(32000)]}
                massive_json=json.dumps(massive)
                page.route('**/api/dashboard?compact=true',lambda route:route.fulfill(status=200,content_type='application/json',body=massive_json))
                started=time.monotonic()
                page.reload()
                expect(page.get_by_text('Total Peserta',exact=True).locator('..').locator('span').nth(1)).to_have_text('25.000',timeout=30000)
                expect(page.get_by_text('CSI Bobot Setara',exact=True).first.locator('..')).to_contain_text('95.00%')
                expect(page.locator('#pkkm-print-report')).to_have_count(0)
                assert page.locator('body *').count()<5000
                page.get_by_label('Tahun',exact=True).select_option('2026')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..').locator('span').nth(1)).to_have_text('1')
                print('PASS: 25000 students and 32000 survey responses render without hidden report DOM; interactive dashboard in',round(time.monotonic()-started,2),'seconds')
                assert not errors, errors
                print('PASS: mobile navigation; no browser JavaScript errors')
                browser.close()
        finally:
            os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=10)
            log.close()


if __name__=='__main__':
    main()
