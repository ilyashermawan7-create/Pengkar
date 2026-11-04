# Migrasi kegiatan dan survei kepuasan

Setelah deployment terbaru Live, buka **Laporan → Impor / Migrasi Data Lama**.
Gunakan akun Super Admin atau Operator untuk kegiatan. Verifikator Survey
dapat mengimpor survei; Viewer hanya dapat membaca dan mengekspor.

## Database master mahasiswa (tanpa kegiatan)

Super Admin atau Operator KKA dapat membuka **Database Master Mahasiswa**
pada panel migrasi, mengunduh **Template Master Mahasiswa**, lalu mengimpor
Excel/CSV berisi NIM, Nama Mahasiswa, Program Studi, Fakultas, dan Kampus.
Nama, NIM, atau kolom lainnya boleh kosong. Baris yang seluruhnya kosong
dilewati; baris dengan sebagian data tetap disimpan.

Hasil muncul pada tabel **Database Master Mahasiswa** di menu Laporan,
termasuk data tanpa NIM atau nama dengan penanda Belum diisi. Master tidak
menambah jumlah peserta, kehadiran, atau kegiatan. Daftar peserta kegiatan
tetap memakai NIM untuk menghubungkan mahasiswa ke kegiatan.

NIM yang sama memperbarui master, tetapi kolom kosong tidak menghapus
informasi lama. Rekor tanpa NIM memakai identitas baris sumber, bukan NIM
buatan. Untuk melengkapi NIM rekor tersebut, gunakan **Ekspor Master
Mahasiswa**, pertahankan kolom **ID Master**, isi NIM/data yang diketahui,
lalu impor kembali. ID Master membantu memperbarui rekor yang sama tanpa
membuat salinan baru.

## 1. Impor kegiatan terlebih dahulu

1. Klik **Template Migrasi Kegiatan**.
2. Ganti baris contoh dengan data asli. Isi Nama Kegiatan, Tanggal Kegiatan,
   **Tahun**, Program, Kategori, dan field lain yang tersedia. Tanggal menerima
   `YYYY-MM-DD` atau `DD/MM/YYYY`. Program: Pengembangan Karakter atau Asrama.
3. Pilih file Excel/CSV pada **File migrasi kegiatan**, periksa pratinjau,
   lalu klik **Migrasikan … Kegiatan**.

Kegiatan dengan nama, tanggal, dan program yang sama dilewati, bukan ditimpa.
Impor tidak memperbarui kegiatan lama; gunakan Edit untuk koreksi. Spasi
berulang dan perbedaan huruf besar/kecil tidak membuat kegiatan baru.
Jumlah Peserta adalah jumlah kehadiran; daftar NIM/nama diimpor terpisah
dengan fitur peserta yang sudah ada.

Tanggal boleh kosong. Jika hanya Tahun yang diketahui, isi Tahun tanpa
membuat tanggal perkiraan: kegiatan tetap tersimpan dan dapat difilter
berdasarkan tahun tersebut, sedangkan tanggal/triwulan tetap kosong. Jika
tanggal dan Tahun sama-sama diisi, keduanya harus cocok. Nama dan jumlah
peserta yang belum diketahui juga tetap kosong; data tersebut tidak diubah
menjadi nama contoh atau jumlah peserta nol. Kegiatan belum lengkap dapat
dilengkapi melalui Edit.

## 2. Impor peserta kegiatan

Bagian **Import Peserta Kegiatan** tersedia untuk Super Admin, Operator KKA,
atau operator program terkait. Impor ini menghubungkan peserta ke kegiatan,
berbeda dengan impor Database Master Mahasiswa yang berdiri sendiri.

1. Klik **Template Migrasi Peserta Kegiatan**.
2. Isi ID/Nama Kegiatan, Tanggal Kegiatan bila diperlukan untuk membedakan
   nama yang sama, serta NIM, Nama Mahasiswa, Program Studi, Fakultas, Kampus.
3. Untuk daftar satu kegiatan yang tidak memiliki kolom kegiatan, pilih
   **Kegiatan tujuan peserta**. Untuk beberapa kegiatan sekaligus, biarkan
   pencocokan dari file dan isi metadata kegiatan pada setiap baris.
4. Pilih **File migrasi peserta kegiatan**, periksa pratinjau, lalu klik
   **Migrasikan … Peserta Kegiatan**.

Daftar lama tidak dihapus. NIM yang sama pada kegiatan yang sama dilewati,
dan impor berulang tidak menggandakan kehadiran. Kolom kosong tidak
menghapus nama/prodi/fakultas/kampus yang sebelumnya sudah diketahui.
Jumlah peserta kegiatan diperbarui minimal sebesar daftar peserta tersimpan;
jika angka rekap sebelumnya lebih besar, angka itu tidak diturunkan hanya
karena daftar nama yang diimpor belum lengkap.

Peserta tanpa NIM tetap disimpan sebagai data belum teridentifikasi dengan
identitas baris sumber, bukan NIM buatan. Rekap dan PDF menampilkan semua
data tersebut, sedangkan hitungan NIM unik hanya memakai NIM yang terisi.
NIM yang kemudian dilengkapi melalui ekspor/impor Master (pertahankan ID
Master) juga dihubungkan kembali ke riwayat kegiatan terkait.

Baris yang belum cocok dengan kegiatan disimpan dalam **Peserta Perlu
Dicocokkan**. Pilih tujuan dan klik **Hubungkan Peserta** kemudian. Baris
yang seluruh kolom mahasiswanya kosong dilewati, tanpa membuat peserta
buatan. Salah ketik NIM atau pelanggaran hak akses tetap harus diperbaiki.

## 3. Impor hasil survei kepuasan

1. Unduh **Template Survei Kepuasan 20 Pertanyaan**.
2. Isi Nama Kegiatan sama dengan daftar kegiatan. ID Kegiatan bersifat
   opsional dan harus merupakan ID di aplikasi tujuan ini, bukan ID dari
   sistem lain. Jika satu nama dipakai pada beberapa tanggal, isi Tanggal
   Kegiatan atau ID Kegiatan agar cocok dengan satu kegiatan.
3. Isi Tanggal Survey atau Timestamp/Stempel Waktu. Simpan Timestamp asli
   jika ada untuk membedakan beberapa pengisian pada hari yang sama.
4. Isi jawaban yang tersedia untuk 20 pertanyaan dan kolom
   **Saran Topik untuk Webinar selanjutnya**. Teks pertanyaan tidak perlu
   diubah: gunakan langsung judul kolom pada template atau ekspor Google Forms.
5. Pilih file pada **File migrasi hasil survei**. Periksa jumlah respons
   per kegiatan, lalu klik **Migrasikan … Respons Survei**.

Untuk file tanpa Nama Kegiatan/ID Kegiatan, pilih satu kegiatan tujuan pada
dropdown. Jika file sudah menyebut nama, tanggal, atau ID, informasi itu harus
sesuai pilihan; aplikasi tidak mengabaikan ketidakcocokan. File beberapa
kegiatan dapat diproses sekaligus menggunakan metadata masing-masing baris.

Nama kegiatan kosong, tidak ditemukan, atau ambigu tidak lagi membuat data
hilang: respons disimpan pada **Survei Perlu Dicocokkan**, terpisah dari
laporan kegiatan. Pilih kegiatan yang benar dan klik **Hubungkan Survei**
untuk menghubungkannya kemudian. Aplikasi tidak membuat kegiatan atau
menebak hubungan secara diam-diam. Tanggal survei boleh kosong. Nilai
terisi yang tidak valid (misalnya skor 9 atau tanggal 30 Februari) tetap
harus diperbaiki, agar tidak dianggap data yang sah.

## Penilaian dan pertanyaan asli

Seluruh teks pertanyaan disimpan di `survey_schema.json`, dipakai bersama
oleh template, API, tampilan, ekspor Excel, dan laporan PDF. Ada 20 pernyataan
yang dinilai dan satu pertanyaan saran bebas. Pertanyaan tidak diganti dengan
label ringkasan, dan nilai masing-masing pernyataan tetap tersimpan.

Skala yang diterima:

| Nilai | Label pernyataan |
| --- | --- |
| 1 | Sangat Tidak Setuju |
| 2 | Tidak Setuju |
| 3 | Netral / Ragu-ragu |
| 4 | Setuju |
| 5 | Sangat Setuju |

Angka 1–5, label di atas, atau bentuk `5 - Sangat Setuju` diterima. Label
kepuasan Sangat Tidak Puas sampai Sangat Puas juga dipetakan berurutan 1–5.
Jawaban, saran, atau kolom pertanyaan yang belum tersedia tetap kosong.
Template tidak berisi skor contoh. Seluruh pertanyaan asli tetap ada pada
laporan, termasuk pertanyaan yang belum memiliki jawaban.

- Indeks kepuasan: rerata jawaban yang terisi pada setiap respons, kemudian
  rerata antarrespons yang memiliki nilai. Kosong bukan nol dan bukan lima.
- Persentase: rerata dibagi 5, dikali 100 (persentase skor maksimum).
- Rerata tiap pertanyaan dan saran dapat dilihat di bagian
  **Survei Kepuasan Kegiatan — Pertanyaan Asli**.
- Jumlah jawaban terisi ditampilkan per pertanyaan. Bila seluruh jawaban
  kosong, skor ditampilkan sebagai belum ada nilai, bukan nol.
- Ringkasan dimensi memakai kelompok pertanyaan yang tercantum di
  `survey_schema.json`; pertanyaan dan jawaban mentah tetap tersedia.
- Label ringkasan aplikasi: rerata ≥4,5 Sangat Memuaskan; ≥3,5 Memuaskan;
  di bawahnya Perlu Perbaikan. Label ini bukan pengganti nilai per pertanyaan.

Format lama empat skor masih dapat diimpor agar data lama tetap tersedia,
tetapi tidak dianggap menjawab 20 pertanyaan. Bila respons 20 pertanyaan
tersedia, indeks dan dimensi memakai instrumen tersebut, tanpa mencampur
nilai format lama. Kedua format tetap disimpan.

## Duplikat dan data anonim

Impor survei menambah respons; tidak menghapus respons yang sudah ada.
Respons teridentifikasi dibandingkan menggunakan NIM, tanggal/Timestamp,
jawaban, dan saran. Nama dipakai jika NIM tidak tersedia. Respons dengan
Timestamp berbeda tetap dianggap pengisian berbeda.

Untuk respons tanpa NIM dan tanpa Timestamp, identitas sumber memakai hash
isi file dan nomor baris. Dua baris anonim dengan nilai sama tetap disimpan.
Mengimpor file yang sama kembali melewati baris yang sudah ada. Mengubah
susunan/isi file anonim mengubah identitas sumber; ekspor dari aplikasi
mempertahankan kolom ID Sumber untuk impor ulang yang konsisten.

## Memeriksa hasil

Tabel **Daftar Kegiatan Terpublikasi** menyediakan **Tampilkan kegiatan**
dengan pilihan 10, 50, dan Semua (All), serta tombol Sebelumnya/Berikutnya.
Pencarian atau perubahan filter mengembalikan tampilan ke halaman pertama.
Pagination hanya membatasi baris di layar; Excel dan PDF tetap mencakup
seluruh hasil filter, bukan hanya halaman yang sedang terlihat.

Atur filter tahun/triwulan sesuai tahun data lama, bukan hanya tahun berjalan.
Periksa tabel kegiatan, jumlah respons, nama kegiatan, dan ringkasan pertanyaan.
**Ekspor Jawaban Survei Kepuasan** mengunduh jawaban individual dengan judul
pertanyaan asli. **Unduh PDF** memuat ringkasan per pertanyaan bersama data
laporan sesuai filter.

Batas file: 10 MB, maksimal 10.000 baris per impor. Header dicari pada 30 baris
awal; sheet petunjuk dilewati. Impor berlangsung sebagai satu transaksi per
permintaan, dan hak akses program tetap diperiksa server.
