import React, {useState} from 'react';
import * as XLSX from 'xlsx';

export default function StudentRecap({rows, activities}) {
  const [search,setSearch] = useState('');
  const names = new Map(activities.map(a=>[a.id,a.namaKegiatan]));
  const grouped = new Map();
  for (const student of rows) {
    if (!grouped.has(student.nim)) grouped.set(student.nim,{...student,kegiatan:new Map()});
    grouped.get(student.nim).kegiatan.set(student.activityId,names.get(student.activityId)||'Kegiatan');
  }
  const query=search.trim().toLowerCase();
  const students=[...grouped.values()].filter(student =>
    [student.nim,student.nama,student.prodi,student.fakultas,student.kampus,...student.kegiatan.values()]
      .some(value=>String(value||'').toLowerCase().includes(query))
  ).sort((a,b)=>a.nama.localeCompare(b.nama,'id'));
  const exportData = () => {
    const safe=value=>/^[=+@-]/.test(String(value))?"'"+value:value;
    const data=students.map(s=>Object.fromEntries(Object.entries({
      NIM:s.nim,Nama:s.nama,'Program Studi':s.prodi,Fakultas:s.fakultas,Kampus:s.kampus,
      'Jumlah Kegiatan':s.kegiatan.size,Kegiatan:[...s.kegiatan.values()].join('; '),
    }).map(([key,value])=>[key,safe(value)])));
    const workbook=XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook,XLSX.utils.json_to_sheet(data),'Rekap Mahasiswa');
    XLSX.writeFile(workbook,'Rekap_Mahasiswa_PKKM.xlsx');
  };
  return <section aria-label="Rekap mahasiswa tersimpan" className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold text-base text-slate-900">Rekap Data Mahasiswa</h2><p className="text-xs text-slate-500 mt-1">{grouped.size} mahasiswa unik dari daftar peserta kegiatan yang sudah disimpan. Mengikuti filter tahun, triwulan, dan kategori.</p></div><button disabled={!students.length} onClick={exportData} className="text-xs border rounded-xl px-4 py-2">Ekspor Rekap Mahasiswa</button></div>
    <input aria-label="Cari mahasiswa dalam rekap" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cari NIM, nama, prodi, fakultas, kampus, atau kegiatan" className="w-full border rounded-xl p-3 text-xs no-print" />
    <div className="overflow-x-auto"><table className="w-full text-xs text-left"><thead className="bg-slate-800 text-white"><tr>{['NIM','Nama Mahasiswa','Program Studi','Fakultas','Kampus','Kegiatan'].map(label=><th key={label} className="px-3 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">
      {students.slice(0,100).map(student=><tr key={student.nim}><td className="px-3 py-3 font-mono">{student.nim}</td><td className="px-3 py-3 font-semibold">{student.nama}</td><td className="px-3 py-3">{student.prodi||'—'}</td><td className="px-3 py-3">{student.fakultas||'—'}</td><td className="px-3 py-3">{student.kampus||'—'}</td><td className="px-3 py-3">{[...student.kegiatan.values()].join('; ')}</td></tr>)}
      {!students.length && <tr><td colSpan={6} className="p-6 text-slate-500 text-center">{grouped.size?'Tidak ada mahasiswa yang cocok dengan pencarian.':'Belum ada daftar mahasiswa tersimpan untuk filter ini. Impor peserta, lengkapi nama kegiatan, lalu klik Simpan & Publikasikan Kegiatan. Mengisi angka Jumlah Peserta saja tidak membuat daftar mahasiswa.'}</td></tr>}
    </tbody></table></div>
    {students.length>100&&<p className="text-xs text-slate-500">Menampilkan 100 dari {students.length} mahasiswa. Gunakan pencarian untuk mempersempit hasil; ekspor memuat seluruh hasil pencarian.</p>}
  </section>;
}
