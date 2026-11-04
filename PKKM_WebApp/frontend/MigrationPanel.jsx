import React,{useState} from 'react';
import PendingParticipantMatcher from './PendingParticipantMatcher.jsx';
import {readActivities,readSurveyResponses,matchSurveyActivities,downloadActivityTemplate,downloadSatisfactionTemplate,readDirectory,downloadDirectoryTemplate,readActivityParticipants,downloadParticipantTemplate} from './migration.mjs';

export default function MigrationPanel({activities,role,api,reload,pendingSurveys=[],pendingParticipants=[]}) {
  const [participantDraft,setParticipantDraft]=useState([]);
  const [participantTarget,setParticipantTarget]=useState('');
  const [studentDraft,setStudentDraft]=useState([]);
  const [pendingTargets,setPendingTargets]=useState({});
  const [activityDraft,setActivityDraft]=useState([]);
  const [surveyDraft,setSurveyDraft]=useState([]);
  const [target,setTarget]=useState('');
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const canActivities=['admin','operator','pengkar','asrama'].includes(role);
  const canMaster=['admin','operator'].includes(role);
  if(role==='viewer')return null;
  const run=async(operation)=>{
    if(busy)return;
    setBusy(true);setMessage('');setError('');
    try{await operation();}catch(err){setError(err.message);}finally{setBusy(false);}
  };
  const selectFile=async(event,kind)=>{
    const file=event.target.files[0];event.target.value='';if(!file)return;
    await run(async()=>{
      if(kind==='participants'){
        const items=await readActivityParticipants(file);setParticipantDraft(items);
        setMessage(`${items.length} baris peserta kegiatan siap diperiksa. Belum disimpan.`);
      }else if(kind==='students'){
        const rows=await readDirectory(file);setStudentDraft(rows);
        setMessage(`${rows.length} baris master mahasiswa siap diimpor. Data kosong tetap kosong; belum disimpan.`);
      }else if(kind==='activities'){
        const rows=await readActivities(file);setActivityDraft(rows);
        setMessage(`${rows.length} baris kegiatan siap dimigrasikan dari ${file.name}. Belum disimpan.`);
      }else{
        const parsed=await readSurveyResponses(file);setSurveyDraft(parsed.items);
        setMessage(`${parsed.items.length} respons ${parsed.format==='legacy-4'?'format lama 4 skor':'survei kepuasan 20 pertanyaan'} siap diperiksa. Belum disimpan.`);
      }
    });
  };
  const commitStudents=()=>run(async()=>{
    const result=await api('/migrate/students',{method:'POST',body:JSON.stringify({items:studentDraft})});
    await reload();setStudentDraft([]);setMessage(`Impor master mahasiswa selesai: ${result.created} ditambahkan, ${result.updated} diperbarui, ${result.skipped} tanpa perubahan. Kolom kosong tidak menghapus data lama.`);
  });
  const commitActivities=()=>run(async()=>{
    const result=await api('/migrate/activities',{method:'POST',body:JSON.stringify({items:activityDraft})});
    await reload();setActivityDraft([]);setMessage(`Migrasi kegiatan selesai: ${result.created} ditambahkan, ${result.skipped} duplikat dilewati. Data lama tidak ditimpa.`);
  });
  const commitSurveys=()=>run(async()=>{
    const items=matchSurveyActivities(surveyDraft,activities,target,true);
    const result=await api('/migrate/surveys',{method:'POST',body:JSON.stringify({items})});
    await reload();setSurveyDraft([]);setMessage(`Migrasi survei selesai: ${result.created} respons ditambahkan ke ${result.activities} kegiatan, ${result.skipped} duplikat dilewati. ${result.pending||0} respons disimpan untuk dicocokkan. Respons lama tetap disimpan.`);
  });
  const participantPreview=matchSurveyActivities(participantDraft,activities,participantTarget,true);
  const commitParticipants=()=>run(async()=>{
    const items=matchSurveyActivities(participantDraft,activities,participantTarget,true);
    const result=await api('/migrate/participants',{method:'POST',body:JSON.stringify({items})});
    await reload();setParticipantDraft([]);setMessage(`Migrasi peserta selesai: ${result.created} peserta ditambahkan ke ${result.activities} kegiatan, ${result.skipped} duplikat/baris kosong dilewati, ${result.pending} peserta disimpan untuk dicocokkan. Daftar lama tidak dihapus.`);
  });
  let preview=[],matchError='';
  if(surveyDraft.length){
    try{preview=matchSurveyActivities(surveyDraft,activities,target,true);}catch(err){matchError=err.message;}
  }
  const counts=new Map();
  for(const item of preview)if(item.activityId)counts.set(item.activityId,{nama:item.namaKegiatan,count:(counts.get(item.activityId)?.count||0)+1});
  return <section aria-label="Migrasi data kegiatan dan survei" className="bg-white p-6 border border-slate-200 rounded-2xl space-y-5 no-print">
    <div><h2 className="font-bold text-lg">Impor / Migrasi Data Lama</h2><p className="text-xs text-slate-600 mt-1">Impor master mahasiswa dapat dilakukan tanpa kegiatan. Impor kegiatan dahulu untuk menghubungkan survei. Kolom kosong tetap diproses dan ditandai belum diisi. Excel/CSV maksimal 10 MB dan 10.000 baris.</p></div>
    {message&&<p role="status" className="bg-blue-50 text-blue-900 p-3 rounded-xl text-sm">{message}</p>}
    {error&&<p role="alert" className="bg-red-50 text-red-800 p-3 rounded-xl text-sm">{error}</p>}
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {canMaster&&<div className="p-4 border rounded-xl space-y-3"><h3 className="font-bold text-sm">Database Master Mahasiswa</h3><p className="text-xs text-slate-600">Impor NIM, nama, prodi, fakultas, dan kampus tanpa memilih kegiatan. NIM atau nama kosong tetap disimpan untuk dilengkapi. Master tidak menambah jumlah kehadiran kegiatan.</p><input aria-label="File database master mahasiswa" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event=>selectFile(event,'students')}/><div className="flex gap-2"><button disabled={busy} onClick={downloadDirectoryTemplate} className="border rounded-lg p-2 text-xs">Template Master Mahasiswa</button><button disabled={busy||!studentDraft.length} onClick={commitStudents} className="bg-emerald-700 text-white rounded-lg p-2 text-xs">Impor {studentDraft.length} Master Mahasiswa</button></div>{studentDraft.length>0&&<div className="max-h-52 overflow-auto text-xs"><table className="w-full text-left"><thead><tr><th>NIM</th><th>Nama</th><th>Prodi</th></tr></thead><tbody>{studentDraft.slice(0,20).map((row,index)=><tr key={index}><td className="p-2">{row.nim||'Belum diisi'}</td><td className="p-2">{row.nama||'Belum diisi'}</td><td className="p-2">{row.prodi||'—'}</td></tr>)}</tbody></table></div>}</div>}
      {canActivities&&<div className="p-4 border rounded-xl space-y-3"><h3 className="font-bold text-sm">1. Import Kegiatan Pengembangan Karakter / Asrama</h3><p className="text-xs text-slate-600">Kolom mengikuti 16 field kegiatan. Kegiatan dengan nama, tanggal, dan program yang sama dilewati; kegiatan lama tidak diubah.</p><input aria-label="File migrasi kegiatan" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event=>selectFile(event,'activities')}/><div className="flex flex-wrap gap-2"><button disabled={busy} onClick={downloadActivityTemplate} className="border rounded-lg p-2 text-xs">Template Migrasi Kegiatan</button><button disabled={busy||!activityDraft.length} onClick={commitActivities} className="bg-blue-700 text-white rounded-lg p-2 text-xs">Migrasikan {activityDraft.length} Kegiatan</button></div>
        {activityDraft.length>0&&<div className="overflow-auto max-h-64"><table className="w-full text-xs text-left"><thead><tr><th>Tanggal</th><th>Tahun</th><th>Nama Kegiatan</th><th>Program</th><th>Peserta</th></tr></thead><tbody>{activityDraft.slice(0,20).map((row,index)=><tr key={index}><td className="p-2">{row.tanggal||'—'}</td><td className="p-2">{row.tahun||'—'}</td><td className="p-2">{row.namaKegiatan||'Belum diisi'}</td><td className="p-2">{row.program}</td><td className="p-2">{row.jumlahPeserta??'—'}</td></tr>)}</tbody></table><p className="text-xs">Pratinjau {Math.min(20,activityDraft.length)} dari {activityDraft.length} baris.</p></div>}
      </div>}
      {canActivities&&<div className="p-4 border rounded-xl space-y-3"><h3 className="font-bold text-sm">2. Import Peserta Kegiatan</h3><p className="text-xs text-slate-600">Impor peserta untuk satu atau beberapa kegiatan. Gunakan Nama/ID Kegiatan dari file atau pilih tujuan di bawah. Daftar lama tetap ada; NIM yang sama pada kegiatan yang sama tidak digandakan. NIM/nama kosong tetap dipertahankan.</p>
        <label className="block text-xs font-semibold">Kegiatan tujuan peserta<select aria-label="Kegiatan tujuan migrasi peserta" value={participantTarget} onChange={event=>setParticipantTarget(event.target.value)} disabled={busy} className="block border p-2 rounded-lg w-full mt-1"><option value="">Cocokkan Nama / ID Kegiatan dari file</option>{activities.map(activity=><option key={activity.id} value={activity.id}>{activity.namaKegiatan||'Nama belum diisi'} · {activity.tanggal||activity.tahun||'Tanggal belum diisi'} · ID {activity.id}</option>)}</select></label>
        <input aria-label="File migrasi peserta kegiatan" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event=>selectFile(event,'participants')}/>
        <div className="flex gap-2"><button disabled={busy} onClick={downloadParticipantTemplate} className="border rounded-lg p-2 text-xs">Template Migrasi Peserta Kegiatan</button><button disabled={busy||!participantDraft.length} onClick={commitParticipants} className="bg-emerald-700 text-white rounded-lg p-2 text-xs">Migrasikan {participantDraft.length} Peserta Kegiatan</button></div>
        {participantPreview.length>0&&<div className="max-h-64 overflow-auto"><table className="w-full text-xs text-left"><thead><tr><th>Kegiatan</th><th>NIM</th><th>Nama</th><th>Status</th></tr></thead><tbody>{participantPreview.slice(0,20).map((item,index)=><tr key={index}><td className="p-2">{item.namaKegiatan||'Belum diisi'}</td><td className="p-2">{item.student.nim||'Belum diisi'}</td><td className="p-2">{item.student.nama||'Belum diisi'}</td><td className="p-2">{item.activityId?'Siap dihubungkan':'Disimpan untuk dicocokkan'}</td></tr>)}</tbody></table><p className="text-xs">Pratinjau {Math.min(20,participantPreview.length)} dari {participantPreview.length} baris. Jumlah peserta kegiatan tidak diturunkan jika rekap sebelumnya lebih besar.</p></div>}
      </div>}
      <div className="p-4 border rounded-xl space-y-3"><h3 className="font-bold text-sm">3. Import Hasil Survei Kepuasan</h3><p className="text-xs text-slate-600">Pertanyaan tetap sama. Jawaban kosong atau kolom pertanyaan yang belum ada tetap disimpan kosong; rerata hanya memakai jawaban terisi. Survei tanpa kegiatan tujuan disimpan untuk dicocokkan nanti.</p>
        <label className="block text-xs font-semibold">Pencocokan kegiatan<select aria-label="Kegiatan tujuan migrasi survei" value={target} onChange={event=>setTarget(event.target.value)} disabled={busy} className="block border p-2 rounded-lg w-full mt-1"><option value="">Cocokkan Nama / ID Kegiatan dari file</option>{activities.map(a=><option key={a.id} value={a.id}>{a.namaKegiatan} · {a.tanggal} · ID {a.id}</option>)}</select></label>
        <input aria-label="File migrasi hasil survei" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event=>selectFile(event,'surveys')}/>
        <div className="flex flex-wrap gap-2"><button disabled={busy} onClick={()=>downloadSatisfactionTemplate()} className="border rounded-lg p-2 text-xs">Template Survei Kepuasan 20 Pertanyaan</button><button disabled={busy||!preview.length||!!matchError} onClick={commitSurveys} className="bg-amber-700 text-white rounded-lg p-2 text-xs">Migrasikan {surveyDraft.length} Respons Survei</button></div>
        {matchError&&<p role="alert" className="text-red-700 text-xs">{matchError}</p>}
        {preview.length>0&&<ul className="text-xs space-y-1">{[...counts].map(([id,row])=><li key={id}>{row.nama} (ID {id}): {row.count} respons</li>)}</ul>}
        {preview.some(item=>!item.activityId)&&<p className="text-xs text-amber-800">{preview.filter(item=>!item.activityId).length} respons belum cocok; tetap dapat diimpor ke daftar Perlu Dicocokkan tanpa mengubah laporan kegiatan.</p>}
        <p className="text-xs text-slate-500">Impor berulang melewati respons identik; tidak menghapus respons sebelumnya. Nama ambigu tidak dihubungkan secara otomatis.</p>
      </div>
    </div>
    {canActivities&&<PendingParticipantMatcher activities={activities} pending={pendingParticipants} api={api} reload={reload} disabled={busy} onComplete={setMessage} />}
    {pendingSurveys.length>0&&<div aria-label="Survei perlu dicocokkan" className="border border-amber-200 rounded-xl p-4 space-y-3"><h3 className="font-bold">Survei Perlu Dicocokkan ({pendingSurveys.length})</h3>{pendingSurveys.slice(0,50).map(item=><div key={item.id} className="flex flex-wrap gap-2 items-center text-xs border-b pb-2"><span>Baris {item.sourceRow} · {item.namaKegiatan||'Nama kegiatan belum diisi'} · {item.response.nama||item.response.nim||'Responden tanpa identitas'}</span><select aria-label={'Kegiatan untuk survei tertunda '+item.id} value={pendingTargets[item.id]||''} onChange={event=>setPendingTargets({...pendingTargets,[item.id]:event.target.value})} className="border rounded-lg p-2"><option value="">Pilih kegiatan</option>{activities.map(activity=><option key={activity.id} value={activity.id}>{activity.namaKegiatan||'Nama belum diisi'} · {activity.tanggal||activity.tahun||'Tanggal belum diisi'} · ID {activity.id}</option>)}</select><button disabled={busy||!pendingTargets[item.id]} onClick={()=>run(async()=>{await api('/migrate/surveys/pending/'+item.id+'/resolve',{method:'POST',body:JSON.stringify({activityId:Number(pendingTargets[item.id])})});await reload();setMessage('Survei berhasil dihubungkan. Nilai kosong tetap kosong.');})} className="border rounded-lg p-2">Hubungkan Survei</button></div>)}</div>}
    {busy&&<p role="status" className="text-sm text-slate-500">Memproses migrasi…</p>}
  </section>;
}
