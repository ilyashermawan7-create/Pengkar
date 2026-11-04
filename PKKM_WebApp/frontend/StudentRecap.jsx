import React, {useState,useEffect} from 'react';
import * as XLSX from 'xlsx';

export default function StudentRecap({rows, activities,mode='participants'}) {
  const master=mode==='master';
  const [search,setSearch] = useState('');
  const [pageSize,setPageSize] = useState('10');
  const [page,setPage] = useState(1);
  const rowKeys=rows.map(row=>`${row.activityId}:${row.nim||row.directoryId}`).join(',');
  useEffect(()=>{setPage(1);},[rowKeys]);
  const names = new Map(activities.map(a=>[a.id,a.namaKegiatan]));
  const grouped = new Map();
  for (const student of rows) {
    const key=student.nim||student.directoryId;
    if (!grouped.has(key)) grouped.set(key,{...student,kegiatan:new Map()});
    if(student.activityId)grouped.get(key).kegiatan.set(student.activityId,names.get(student.activityId)||'Kegiatan');
  }
  const query=search.trim().toLowerCase();
  const students=[...grouped.values()].filter(student =>
    [student.nim,student.nama,student.prodi,student.fakultas,student.kampus,...student.kegiatan.values()]
      .some(value=>String(value||'').toLowerCase().includes(query))
  ).sort((a,b)=>a.nama.localeCompare(b.nama,'id'));
  const size=pageSize==='all'?Math.max(1,students.length):Number(pageSize);
  const pages=Math.max(1,Math.ceil(students.length/size));
  const currentPage=Math.min(page,pages);
  const start=(currentPage-1)*size;
  const visibleStudents=students.slice(start,start+size);
  const exportData = () => {
    const safe=value=>/^[=+@-]/.test(String(value))?"'"+value:value;
    const data=students.map(s=>Object.fromEntries(Object.entries({
      ...(master?{'ID Master':s.record_key||''}:{}),
      NIM:s.nim,Nama:s.nama,'Program Studi':s.prodi,Fakultas:s.fakultas,Kampus:s.kampus,
      'Jumlah Kegiatan':s.kegiatan.size,Kegiatan:[...s.kegiatan.values()].join('; '),
    }).map(([key,value])=>[key,safe(value)])));
    const workbook=XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook,XLSX.utils.json_to_sheet(data),'Rekap Mahasiswa');
    XLSX.writeFile(workbook,master?'Database_Master_Mahasiswa_PKKM.xlsx':'Rekap_Mahasiswa_PKKM.xlsx');
  };
  return <section aria-label={master?'Database master mahasiswa tersimpan':'Rekap mahasiswa tersimpan'} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold text-base text-slate-900">{master?'Database Master Mahasiswa':'Rekap Data Mahasiswa'}</h2><p className="text-xs text-slate-500 mt-1">{master?`${grouped.size} data master tersimpan, termasuk data tanpa NIM/nama. Tidak dihitung sebagai kehadiran kegiatan.`:`${grouped.size} mahasiswa unik dari daftar peserta kegiatan yang sudah disimpan. Mengikuti filter tahun, triwulan, dan kategori.`}</p></div><button disabled={!students.length} onClick={exportData} className="text-xs border rounded-xl px-4 py-2">{master?'Ekspor Master Mahasiswa':'Ekspor Rekap Mahasiswa'}</button></div>
    <div className="flex flex-wrap gap-3 items-center no-print"><input aria-label="Cari mahasiswa dalam rekap" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="Cari NIM, nama, prodi, fakultas, kampus, atau kegiatan" className="flex-1 min-w-48 border rounded-xl p-3 text-xs" /><label className="text-xs">Tampilkan mahasiswa<select aria-label="Jumlah mahasiswa per halaman" value={pageSize} onChange={e=>{setPageSize(e.target.value);setPage(1);}} className="border rounded-lg p-2 ml-2"><option value="10">10</option><option value="50">50</option><option value="all">Semua (All)</option></select></label></div>
    <div className="overflow-x-auto"><table className="w-full text-xs text-left"><thead className="bg-slate-800 text-white"><tr>{['NIM','Nama Mahasiswa','Program Studi','Fakultas','Kampus','Kegiatan'].map(label=><th key={label} className="px-3 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">
      {visibleStudents.map(student=><tr key={student.nim||student.directoryId}><td className="px-3 py-3 font-mono">{student.nim||'Belum diisi'}</td><td className="px-3 py-3 font-semibold">{student.nama||'Belum diisi'}</td><td className="px-3 py-3">{student.prodi||'—'}</td><td className="px-3 py-3">{student.fakultas||'—'}</td><td className="px-3 py-3">{student.kampus||'—'}</td><td className="px-3 py-3">{[...student.kegiatan.values()].join('; ')||'—'}</td></tr>)}
      {!students.length && <tr><td colSpan={6} className="p-6 text-slate-500 text-center">{grouped.size?'Tidak ada mahasiswa yang cocok dengan pencarian.':'Belum ada daftar mahasiswa tersimpan untuk filter ini. Impor peserta, lengkapi nama kegiatan, lalu klik Simpan & Publikasikan Kegiatan. Mengisi angka Jumlah Peserta saja tidak membuat daftar mahasiswa.'}</td></tr>}
    </tbody></table></div>
    <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600"><p>Menampilkan {students.length?start+1:0}–{Math.min(start+size,students.length)} dari {students.length} mahasiswa. Ekspor memuat seluruh hasil pencarian.</p><nav aria-label="Halaman rekap mahasiswa" className="flex items-center gap-3 no-print"><button disabled={currentPage===1} onClick={()=>setPage(currentPage-1)} className="border rounded-lg px-3 py-2">Sebelumnya</button><span>Halaman {currentPage} dari {pages}</span><button disabled={currentPage===pages} onClick={()=>setPage(currentPage+1)} className="border rounded-lg px-3 py-2">Berikutnya</button></nav></div>
  </section>;
}
