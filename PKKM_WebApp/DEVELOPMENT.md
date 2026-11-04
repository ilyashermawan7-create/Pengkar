# Dashboard sesuai referensi Pengkar.html

Frontend mempertahankan susunan login, sidebar, dashboard, form kegiatan,
analisis survei, pengaturan akun dan profil dari referensi. Grafik dan hitungan
menggunakan data server. Tidak ada data mahasiswa, kegiatan, atau hasil survei
contoh yang otomatis dimasukkan ke database.

## Menjalankan dan mengubah kode

Backend tetap FastAPI + SQLite. Jalankan dari `PKKM_WebApp`:

```sh
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000
```

Untuk database baru, tetapkan `PKKM_ADMIN_USER` dan `PKKM_ADMIN_PASSWORD`
(minimal 12 karakter) melalui pengaturan lingkungan yang aman. Untuk database
lama, akun dan password yang sudah tersimpan tetap dipakai.

- Tampilan dan perilaku UI: `frontend/app.jsx`.
- Gaya dan font: `frontend/styles.css`, `tailwind.config.js`.
- Endpoint dashboard, profil, akun, dan migrasi: `dashboard_api.py`.
- Endpoint lama yang masih dipertahankan: `server.py`.

Setelah mengedit frontend, bangun aset dan commit hasilnya:

```sh
npm ci
npm run build
```

`static/app.js`, `static/app.css`, font, dan pemberitahuan lisensi disimpan di
Git. Render dapat menjalankan hasil build tanpa Node, Babel, atau CDN.
`static/index.html` hanya menjadi halaman pemuat; jangan mengedit bundel
`static/app.js` secara langsung.

## Perubahan data dan hak akses

Migrasi menambahkan kolom profil/peran pada `users` serta tabel detail
kegiatan, master mahasiswa, relasi peserta, dan respons survei. Tidak ada
penghapusan tabel atau reset akun. Sebelum peningkatan pertama database
yang sudah berisi akun, aplikasi membuat backup SQLite konsisten di sebelah
database: `pkkm.before-dashboard-v2.sqlite3` untuk database Render standar.
Backup ini dibuat sekali, bukan pengganti backup rutin.

- Super Admin mengelola semua program dan akun.
- Operator KKA mengelola kedua program.
- Operator Pengkar dan Asrama dibatasi ke program masing-masing.
- Verifikator Survey dapat membaca laporan dan mengganti respons survei
  kegiatan yang dipilih, tanpa mengubah kegiatan atau akun.
- Viewer membaca laporan dan melakukan ekspor.

Menonaktifkan akun membatalkan sesinya dan mempertahankan riwayat kegiatan.
Pengguna dapat mengganti username, profil, dan password di Pengaturan.
Perubahan password memerlukan password lama dan membatalkan semua sesi akun.

## Impor dan perhitungan

Unduh template Excel melalui menu Laporan. Excel `.xlsx`, `.xls`, dan CSV
dibaca di browser; maksimal 10 MB dan 10.000 baris per impor.
Peserta dideduplikasi berdasarkan NIM pada setiap kegiatan. NIM harus berupa
teks berisi 6–30 angka agar angka nol di awal tidak hilang di Excel.
Impor pada form masih berupa draft sampai kegiatan disimpan. Saat mengedit,
berkas impor mengganti daftar peserta atau respons survei kegiatan itu.
Mengedit kegiatan tanpa impor baru mempertahankan daftar sebelumnya.

Pembaca peserta mengenali variasi kolom Nama Mahasiswa/Nama Lengkap,
NIM/NPM, Program Studi/Prodi, Fakultas, dan Kampus. Sheet petunjuk dilewati;
judul kolom dicari dalam 30 baris pertama setiap sheet. Pratinjau dan kesalahan
impor ditampilkan di dekat tombol pemilih file. File yang tidak valid tidak
mengganti daftar peserta yang sebelumnya sudah dipilih.

Rekap Data Mahasiswa tersedia pada dashboard dan laporan setelah kegiatan
disimpan. Rekap mengelompokkan NIM yang sama lintas kegiatan, mendukung
pencarian dan ekspor Excel. Filter kegiatan juga berlaku pada rekap. Kolom
prodi, fakultas, atau kampus yang kosong pada impor berikutnya tidak menghapus
informasi master mahasiswa yang sudah diketahui. Angka Jumlah Peserta tanpa
daftar NIM tetap merupakan jumlah kehadiran, bukan daftar mahasiswa.

Skor survei wajib 1–5 pada keempat dimensi; skor kosong tidak diganti angka 5.
Tanggal dan triwulan berasal dari tanggal kegiatan. Grafik, statistik,
peserta unik berdasarkan NIM, dan ekspor mengikuti filter yang sama.
Total peserta adalah akumulasi jumlah kehadiran; peserta unik hanya dihitung
dari daftar NIM yang benar-benar diimpor. Rasio membandingkan peserta unik
dengan target 45.000 dari referensi. Analisis dimensi survei dihitung dari
respons individual, sehingga evaluasi agregat versi lama tetap ada pada API
lama dan skor tabel kegiatan, tetapi tidak dianggap sebagai respons individual.

Login pada HTML referensi dan OTP yang ditampilkan di layar adalah simulasi;
implementasi ini menggunakan pemeriksaan password server yang sebenarnya.
Google/SSO tetap dinonaktifkan seperti referensi; OTP belum diaktifkan.
Tidak ada sinkronisasi Looker Studio atau impor otomatis localStorage lama.

## Cetak dan PDF

Tombol **Unduh PDF** membuat file `Laporan_PKKM.pdf` langsung dari data memakai
`frontend/reportPdf.mjs` (jsPDF dan AutoTable). Tombol ini tidak menggunakan
`window.print`, screenshot, atau HTML homepage. Font lokal berlisensi OFL
disertakan di `static/fonts/report-sans.ttf` (konversi font Latin 400 yang sama
dengan font aplikasi dari WOFF menjadi TTF menggunakan FontTools).
Dokumen berisi kegiatan, rekap mahasiswa, dan respons survei sesuai filter
laporan. Seluruh hasil filter masuk PDF meskipun tampilan dipaginasi 10 atau
50 baris. Formatnya A4 landscape, header tabel berulang, dan nomor halaman.

Rekap mahasiswa menyediakan pilihan 10, 50, dan Semua, navigasi Sebelumnya /
Berikutnya, serta pencarian. Jumlah baris layar tidak membatasi ekspor Excel
maupun PDF. `frontend/PrintReport.jsx` tetap menyediakan tampilan khusus cetak
untuk Ctrl+P, tetapi bukan jalur tombol unduh PDF.

Halaman utama dikirim dengan `Cache-Control: no-store`. Build menambahkan
hash konten pada URL aset JS/CSS di `static/index.html` agar versi kode dan
gaya yang baru dimuat bersama setelah deployment.

## Validasi

Instal dependensi uji terpisah bila belum tersedia:

```sh
pip install httpx
python -m unittest discover -s tests -v
```

Uji pembacaan spreadsheet dan variasi template:

```sh
npm run test:imports
```

Untuk uji UI opsional, instal Playwright dan sediakan Chromium:

```sh
pip install playwright pypdf
# Gunakan Chromium sistem melalui CHROMIUM_PATH bila tidak bernama chromium.
python tests/browser_smoke.py
```

Kedua runner membuat database sementara; tidak menggunakan database layanan.
Screenshot browser disimpan di `/tmp/pkkm-browser-artifacts`.

Deploy tetap menggunakan `render.yaml`, branch `work`, dan disk `/var/data`.
Setelah Render menandai deployment Live, muat ulang aplikasi dan login dengan
akun lama. Data produksi dan URL publik harus diperiksa di layanan Render;
keberhasilan uji lokal bukan bukti deployment publik telah selesai.
