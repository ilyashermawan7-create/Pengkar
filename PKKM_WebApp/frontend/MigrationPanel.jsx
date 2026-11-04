import React,{useState} from 'react';
import {readActivities,readSurveyResponses,matchSurveyActivities,downloadActivityTemplate,downloadSatisfactionTemplate} from './migration.mjs';

export default function MigrationPanel({activities,role,api,reload}) {
  const [activityDraft,setActivityDraft]=useState([]);
  const [surveyDraft,setSurveyDraft]=useState([]);
  const [target,setTarget]=useState('');
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const canActivities=['admin','operator','pengkar','asrama'].includes(role);
  if(role==='viewer')return null;
  const run=async(operation)=>{
    if(busy)return;
    setBusy(true);setMessage('');setError('');
    try{await operation();}catch(err){setError(err.message);}finally{setBusy(false);}
  };
  const selectFile=async(event,kind)=>{
    const file=event.target.files[0];event.target.value='';if(!file)return;
    await run(async()=>{
      if(kind==='activities'){
        const rows=await readActivities(file);setActivityDraft(rows);
        setMessage(`${rows.length} baris kegiatan siap dimigrasikan dari ${file.name}. Belum disimpan.`);
      }else{
        const parsed=await readSurveyResponses(file);setSurveyDraft(parsed.items);
        setMessage(`${parsed.items.length} respons ${parsed.format==='legacy-4'?'format lama 4 skor':'survei kepuasan 20 pertanyaan'} siap diperiksa. Belum disimpan.`);
      }
    });
  };
  const commitActivities=()=>run(async()=>{
    const result=await api('/migrate/activities',{method:'POST',body:JSON.stringify({items:activityDraft})});
    await reload();setActivityDraft([]);setMessage(`Migrasi kegiatan selesai: ${result.created} ditambahkan, ${result.skipped} duplikat dilewati. Data lama tidak ditimpa.`);
  });
  const commitSurveys=()=>run(async()=>{
    const items=matchSurveyActivities(surveyDraft,activities,target);
    const result=await api('/migrate/surveys',{method:'POST',body:JSON.stringify({items})});
    await reload();setSurveyDraft([]);setMessage(`Migrasi survei selesai: ${result.created} respons ditambahkan ke ${result.activities} kegiatan, ${result.skipped} duplikat dilewati. Respons lama tetap disimpan.`);
  });
  let preview=[],matchError='';
  if(surveyDraft.length){
    try{preview=matchSurveyActivities(surveyDraft,activities,target);}catch(err){matchError=err.message;}
  }
  const counts=new Map();
  for(const item of preview)counts.set(item.activityId,{nama:item.namaKegiatan,count:(counts.get(item.activityId)?.count||0)+1});
  return <section aria-label="Migrasi data kegiatan dan survei" className="bg-white p-6 border border-slate-200 rounded-2xl space-y-5 no-print">
    <div><h2 className="font-bold text-lg">Impor / Migrasi Data Lama</h2><p className="text-xs text-slate-600 mt-1">Urutan: impor kegiatan dahulu, lalu impor hasil survei. Excel/CSV maksimal 10 MB dan 10.000 baris. Data hanya disimpan setelah tombol migrasi ditekan.</p></div>
    {message&&<p role="status" className="bg-blue-50 text-blue-900 p-3 rounded-xl text-sm">{message}</p>}
    {error&&<p role="alert" className="bg-red-50 text-red-800 p-3 rounded-xl text-sm">{error}</p>}
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {canActivities&&<div className="p-4 border rounded-xl space-y-3"><h3 className="font-bold text-sm">1. Import Kegiatan Pengembangan Karakter / Asrama</h3><p className="text-xs text-slate-600">Kolom mengikuti 16 field kegiatan. Kegiatan dengan nama, tanggal, dan program yang sama dilewati; kegiatan lama tidak diubah.</p><input aria-label="File migrasi kegiatan" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event=>selectFile(event,'activities')}/><div className="flex flex-wrap gap-2"><button disabled={busy} onClick={downloadActivityTemplate} className="border rounded-lg p-2 text-xs">Template Migrasi Kegiatan</button><button disabled={busy||!activityDraft.length} onClick={commitActivities} className="bg-blue-700 text-white rounded-lg p-2 text-xs">Migrasikan {activityDraft.length} Kegiatan</button></div>
        {activityDraft.length>0&&<div className="overflow-auto max-h-64"><table className="w-full text-xs text-left"><thead><tr><th>Tanggal</th><th>Nama Kegiatan</th><th>Program</th><th>Peserta</th></tr></thead><tbody>{activityDraft.slice(0,20).map((row,index)=><tr key={index}><td className="p-2">{row.tanggal}</td><td className="p-2">{row.namaKegiatan}</td><td className="p-2">{row.program}</td><td className="p-2">{row.jumlahPeserta}</td></tr>)}</tbody></table><p className="text-xs">Pratinjau {Math.min(20,activityDraft.length)} dari {activityDraft.length} baris.</p></div>}
      </div>}
      <div className="p-4 border rounded-xl space-y-3"><h3 className="font-bold text-sm">2. Import Hasil Survei Kepuasan</h3><p className="text-xs text-slate-600">Gunakan 20 pertanyaan asli sebagai judul kolom dan satu kolom saran. Angka 1–5 atau label Sangat Tidak Setuju sampai Sangat Setuju diterima. Jawaban kosong harus dilengkapi; tidak diisi nilai otomatis.</p>
        <label className="block text-xs font-semibold">Pencocokan kegiatan<select aria-label="Kegiatan tujuan migrasi survei" value={target} onChange={event=>setTarget(event.target.value)} disabled={busy} className="block border p-2 rounded-lg w-full mt-1"><option value="">Cocokkan Nama / ID Kegiatan dari file</option>{activities.map(a=><option key={a.id} value={a.id}>{a.namaKegiatan} · {a.tanggal} · ID {a.id}</option>)}</select></label>
        <input aria-label="File migrasi hasil survei" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event=>selectFile(event,'surveys')}/>
        <div className="flex flex-wrap gap-2"><button disabled={busy} onClick={()=>downloadSatisfactionTemplate()} className="border rounded-lg p-2 text-xs">Template Survei Kepuasan 20 Pertanyaan</button><button disabled={busy||!preview.length||!!matchError} onClick={commitSurveys} className="bg-amber-700 text-white rounded-lg p-2 text-xs">Migrasikan {surveyDraft.length} Respons Survei</button></div>
        {matchError&&<p role="alert" className="text-red-700 text-xs">{matchError}</p>}
        {preview.length>0&&<ul className="text-xs space-y-1">{[...counts].map(([id,row])=><li key={id}>{row.nama} (ID {id}): {row.count} respons</li>)}</ul>}
        <p className="text-xs text-slate-500">Nama harus cocok dengan satu kegiatan. Jika nama sama pada beberapa tanggal, isi ID Kegiatan atau Tanggal Kegiatan. Impor berulang melewati respons identik; tidak menghapus respons sebelumnya.</p>
      </div>
    </div>
    {busy&&<p role="status" className="text-sm text-slate-500">Memproses migrasi…</p>}
  </section>;
}
