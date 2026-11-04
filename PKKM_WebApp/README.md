# Dashboard PKKM — Web App v1.0

Pengembangan dari dashboard HTML KKA: difokuskan pada **Pengembangan Karakter** dan **Asrama**, dengan pelaporan, evaluasi, multi-user, dan SQLite terpusat.

Dashboard kini mengikuti referensi `Pengkar.html`: grafik dan filter, formulir
16 field, impor peserta/survei Excel atau CSV, pengelolaan akun, profil, serta
penggantian username dan password. Lihat [panduan pengembangan](DEVELOPMENT.md)
untuk lokasi kode, perhitungan, migrasi data, dan cara membangun frontend.

Impor massal kegiatan dan hasil survei tersedia di menu Laporan. Instrumen
kepuasan mempertahankan 20 pertanyaan asli serta pertanyaan saran topik.
Ikuti [panduan migrasi data](MIGRASI_DATA.md) untuk memakai template Excel/CSV
dan mencocokkan survei dengan nama kegiatan yang benar.

## Menjalankan (Windows PowerShell)

```powershell
cd PKKM_WebApp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PKKM_ADMIN_USER="admin"
$env:PKKM_ADMIN_PASSWORD="GANTI_DENGAN_PASSWORD_KUAT_2026!"
uvicorn server:app --host 127.0.0.1 --port 8000
```

Buka http://127.0.0.1:8000. **Ubah password contoh di atas** sebelum penggunaan. Saat pertama kali berjalan, akun admin dibuat dari environment variable. Untuk Linux/macOS, gunakan `python3 -m venv .venv`, `source .venv/bin/activate`, dan `export PKKM_ADMIN_USER=...` serta `export PKKM_ADMIN_PASSWORD=...`.

## Multi-user dan server bersama

- Jalankan di **satu server** yang bisa diakses pengguna melalui jaringan kampus; semua pengguna berbagi database SQLite di server tersebut (`pkkm.sqlite3`). Jangan menyalin database ke komputer masing-masing.
- Role: `admin` (semua data dan pengguna), `operator` (kedua program), `pengkar` (program Pengembangan Karakter), `asrama` (program Asrama), `verifier` (impor respons survei), `viewer` (baca/ekspor saja).
- Untuk akses dari luar localhost, wajib pasang reverse proxy HTTPS, firewall, pembatasan jaringan/VPN, dan kebijakan backup. **Jangan mengekspos `uvicorn` langsung ke internet.**
- Backup database menggunakan SQLite backup API / `sqlite3 .backup`, bukan menyalin file aktif tanpa konsistensi. Batasi hak akses file DB pada akun layanan.
- Untuk produksi skala besar, migrasikan SQLite ke PostgreSQL, tambahkan SSO kampus, MFA, reset password, rate limiting login, monitoring, dan kebijakan retensi data.

## Fungsi

1. Rekap KPI: kegiatan, realisasi, jumlah peserta, anggaran, cakupan evaluasi, skor dampak.
2. Form kegiatan: tanggal, program, kategori, target/realisasi peserta, biaya, eviden, laporan, kendala, tindak lanjut.
3. Evaluasi: responden, skor materi/narasumber/fasilitas/dampak (skala 1–5), temuan dan rekomendasi.
4. Filter program/tahun, ekspor laporan CSV, daftar tindak lanjut.
5. Pengelolaan akun berdasarkan role dan log audit perubahan.

## Batasan & migrasi

- **Data lama dari file HTML belum otomatis dipindahkan**. Dashboard lama menggunakan localStorage dan struktur field berbeda; diperlukan pemetaan dan persetujuan sebelum impor, terutama bila memuat data pribadi mahasiswa.
- Daftar mahasiswa dan respons survei individual dapat diimpor melalui form kegiatan. Tidak ada data contoh atau skor survei buatan yang otomatis dimasukkan ke database.
- Belum tersedia unggah file eviden (menggunakan tautan URL), lampiran laporan PDF, approval berjenjang, atau survei responden langsung.
- Jumlah peserta = total kehadiran lintas kegiatan. Peserta unik dihitung dari NIM pada daftar peserta yang diimpor. Analisis dashboard memakai respons survei individual; API ringkasan lama tetap memakai evaluasi agregat kegiatan. Skor survei bukan bukti perubahan karakter jangka panjang.
- Ini versi awal fungsional untuk uji coba internal, **belum lolos audit keamanan dan belum dinyatakan siap produksi**.

## API

Dokumentasi interaktif setelah login server: `/docs` (endpoint memerlukan token untuk data). Database otomatis dibuat saat aplikasi dijalankan.
