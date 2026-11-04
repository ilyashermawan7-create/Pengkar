"""Optional browser checks: python tests/browser_smoke.py.
Requires Playwright and Chromium; uses only a temporary database.
"""
import os
import io
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
                page.locator('input[type=file]').nth(0).set_input_files(participant_template.value.path())
                expect(page.get_by_text('1 peserta unik siap disimpan bersama kegiatan.',exact=True)).to_be_visible()
                print('PASS: download and reimport XLSX participant template')
                csv = b'Nama Mahasiswa,NIM / NPM,Program Studi (Prodi),Nama Fakultas,Lokasi Kampus\nPeserta Uji,123456789012,Informatika,FIF,Bandung\nPeserta Uji,123456789012,Informatika,FIF,Bandung\n'
                page.locator('input[type=file]').nth(0).set_input_files({'name':'peserta.csv','mimeType':'text/csv','buffer':csv})
                expect(page.get_by_text('1 peserta unik siap disimpan bersama kegiatan.',exact=True)).to_be_visible()
                expect(page.get_by_label('Jumlah Peserta',exact=True)).to_have_value('1')
                preview=page.get_by_label('Pratinjau peserta kegiatan',exact=True)
                expect(preview).to_contain_text('Peserta Uji')
                expect(preview).to_contain_text('belum disimpan')
                expect(preview).to_contain_text('1 baris NIM duplikat digabung')
                invalid=b'Nama Mahasiswa,NIM\nPeserta Salah,BAD\n'
                page.locator('input[type=file]').nth(0).set_input_files({'name':'salah.csv','mimeType':'text/csv','buffer':invalid})
                expect(page.get_by_role('alert')).to_contain_text('Baris 2')
                expect(preview).to_contain_text('Peserta Uji')
                print('PASS: common header aliases, visible preview and error; invalid import preserves previous draft')
                with page.expect_download() as survey_template:
                    page.get_by_role('button',name='Template Survey',exact=True).click()
                page.locator('input[type=file]').nth(1).set_input_files(survey_template.value.path())
                expect(page.get_by_text('1 respons survei siap disimpan.',exact=True)).to_be_visible()
                print('PASS: download and reimport XLSX survey template')
                survey = b'tanggalSurvey,NIM,skorMateri,skorNarasumber,skorFasilitas,skorDampak,Saran\n2026-11-04,123456789012,4,5,3,4,Uji browser\n'
                page.locator('input[type=file]').nth(1).set_input_files({'name':'survei.csv','mimeType':'text/csv','buffer':survey})
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
                expect(page.locator('#pkkm-print-report')).to_be_hidden()
                page.evaluate('() => { window.__printCalls=0; window.print=()=>{window.__printCalls+=1;}; }')
                page.get_by_role('button',name='Cetak / PDF',exact=True).click()
                page.wait_for_function('window.__printCalls >= 1',timeout=5000)
                page.emulate_media(media='print')
                expect(page.locator('#root')).to_be_hidden()
                expect(page.locator('#pkkm-print-report')).to_be_visible()
                pdf=page.pdf(path=str(ARTIFACTS/'laporan.pdf'),prefer_css_page_size=True,print_background=True)
                reader=PdfReader(io.BytesIO(pdf))
                text=' '.join(p.extract_text() for p in reader.pages)
                for expected in ['Kegiatan Uji Browser','Peserta Uji','123456789012','Rekap Data Mahasiswa','Data Kegiatan']:
                    assert expected in text, (expected,text)
                for forbidden in ['Input Kegiatan Pengembangan','Simpan & Publikasikan','Pilih File Mahasiswa','Kegiatan berhasil disimpan','MENU NAVIGASI']:
                    assert forbidden not in text, (forbidden,text)
                assert len(reader.pages)<=2,len(reader.pages)
                assert float(reader.pages[0].mediabox.width)>float(reader.pages[0].mediabox.height)
                page.emulate_media(media='screen')
                print('PASS: PDF contains report data in landscape, excludes application form/homepage')
                page.get_by_label('Cari laporan',exact=True).fill('TidakAdaHasilPDF')
                page.emulate_media(media='print')
                empty_pdf=page.pdf(prefer_css_page_size=True)
                empty_text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(empty_pdf)).pages)
                assert 'Tidak ada kegiatan sesuai filter' in empty_text
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
                page.emulate_media(media='print')
                large_pdf=page.pdf(path=str(ARTIFACTS/'laporan-banyak-mahasiswa.pdf'),prefer_css_page_size=True)
                large_text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(large_pdf)).pages)
                assert 'Cetak0' in large_text and 'Cetak134' in large_text
                assert '900000000134' in large_text
                page.emulate_media(media='screen')
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
                assert not errors, errors
                print('PASS: mobile navigation; no browser JavaScript errors')
                browser.close()
        finally:
            os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=10)
            log.close()


if __name__=='__main__':
    main()
