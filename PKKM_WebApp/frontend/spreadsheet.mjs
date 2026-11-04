import * as XLSX from 'xlsx';

const aliases = {
  nim: ['nim','npm','nimnpm','nomorindukmahasiswa','nomorinduk','nimmahasiswa','nomorindukmahasiswanim','noindukmahasiswa'],
  nama: ['nama','namalengkap','namamahasiswa','namapeserta','namalengkapmahasiswa','namalengkappeserta','namasesuaiktm','namamahasiswasesuaiktm'],
  prodi: ['prodi','programstudi','programstudiprodi','prodiprogramstudi','namaprogramstudi'],
  fakultas: ['fakultas','namafakultas','asalfakultas'],
  kampus: ['kampus','asalkampus','lokasi','lokasikampus','namakampus','kampusasal'],
  namakegiatan: ['namakegiatan','kegiatan','judulwebinar','namawebinar','namakegiatanpengembangankarakter'],
};
const normalized = value => String(value).trim().toLowerCase().replace(/\(wajib\)/g,'').replace(/[^a-z0-9]/g,'');
const canonical = value => {
  const key = normalized(value);
  return Object.entries(aliases).find(([, options]) => options.includes(key))?.[0] || key;
};

export async function readSpreadsheet(file, kind='survey') {
  if (file.size > 10*1024*1024) throw Error('Ukuran file maksimal 10 MB.');
  const workbook = XLSX.read(await file.arrayBuffer(), {
    type:'array',cellDates:true,dateNF:'yyyy-mm-dd',sheetRows:10032,
  });
  let selected;
  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    const range = XLSX.utils.decode_range(sheet['!ref'] || 'A1');
    const rows = XLSX.utils.sheet_to_json(sheet,{header:1,defval:'',raw:true,blankrows:true});
    const index = rows.findIndex((row,i) => {
      if(i>=30)return false;
      const headers=row.map(canonical);
      if(kind==='activities')return headers.includes('namakegiatan')&&headers.some(h=>['tanggal','tanggalkegiatan','tanggalpelaksanaan','tahun','tahunkegiatan'].includes(h));
      if(kind==='directory')return headers.some(header=>['nim','nama','prodi','fakultas','kampus'].includes(header));
      if(kind==='participants')return headers.includes('nim')&&headers.includes('nama');
      return headers.includes('nim')||headers.includes('skormateri')||headers.includes('q01')||headers.includes('kegiataninimeningkatkanpemahamansayatentangtopikyangdibahas');
    });
    if (index>=0) { selected={sheetName,sheet,rows,index,range};break; }
  }
  if (!selected) throw Error(kind==='participants'
    ? 'Kolom Nama Mahasiswa dan NIM/NPM tidak ditemukan dalam 30 baris awal. Gunakan template atau periksa judul kolom file.'
    : kind==='activities'?'Kolom Nama Kegiatan dan Tanggal Kegiatan tidak ditemukan. Gunakan template kegiatan.'
    : 'Judul kolom survei tidak ditemukan dalam 30 baris awal. Gunakan template survei.');
  const {sheetName,sheet,rows,index,range} = selected;
  const headers = rows[index].map(canonical);
  const data = rows.slice(index+1).filter(row=>row.some(value=>String(value).trim()));
  if (!data.length || data.length>10000) throw Error('Berkas harus berisi 1–10.000 baris data.');
  const positions = new Map(rows.map((row,i)=>[row,i+range.s.r]));
  const rowNumber = row => positions.get(row)+1;
  const get = (row,...names) => {
    const column = headers.findIndex(h=>names.map(canonical).includes(h));
    if (column<0) return '';
    const value = row[column];
    if (headers[column]==='nim' && typeof value==='number') {
      if (!Number.isSafeInteger(value)) throw Error(`Baris ${rowNumber(row)}: NIM terlalu panjang atau tidak bulat. Simpan kolom NIM sebagai teks di Excel.`);
      const cell = sheet[XLSX.utils.encode_cell({r:positions.get(row),c:column+range.s.c})];
      // Preserve zeroes from Excel formats such as 000000000000.
      if (cell?.w && /^\d+$/.test(cell.w)) return cell.w;
    }
    return value instanceof Date ? (['timestamp','stempelwaktu','waktupengisian'].includes(headers[column])?value.toISOString():value.toISOString().slice(0,10)) : String(value??'').trim();
  };
  const has=(...names)=>names.some(name=>headers.includes(canonical(name)));
  return {data,get,has,rowNumber,sheetName};
}

export async function readParticipants(file) {
  const {data,get,rowNumber,sheetName} = await readSpreadsheet(file,'participants');
  const parsed = data.map(row => {
    const student = Object.fromEntries(['nim','nama','prodi','fakultas','kampus'].map(key=>[key,get(row,key)]));
    if (!/^\d{6,30}$/.test(student.nim)) {
      throw Error(`Baris ${rowNumber(row)}: NIM peserta harus berisi 6–30 angka untuk dihubungkan ke kegiatan. Untuk data tanpa NIM, gunakan impor Database Master Mahasiswa.`);
    }
    return student;
  });
  const students = [...new Map(parsed.map(student=>[student.nim,student])).values()];
  return {students,duplicateCount:parsed.length-students.length,sheetName};
}
