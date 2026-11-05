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
- Impor massal dan pencocokan kegiatan: `frontend/MigrationPanel.jsx`, `frontend/migration.mjs`.
- Instrumen kepuasan dan pertanyaan asli: `survey_schema.json`, `frontend/SurveySummary.jsx`.
- Master mahasiswa dan survei yang belum cocok memakai tabel aditif
  `student_directory` dan `pending_surveys`. Data master tidak menaikkan
  kehadiran kegiatan. Nilai kosong survei memakai `null`, dan tanggal
  kegiatan yang belum diketahui memakai string kosong pada tabel lama
  dengan metadata Tahun tersendiri; tidak dibuat tanggal perkiraan.
- Migrasi peserta menambah relasi `activity_participants` tanpa mengganti
  daftar lama. Data tanpa NIM memakai `activity_unidentified_participants`
  dengan referensi master; pencocokan yang tertunda memakai
  `pending_participants`. Semua diperiksa menurut hak akses program.
- `participant_matching.py` menyediakan pencocokan nama kanonis yang
  konservatif, bukan fuzzy matching. Endpoint
  `POST /api/migrate/participants/pending/auto-connect` mendukung dry-run,
  batch maksimum 1.000, dan pemetaan kelompok eksplisit. UI ada pada
  `frontend/PendingParticipantMatcher.jsx`. Tanggal konflik/nama ambigu
  tidak dihubungkan otomatis; operasi dibatasi akun dan program yang diizinkan.
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

Survei kepuasan memakai 20 jawaban 1–5 dan satu saran bebas; pertanyaan asli
tidak diubah. Format lama empat skor tetap dibaca sebagai format legacy.
Skor kosong tidak diganti angka 5. Lihat [panduan migrasi](MIGRASI_DATA.md)
untuk template, penilaian, pencocokan kegiatan, dan aturan duplikat.
Impor sekarang menerima kolom kosong, menghitung rerata dari nilai terisi,
dan menyimpan survei tanpa kegiatan tujuan untuk dicocokkan belakangan.
Tanggal dan triwulan berasal dari tanggal kegiatan. Grafik, statistik,
peserta unik berdasarkan NIM, dan ekspor mengikuti filter yang sama.
Total peserta adalah akumulasi jumlah kehadiran; peserta unik hanya dihitung
dari daftar NIM yang benar-benar diimpor. Rasio memakai **Total Peserta
÷ 45.000 × 100%**, bukan peserta unik, dan tidak dibatasi maksimal 100%.
Analisis dimensi survei dihitung dari
respons individual, sehingga evaluasi agregat versi lama tetap ada pada API
lama dan skor tabel kegiatan, tetapi tidak dianggap sebagai respons individual.

Login pada HTML referensi dan OTP yang ditampilkan di layar adalah simulasi;
implementasi ini menggunakan pemeriksaan password server yang sebenarnya.
Google/SSO tetap dinonaktifkan seperti referensi; OTP belum diaktifkan.
Tidak ada sinkronisasi Looker Studio atau impor otomatis localStorage lama.

## Rekap kegiatan dashboard

`frontend/dashboardMetrics.mjs` menghitung seluruh metrik dari dataset hasil
filter yang sama dengan tabel dan ekspor. Total Kegiatan adalah jumlah rekaman
kegiatan sesuai filter; kartu juga menunjukkan pembanding seluruh kegiatan.
Pagination tidak membatasi perhitungan.

Setiap kegiatan masuk tepat satu kelompok rekap dengan prioritas PPKPT/PPKS/
kekerasan, kemudian Asrama/Resident/SR, lalu Karakter/Pengkar/Wawasan/Konseling/
Kesehatan Mental atau program Pengembangan Karakter. Sisanya ditampilkan
sebagai Lainnya. Ini mencegah acara Pengkar Asrama dihitung pada dua kartu.
Subtotal kelompok selalu berjumlah Total Kegiatan. Kategori asli tetap ada;
ekspor Excel menambahkan kolom `kelompokRekap` untuk pemeriksaan.

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
Tabel kegiatan pada `frontend/app.jsx` juga menyediakan pagination 10/50/Semua
dengan reset halaman saat filter berubah, terpisah dari dataset ekspor penuh.

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

## RAM pada Render Starter

`/api/dashboard` mengirim JSON bertahap melalui `StreamingResponse`, sehingga
FastAPI tidak membuat salinan rekursif seluruh data dan buffer JSON utuh.
Satu lock per worker membatasi penyusunan/pengiriman snapshot besar secara
bersamaan. Autentikasi dan cakupan hak akses tetap dijalankan sebelum data
tersedia. Isi respons tetap kompatibel dengan frontend; Cache-Control no-store.
Snapshot data sendiri masih dimuat di RAM, sehingga ini bukan batas memori
absolut. Jika Render masih melaporkan OOM pada volume lebih besar, periksa
Metrics dan pertimbangkan pagination server atau kapasitas RAM lebih besar.

Uji sintetis 75.000 baris mahasiswa: alokasi puncak tambahan proses encoding
JSON turun dari sekitar 40,56 MiB menjadi 0,57 MiB (tracemalloc; di luar memori
data awal dan proses server). Angka ini bukan pengukuran RAM produksi.

## Batas Operator KKA

Role `operator` pada Laporan menampilkan input kegiatan, daftar kegiatan
terpublikasi, dan rekap mahasiswa. Panel migrasi, master mahasiswa, serta
analisis survei terpisah disembunyikan. Filter dan ekspor daftar tetap tersedia.
Backend menolak semua endpoint `/api/migrate/*` untuk role ini dan tidak
mengirim master mahasiswa pada snapshot Operator KKA.

Pengaturan Admin tersedia bagi Super Admin dan Operator KKA. Operator KKA
hanya dapat membuat atau menonaktifkan `pengkar`, `asrama`, dan `viewer`;
daftar akun yang diterima juga dibatasi ke tiga role tersebut. Pembuatan dan
penonaktifan admin, operator lain, maupun verifier ditolak server. Hak penuh
Super Admin dan pembatasan program Operator Pengkar/Asrama tetap berlaku.

## Grup pengguna dan cakupan data

Sidebar memakai dropdown Grup Pengguna: Pengkar, Asrama, dan PPK Tel-U.
Dashboard dan Laporan mengikuti pilihan tersebut; Pengaturan Admin dan
Pengaturan tetap menjadi menu umum. Dropdown tidak mengubah role akun.

Data Asrama dikenali dari program Asrama, penanda grup Asrama, atau klasifikasi
kegiatan Asrama. Data tersebut dikeluarkan dari Pengkar, termasuk data lama
berpenanda navigationGroup=pengkar. Pengkar menampilkan kegiatan Pengembangan
Karakter dan PPKPT. PPK Tel-U tetap grup eksplisit tersendiri, berbeda dari
PPKPT. Pemisahan tampilan tidak mengubah atau menghapus record lama.

Jumlah peserta, kegiatan, grafik, rekap, survei, CSI, dan ekspor mengikuti ID
kegiatan yang lolos filter grup. Survei selalu mengikuti kegiatan asalnya.
Role dan pembatasan program backend tetap berlaku. Migrasi di Pengkar tetap
menyediakan seluruh kegiatan yang boleh diakses agar migrasi data lama Asrama
tetap dapat dilakukan. Grup baru disimpan melalui atribut navigationGroup.

Dropdown Grup Pengguna juga menyediakan Dashboard (ID `overview`) dengan
satu submenu Dashboard saja. Tampilan ini menggabungkan kegiatan Pengkar,
PPKPT, dan Asrama yang dapat diakses akun, tanpa duplikasi. Grup PPK Tel-U
tersendiri tidak ikut dihitung. Filter, peserta, grafik, dan survei mengikuti
kumpulan ID gabungan tersebut. Overview hanya mode tampilan, bukan grup
kegiatan baru yang disimpan di database; tidak ada formulir Laporan di sini.

## Tren kegiatan bulanan

Komponen MonthlyActivityTrend menerima kegiatan yang sudah difilter grup,
tahun, triwulan, kategori, dan pencarian dashboard. Grafik garis menampilkan
Januari–Desember dengan satu seri per tahun, termasuk bulan bernilai nol.
Nama dinormalisasi NFKC, huruf kecil, dan spasi, lalu dihitung unik untuk
setiap bulan/tahun. Nama yang sama lintas kategori atau grup pada dashboard
gabungan tetap satu kegiatan dalam bulan yang sama. Bulan berbeda dihitung
masing-masing satu kali. Grafik tidak mengubah hitungan kartu Total Kegiatan
atau record database. Nama kosong serta tanggal kosong/tidak valid tidak
ditebak dan jumlahnya diberi keterangan. Tabel angka tersedia di bawah grafik.

Dashboard seluruh grup tidak menampilkan tabel Survei Kepuasan Kegiatan —
Pertanyaan Asli dan Rekap Data Mahasiswa. Ringkasan analisis/CSI serta grafik
masih tampil. Kedua komponen detail tetap tersedia di Laporan sesuai role;
penyembunyian dashboard tidak menghapus data atau mengubah hak akses.

Dashboard Asrama menyembunyikan kartu Kegiatan Karakter dan PPKPT. Filter
kategori dan grafik per kategori memakai Adaptif, Spiritual, Akademik, Sosial.
Alias Adaktif/Spritual dikenali tanpa mengubah nilai asli di database. Record
lama tanpa kategori tersebut tetap masuk total Asrama dan tren bulanan;
jumlah yang belum terklasifikasi ditampilkan sebagai catatan. Form kegiatan
Asrama baru memakai pilihan kategori yang sama (default Adaptif); kategori
lama dipertahankan saat edit sampai pengguna memilih kategori baru.

## Pengategorian data lama Asrama

Saat startup, kategori lama yang belum baku disesuaikan melalui aturan konservatif
pada asrama_classification.py: normalisasi ejaan dan kata kunci eksplisit dari
judul, kemudian jenis/uraian bila judul belum memberi petunjuk. Hanya kegiatan
Asrama yang diproses; PPK Tel-U dikecualikan. Kategori yang sudah baku tidak
ditimpa. Riwayat kategori asli disimpan di asrama_category_history dan audit;
proses berulang tidak mengubah ulang kegiatan yang sudah memiliki riwayat.
Tidak ada perubahan pada nama, tanggal, peserta, atau respons survei.

Judul tanpa petunjuk atau dengan beberapa asas dibiarkan menunggu pemeriksaan,
bukan diisi Adaptif sebagai tebakan. Pada Grup Asrama → Laporan, Super Admin
dan Operator Asrama dapat membuka Periksa Kategori Data Lama, melihat alasan
saran, memilih kategori manual, kemudian menerapkan pilihan. Pagination 10/50/
semua dan pencarian tersedia; tombol menerapkan seluruh pilihan lintas halaman.

Endpoint GET/POST /api/dashboard/asrama/categories memeriksa role dan program,
mempertahankan kategori yang sudah baku, menolak update bersamaan yang sudah
berubah lewat expectedCategory, serta memvalidasi seluruh batch sebelum menulis.
API ini tidak tersedia untuk Operator KKA, Pengkar, Viewer, maupun Verifikator.

## Dashboard dengan data besar

PrintReport tidak lagi dipasang tersembunyi pada setiap render dashboard.
Komponen itu membangun tabel seluruh mahasiswa dan respons survei di DOM,
meskipun display:none; puluhan ribu baris dapat membuat browser tampak putih
atau macet saat login. Unduh PDF tetap melalui reportPdf.mjs dan hanya dibuat
saat pengguna menekan Unduh PDF. Pemeriksaan browser mencakup 25.000 mahasiswa
dan 32.000 respons dengan jumlah elemen halaman tetap di bawah 5.000.

Permintaan API memiliki batas 45 detik, mencakup pembacaan body respons.
Jika permintaan macet, AbortController mengembalikan pesan yang bisa dicoba
ulang dan status busy login dilepas melalui finally. Form login menampilkan
tahap pemeriksaan akun dan pemuatan dashboard; respons snapshot divalidasi
sebelum state diisi agar body yang tidak lengkap tidak membuat render gagal.
Tidak ada pengulangan otomatis permintaan tulis atau perubahan kredensial.

## Database kasus PPK Tel-U

Grup PPK Tel-U memakai PpktDashboard dan API /api/ppkt/*, bukan dashboard
kegiatan/CSI. Tabel ppkt_cases terpisah dari kegiatan, mahasiswa, dan survei.
Input/import/export mengikuti 19 kolom Kasus PPKPT.xlsx; DD/MM/YYYY, boolean
TRUE/FALSE dan konseling YA/TIDAK dikenali. Nilai kosong tetap kosong. Nomor
Kasus dinormalisasi sebagai kunci unik; impor ulang melewati kasus yang sudah
ada dan tidak menimpa status. Edit kasus dilakukan terpisah dengan audit.

Dashboard berisi rekap tahunan/bulanan, kategori, status asli dan ringkas,
progres BAP/surat tugas/fakultas/direktorat, serta konseling. Tanggal kosong
tidak dimasukkan ke tren bulanan. Status Tutup Kasus/Selesai dihitung ditutup,
Tarik Kasus/SK Pencabutan Kasus dihitung ditarik/dicabut, status kosong tidak
digabungkan ke dalam proses. Status lainnya menjadi dalam proses; teks asli
tetap disimpan. Tiga filter: tahun, kategori, kelompok status.

Super Admin mengelola dan mengekspor rincian, termasuk nomor dan keterangan.
Operator KKA dan Viewer hanya memperoleh agregat dashboard; Operator Pengkar,
Operator Asrama dan Verifikator tidak memperoleh API kasus. Respons dashboard
agregat tidak memuat nomor kasus atau narasi pribadi. Workbook pengguna dan
baris kasus tidak disimpan dalam repositori; unggah satu kali melalui PPK
Tel-U → Laporan → Impor Database Kasus setelah deployment.
