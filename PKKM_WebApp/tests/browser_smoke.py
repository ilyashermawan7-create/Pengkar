"""Optional browser checks: python tests/browser_smoke.py.
Requires Playwright and Chromium; uses only a temporary database.
"""
import os
import io
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
                print('PASS: real login rejects wrong password and accepts stored account')
                page.get_by_role('button',name='Laporan',exact=False).first.click()
                page.get_by_label('Nama Kegiatan *',exact=True).fill('Kegiatan Uji Browser')
                page.get_by_label('Tanggal Kegiatan *',exact=True).fill('2026-11-04')
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
                expect(page.get_by_role('status')).to_contain_text('Pertanyaan 1 wajib')
                print('PASS: blank satisfaction template has no fabricated scores and must be completed')
                survey = b'tanggalSurvey,NIM,skorMateri,skorNarasumber,skorFasilitas,skorDampak,Saran\n2026-11-04,123456789012,4,5,3,4,Uji browser\n'
                page.get_by_label('Berkas survei kegiatan',exact=True).set_input_files({'name':'survei.csv','mimeType':'text/csv','buffer':survey})
                expect(page.get_by_text('1 respons survei siap disimpan.',exact=True)).to_be_visible()
                page.get_by_role('button',name='Simpan & Publikasikan Kegiatan').click()
                expect(page.get_by_text('Kegiatan berhasil disimpan di server.',exact=True)).to_be_visible()
                expect(page.locator('tbody tr').first).to_contain_text('Kegiatan Uji Browser')
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
                page.get_by_role('button',name='Laporan',exact=False).first.click()
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
                expect(page.get_by_text('Indeks Kepuasan Total',exact=True).locator('..')).to_contain_text('4.00')
                page.get_by_label('Cari Mahasiswa Berdasarkan NIM / Kegiatan',exact=True).fill('not-found')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('0')
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                page.get_by_label('Triwulan',exact=True).select_option('TW1')
                expect(page.get_by_text('Total Kegiatan',exact=True).locator('..')).to_contain_text('0')
                page.get_by_role('button',name='Reset Filter',exact=True).click()
                expect(page.get_by_role('region',name='Rekap mahasiswa tersimpan',exact=True)).to_contain_text('Peserta Uji')
                page.screenshot(path=str(ARTIFACTS/'dashboard.png'),full_page=True)
                print('PASS: reload retains data and real charts; search and quarter filters update metrics')
                page.get_by_role('button',name='Laporan',exact=False).first.click()
                page.get_by_role('button',name='Edit',exact=True).first.click()
                expect(page.get_by_label('Nama Kegiatan *',exact=True)).to_have_value('Kegiatan Uji Browser')
                expect(page.get_by_label('Honor Pembicara (Rp)',exact=True)).to_have_value('Rp 250.000')
                page.get_by_label('Nama Kegiatan *',exact=True).fill('Kegiatan Uji Diedit')
                page.get_by_role('button',name='Simpan & Publikasikan Kegiatan').click()
                expect(page.get_by_text('Kegiatan berhasil disimpan di server.',exact=True)).to_be_visible()
                expect(page.locator('tbody tr').first).to_contain_text('Kegiatan Uji Diedit')
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
                expect(page.get_by_text('Indeks Kepuasan Total',exact=True).locator('..')).to_contain_text('4.00')
                print('PASS: persisted database, survey responses, and session survive server restart')
                page.get_by_role('button',name='Pengaturan Admin',exact=False).click()
                page.get_by_label('Username Admin *',exact=True).fill('operatoruji')
                page.get_by_label('Email Resmi Tel-U *',exact=True).fill('operator@example.test')
                page.get_by_label('Nama Lengkap Petugas *',exact=True).fill('Operator Uji')
                page.get_by_label('Password awal (minimal 12 karakter) *',exact=True).fill(secrets.token_urlsafe(24))
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
                page.get_by_role('button',name='Laporan',exact=False).first.click()
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
                with page.expect_download() as exported20:
                    survey_summary.get_by_role('button',name='Ekspor Jawaban Survei Kepuasan',exact=True).click()
                subprocess.run(['node','--input-type=module','-e',inspect_script,exported20.value.path()],cwd=ROOT,check=True)
                print('PASS: unchanged 20-question template/export, name matching, raw answers and idempotent survey migration')
                bad=io.StringIO();bad_writer=csv_tools.writer(bad);bad_writer.writerow(headers);bad_writer.writerow(['Kegiatan Tidak Ada',*rows[0][1:]])
                migration.get_by_label('File migrasi hasil survei',exact=True).set_input_files({'name':'salah-kegiatan.csv','mimeType':'text/csv','buffer':bad.getvalue().encode()})
                expect(migration).to_contain_text('tidak ditemukan atau tidak sesuai pilihan')
                expect(migration.get_by_role('button',name='Migrasikan 1 Respons Survei',exact=True)).to_be_disabled()
                with page.expect_download() as migrated_pdf:
                    page.get_by_role('button',name='Unduh PDF',exact=True).click()
                pdf_text=' '.join(p.extract_text() for p in PdfReader(migrated_pdf.value.path()).pages)
                assert 'meningkatkan pemahaman saya' in pdf_text
                assert 'Webinar Migrasi A' in pdf_text
                page.screenshot(path=str(ARTIFACTS/'migrasi-survei.png'),full_page=True)
                print('PASS: wrong activity is blocked and PDF includes satisfaction question analysis')
                assert not errors, errors
                print('PASS: mobile navigation; no browser JavaScript errors')
                browser.close()
        finally:
            os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=10)
            log.close()


if __name__=='__main__':
    main()
