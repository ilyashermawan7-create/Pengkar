# Deploy PKKM di Render

Konfigurasi `render.yaml` menyiapkan layanan Python berbayar (Starter),
region Singapore, dan disk permanen 1 GB. Periksa biaya terbaru di Render
sebelum membuat layanan. Gunakan satu instance dan satu worker untuk SQLite.

1. Login atau daftar di https://dashboard.render.com/.
2. Pilih **New → Blueprint** lalu hubungkan repositori GitHub
   `ilyashermawan7-create/Pengkar`. Izinkan akses repositori bila diminta.
3. Pilih branch **work**, dengan Blueprint Path `render.yaml` di root repositori.
4. Isi variabel rahasia di Render (jangan di GitHub atau chat):
   - `PKKM_ADMIN_USER`: nama pengguna administrator pilihan Anda.
   - `PKKM_ADMIN_PASSWORD`: password unik dan kuat, minimal 12 karakter.
5. Periksa paket Starter dan disk 1 GB, lalu buat/deploy Blueprint.
6. Tunggu layanan berstatus **Live**, buka URL HTTPS yang diberikan Render,
   dan login memakai akun administrator tadi.
7. Buat satu kegiatan percobaan. Restart layanan lalu pastikan kegiatan
   masih tersimpan. Buat akun pengguna lain melalui pengelolaan pengguna.

Database disimpan di `/var/data/pkkm.sqlite3`, di luar folder kode. Jangan
menghapus disk atau mengganti lokasi database saat memperbarui aplikasi.
Jangan gunakan paket Free untuk konfigurasi SQLite ini karena membutuhkan
disk permanen. Tetapkan prosedur backup SQLite yang konsisten sebelum
menyimpan data penting; ekspor CSV bukan backup lengkap akun dan database.

Akun administrator hanya dibuat ketika tabel pengguna masih kosong.
Mengganti `PKKM_ADMIN_PASSWORD` setelah itu tidak mengganti password akun
yang sudah tersimpan. Simpan kredensial awal di pengelola password.

Jika login tidak bisa digunakan, periksa variabel admin dan log startup di
Render. Bila deploy gagal, periksa log Build/Events dan pastikan branch,
Blueprint Path, serta disk sesuai konfigurasi di atas.

Konfigurasi ini belum membuktikan deployment publik berhasil. Pemeriksaan
lokal dilaporkan terpisah; URL publik baru tersedia setelah Render membuat
layanan. Aplikasi ini ditujukan untuk uji coba internal sesuai README aplikasi.
