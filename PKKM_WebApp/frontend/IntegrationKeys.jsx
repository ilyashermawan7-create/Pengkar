import React,{useState,useEffect} from 'react';
export default function IntegrationKeys({api}){
 const [items,setItems]=useState([]),[name,setName]=useState(''),[days,setDays]=useState('30'),[token,setToken]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const load=async()=>setItems((await api('/integration/keys')).items);
 useEffect(()=>{load().catch(error=>setError(error.message));},[]);
 const run=async(action)=>{setBusy(true);setError('');try{await action();}catch(error){setError(error.message);}finally{setBusy(false);}};
 return <section aria-label="Akses API Integrasi" className="bg-white border rounded-2xl p-6 space-y-4 text-sm">
 <h2 className="font-bold text-lg">Akses API Integrasi</h2>
 <p>Kunci ini dapat membaca seluruh kegiatan, mahasiswa, survei, dan kasus PPKPT termasuk rincian sensitif. Berikan hanya kepada server penerima yang berwenang. Tidak dapat mengubah atau menghapus data.</p>
 <form className="flex flex-wrap gap-3 items-end" onSubmit={event=>{event.preventDefault();run(async()=>{const result=await api('/integration/keys',{method:'POST',body:JSON.stringify({name,days:Number(days)})});setToken(result.token);setName('');await load();});}}>
 <label>Nama penerima / sistem<input required minLength={3} maxLength={100} value={name} onChange={event=>setName(event.target.value)} className="block border rounded-lg p-2"/></label>
 <label>Berlaku (hari)<input required type="number" min="1" max="90" value={days} onChange={event=>setDays(event.target.value)} className="block border rounded-lg p-2 w-28"/></label>
 <button disabled={busy} className="bg-red-700 text-white rounded-lg p-2">Buat API Key</button></form>
 {token&&<div className="bg-amber-50 border rounded-xl p-4 space-y-2"><p>Simpan sekarang. Kunci hanya ditampilkan sekali dan hilang saat halaman ditutup. Jangan kirim ke GitHub atau simpan di frontend.</p><input aria-label="API key baru" readOnly value={token} className="w-full border rounded-lg p-2 font-mono" onFocus={event=>event.target.select()}/><button type="button" onClick={()=>setToken('')} className="border rounded-lg p-2">Tutup Kunci</button></div>}
 <p>Endpoint: <code>GET /api/integration/data</code>, header <code>Authorization: Bearer API_KEY</code>. Simpan kunci di environment server penerima.</p>
 {error&&<p role="alert" className="text-red-700">{error}</p>}
 <ul className="space-y-2">{items.map(item=><li key={item.id} className="border rounded-lg p-3 flex flex-wrap justify-between gap-3"><span>{item.name} · Berakhir {new Date(item.expires_at).toLocaleString('id-ID')} · {item.revoked?'Dicabut':new Date(item.expires_at)<new Date()?'Kedaluwarsa':'Aktif'}</span>{!item.revoked&&<button type="button" disabled={busy} onClick={()=>{if(confirm('Cabut akses API '+item.name+'?'))run(async()=>{await api('/integration/keys/'+item.id,{method:'DELETE'});await load();});}} className="text-red-700">Cabut Akses</button>}</li>)}</ul>
 </section>;
}
