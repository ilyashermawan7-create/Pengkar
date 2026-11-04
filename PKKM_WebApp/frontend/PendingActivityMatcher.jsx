import React,{useEffect,useState} from 'react';

const statusLabels={matched:'Cocok unik',ambiguous:'Lebih dari satu kegiatan',unmatched:'Nama belum ditemukan',date_conflict:'Tanggal tidak cocok',blank:'Nama kegiatan belum diisi'};

export default function PendingActivityMatcher({activities,pending,api,reload,disabled=false,onComplete,kind='participants'}){
  const noun=kind==='surveys'?'survei':'peserta';
  const capital=kind==='surveys'?'Survei':'Peserta';
  const heading=capital+' Perlu Dicocokkan';
  const sectionLabel=capital+' perlu dicocokkan';
  const endpoint='/migrate/'+kind+'/pending/auto-connect';
  const [plan,setPlan]=useState(null);
  const [targets,setTargets]=useState({});
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');
  const [search,setSearch]=useState('');
  const [size,setSize]=useState('10');
  const [page,setPage]=useState(1);
  const pendingKeys=pending.map(record=>record.id).join(',');
  const inspect=async()=>{
    const next=await api(endpoint,{method:'POST',body:JSON.stringify({dry_run:true})});
    setPlan(next);return next;
  };
  useEffect(()=>{
    if(!pending.length){setPlan(null);return;}
    let active=true;
    api(endpoint,{method:'POST',body:JSON.stringify({dry_run:true})})
      .then(next=>{if(active)setPlan(next);}).catch(err=>{if(active)setError(err.message);});
    return()=>{active=false;};
  },[pendingKeys,activities,kind]);
  if(!pending.length)return null;
  const check=async()=>{
    if(busy||disabled)return;
    setBusy(true);setError('');
    try{await inspect();setMessage('Kecocokan sudah diperiksa ulang. Belum ada data yang dihubungkan.');}
    catch(err){setError(err.message);}finally{setBusy(false);}
  };
  const connect=async(group=null)=>{
    if(busy||disabled)return;
    setBusy(true);setError('');setMessage('Memulai pencocokan…');
    let processed=0,created=0,skipped=0;
    try{
      for(;;){
        const body={dry_run:false,limit:1000,...(group?{groupKey:group.key,activityId:Number(targets[group.key])}:{})};
        const result=await api(endpoint,{method:'POST',body:JSON.stringify(body)});
        processed+=result.processed;created+=result.created;skipped+=result.skipped;
        setMessage(`${processed} ${noun} diproses: ${created} hubungan baru, ${skipped} duplikat dilewati. Jangan tutup halaman sampai selesai.`);
        if(!result.processed||(group?result.remainingGroup:result.remainingMatched)===0)break;
      }
      await reload();await inspect();
      const complete=`Selesai: ${processed} ${noun} diproses, ${created} hubungan baru, ${skipped} duplikat dilewati. Data yang belum pasti tetap menunggu pencocokan.`;
      setMessage(complete);onComplete?.(complete);
    }catch(err){
      setError(`${err.message} ${processed} ${noun} sudah diproses. Periksa ulang sebelum melanjutkan; data yang berhasil tidak dihapus.`);
      await reload().catch(()=>{});await inspect().catch(()=>{});
    }finally{setBusy(false);}
  };
  const groups=(plan?.groups||[]).filter(group=>[group.name,group.date,...group.examples].some(value=>String(value||'').toLowerCase().includes(search.trim().toLowerCase())));
  const limit=size==='all'?Math.max(1,groups.length):Number(size);
  const pages=Math.max(1,Math.ceil(groups.length/limit));
  const current=Math.min(page,pages);
  const visible=groups.slice((current-1)*limit,current*limit);
  return <section aria-label={sectionLabel} className="border border-amber-200 rounded-xl p-4 space-y-4">
    <h3 className="font-bold">{heading} ({pending.length})</h3>
    <p className="text-xs text-slate-600">Hubungkan otomatis hanya untuk nama kegiatan yang cocok unik, dengan mengabaikan perbedaan huruf, spasi, dan tanda baca. Tanggal yang bertentangan atau nama yang ambigu tidak ditebak. Seluruh {noun} tertunda diproses, bukan hanya yang tampil di halaman ini.</p>
    <div className="flex flex-wrap items-center gap-3"><button disabled={busy||disabled} onClick={check} className="border rounded-lg p-2 text-xs">Periksa Kecocokan</button><button disabled={busy||disabled||!plan?.summary.matched} onClick={()=>connect()} className="bg-emerald-700 text-white rounded-lg p-2 text-xs">Hubungkan Otomatis ({plan?.summary.matched||0})</button>{plan&&<span className="text-xs">{plan.summary.matched} cocok unik · {plan.summary.ambiguous} ambigu · {plan.summary.date_conflict} tanggal berbeda · {plan.summary.unmatched+plan.summary.blank} belum ditemukan/belum diisi{plan.summary.invalid?` · ${plan.summary.invalid} data perlu diperiksa`:''}</span>}</div>
    {message&&<p role="status" className="bg-blue-50 text-blue-900 p-3 text-sm rounded-lg">{message}</p>}
    {error&&<p role="alert" className="bg-red-50 text-red-800 p-3 text-sm rounded-lg">{error}</p>}
    <div className="flex flex-wrap gap-3 items-center"><input aria-label={'Cari kelompok '+noun+' tertunda'} placeholder="Cari nama kegiatan atau identitas" value={search} onChange={event=>{setSearch(event.target.value);setPage(1);}} className="border rounded-lg p-2 text-xs flex-1 min-w-48"/><label className="text-xs">Tampilkan kelompok<select aria-label={'Jumlah kelompok '+noun+' per halaman'} value={size} onChange={event=>{setSize(event.target.value);setPage(1);}} className="border rounded-lg p-2 ml-2"><option value="10">10</option><option value="50">50</option><option value="all">Semua (All)</option></select></label></div>
    <p className="text-xs text-slate-500">Untuk nama yang belum cocok, pilih tujuan sekali lalu hubungkan seluruh kelompok dengan nama dan tanggal sumber yang sama. Pilihan ini adalah pencocokan manual; periksa judul, tanggal, dan program tujuan.</p>
    {visible.map(group=><div key={group.key} className="border-t pt-3 space-y-2 text-xs"><div><b>{group.name||'Nama kegiatan belum diisi'}</b> · {group.date||'Tanggal belum diisi'} · <b>{group.count} {noun}</b> · {statusLabels[group.status]}</div>{group.examples.length>0&&<p className="text-slate-500">Contoh {kind==='surveys'?'responden':'peserta'}: {group.examples.join(', ')}</p>}{group.status==='matched'&&<p className="text-emerald-800">Tujuan otomatis: {group.targetName} (ID {group.targetId})</p>}<div className="flex flex-wrap gap-2"><select aria-label={'Kegiatan untuk kelompok '+noun+' '+group.key} disabled={busy||disabled} value={targets[group.key]||''} onChange={event=>setTargets({...targets,[group.key]:event.target.value})} className="border rounded-lg p-2 flex-1 min-w-48"><option value="">Pilih kegiatan tujuan untuk kelompok ini</option>{activities.map(activity=><option key={activity.id} value={activity.id}>{activity.namaKegiatan||'Nama belum diisi'} · {activity.tanggal||activity.tahun||'Tanggal belum diisi'} · {activity.program} · ID {activity.id}</option>)}</select><button disabled={busy||disabled||!targets[group.key]} onClick={()=>connect(group)} className="border rounded-lg p-2">Hubungkan {group.count} {capital} Sekaligus</button></div></div>)}
    {plan&&!visible.length&&<p className="text-xs text-slate-500">Tidak ada kelompok yang sesuai pencarian.</p>}
    <nav aria-label={'Halaman kelompok '+noun} className="flex gap-3 items-center text-xs"><button disabled={busy||current===1} onClick={()=>setPage(current-1)} className="border rounded-lg p-2">Sebelumnya</button><span>Halaman {current} dari {pages} · {groups.length} kelompok</span><button disabled={busy||current===pages} onClick={()=>setPage(current+1)} className="border rounded-lg p-2">Berikutnya</button></nav>
  </section>;
}
