import React,{useState} from 'react';
import {asramaCategories} from './asramaCategories.mjs';
export default function AsramaCategoryReview({api,reload}){
 const [plan,setPlan]=useState(null),[choices,setChoices]=useState({}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[search,setSearch]=useState(''),[size,setSize]=useState('10'),[page,setPage]=useState(1);
 const inspect=async()=>{
   const result=await api('/dashboard/asrama/categories');setPlan(result);
   setChoices(Object.fromEntries(result.items.filter(item=>!item.complete).map(item=>[item.id,item.suggestion||''])));setPage(1);
 };
 const check=async()=>{setBusy(true);setError('');setMessage('');try{await inspect();}catch(err){setError(err.message);}finally{setBusy(false);}};
 const pending=plan?.items.filter(item=>!item.complete)||[];
 const selected=pending.filter(item=>choices[item.id]);
 const rows=pending.filter(item=>item.name.toLowerCase().includes(search.toLowerCase().trim()));
 const limit=size==='all'?Math.max(1,rows.length):Number(size),pages=Math.max(1,Math.ceil(rows.length/limit)),current=Math.min(page,pages);
 const apply=async()=>{
   setBusy(true);setError('');setMessage('');
   try{
     const result=await api('/dashboard/asrama/categories',{method:'POST',body:JSON.stringify({items:selected.map(item=>({activityId:item.id,expectedCategory:item.current,category:choices[item.id]}))})});
     await reload();await inspect();setMessage(`${result.updated} kegiatan berhasil dikategorikan. Peserta dan survei tetap tersimpan. Kegiatan yang belum dipilih tetap menunggu pemeriksaan.`);
   }catch(err){setError(err.message);}finally{setBusy(false);}
 };
 return <section aria-label="Kategorisasi data lama Asrama" className="border border-blue-200 rounded-xl p-4 space-y-3 text-xs">
  <h3 className="font-bold text-sm">Kategorisasi Data Lama Asrama</h3>
  <p>Periksa saran berdasarkan nama dan uraian kegiatan. Pilih Adaptif, Spiritual, Akademik, atau Sosial. Judul yang belum jelas tidak diberi kategori otomatis. Kategori yang sudah benar tetap dipertahankan.</p>
  <button type="button" onClick={check} disabled={busy} className="border rounded-lg p-2">Periksa Kategori Data Lama</button>
  {error&&<p role="alert" className="text-red-700">{error}</p>}{message&&<p role="status" className="text-emerald-800">{message}</p>}
  {plan&&<><p>{plan.complete} dari {plan.total} kegiatan sudah berkategori benar · {pending.length} perlu diperiksa · {selected.length} kategori siap diterapkan.</p>
  {pending.length>0&&<><div className="flex flex-wrap gap-3"><input aria-label="Cari kegiatan untuk kategorisasi Asrama" placeholder="Cari nama kegiatan" value={search} onChange={event=>{setSearch(event.target.value);setPage(1);}} className="border rounded-lg p-2 flex-1"/><select aria-label="Jumlah kegiatan kategorisasi per halaman" value={size} onChange={event=>{setSize(event.target.value);setPage(1);}} className="border rounded-lg p-2"><option value="10">10</option><option value="50">50</option><option value="all">Semua</option></select></div>
  <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th className="p-2">Kegiatan / Tanggal</th><th className="p-2">Kategori Lama</th><th className="p-2">Kategori Tujuan</th><th className="p-2">Dasar Saran</th></tr></thead><tbody>{rows.slice((current-1)*limit,current*limit).map(item=><tr key={item.id} className="border-t"><td className="p-2">{item.name||'Nama belum diisi'}<br/>{item.date||'Tanggal belum diisi'} · ID {item.id}</td><td className="p-2">{item.current||'Belum diisi'}</td><td className="p-2"><select aria-label={'Kategori tujuan kegiatan '+item.id} disabled={busy} value={choices[item.id]||''} onChange={event=>setChoices({...choices,[item.id]:event.target.value})} className="border rounded-lg p-2"><option value="">Pilih kategori / lewati</option>{asramaCategories.map(category=><option key={category}>{category}</option>)}</select></td><td className="p-2">{item.reason}</td></tr>)}</tbody></table></div>
  <div className="flex gap-3 items-center"><button type="button" disabled={busy||current===1} onClick={()=>setPage(current-1)} className="border rounded-lg p-2">Sebelumnya</button><span>Halaman {current} dari {pages}</span><button type="button" disabled={busy||current===pages} onClick={()=>setPage(current+1)} className="border rounded-lg p-2">Berikutnya</button></div>
  <p>Seluruh {selected.length} pilihan akan diterapkan, termasuk yang berada di halaman lain. Perubahan hanya pada kategori; kategori sebelumnya dicatat dalam riwayat.</p><button type="button" disabled={busy||!selected.length} onClick={apply} className="bg-blue-700 text-white rounded-lg p-2">Terapkan {selected.length} Kategori Asrama</button></>}
  {!pending.length&&<p>Semua kegiatan Asrama sudah masuk salah satu dari empat asas.</p>}</>}
 </section>;
}
