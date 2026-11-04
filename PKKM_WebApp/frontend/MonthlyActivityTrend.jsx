import React,{useEffect,useRef} from 'react';
import Chart from 'chart.js/auto';
import {monthlyActivityTrend,monthLabels} from './monthlyActivityTrend.mjs';

export default function MonthlyActivityTrend({activities}){
  const canvas=useRef(null);
  const trend=monthlyActivityTrend(activities);
  const signature=JSON.stringify(trend.series);
  useEffect(()=>{
    if(!canvas.current)return;
    const colors=['#D71920','#2563eb','#15803d','#9333ea','#b45309','#0891b2'];
    const chart=new Chart(canvas.current,{type:'line',data:{labels:monthLabels,datasets:trend.series.map((series,index)=>({label:series.year,data:series.counts,borderColor:colors[index%colors.length],backgroundColor:colors[index%colors.length],tension:.2,pointRadius:3,fill:false}))},options:{responsive:true,maintainAspectRatio:false,animation:false,scales:{y:{beginAtZero:true,ticks:{precision:0},title:{display:true,text:'Jumlah nama kegiatan unik'}},x:{grid:{display:false}}},plugins:{legend:{position:'top'},tooltip:{callbacks:{label:item=>`${item.dataset.label}: ${item.parsed.y} kegiatan unik`}}}}});
    return()=>chart.destroy();
  },[signature]);
  return <section aria-label="Tren kegiatan bulanan" className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
    <h2 className="text-sm font-bold text-slate-800">Tren Jumlah Kegiatan Setiap Bulan</h2>
    <p className="text-xs text-slate-500">Mengikuti grup dan filter dashboard. Nama kegiatan yang sama dalam satu bulan dan tahun dihitung 1 kali, termasuk lintas kategori. Perbedaan huruf besar/kecil dan spasi diabaikan. Nama yang muncul di bulan berbeda dihitung sekali pada masing-masing bulan.</p>
    {trend.series.length?<><div className="relative h-64 w-full"><canvas ref={canvas} role="img" aria-label="Grafik garis jumlah nama kegiatan unik setiap bulan per tahun"/></div><details><summary className="text-xs font-semibold cursor-pointer">Lihat Angka Kegiatan Bulanan</summary><div className="overflow-x-auto"><table aria-label="Jumlah kegiatan unik per bulan" className="w-full text-xs text-left"><thead><tr><th className="p-2">Bulan</th>{trend.series.map(series=><th className="p-2" key={series.year}>{series.year}</th>)}</tr></thead><tbody>{monthLabels.map((month,index)=><tr key={month} className="border-t"><td className="p-2">{month}</td>{trend.series.map(series=><td className="p-2" key={series.year}>{series.counts[index]}</td>)}</tr>)}</tbody></table></div></details></>:<p className="text-xs text-slate-500">Belum ada kegiatan bernama dan bertanggal lengkap sesuai filter untuk grafik bulanan.</p>}
    {(trend.missingDate>0||trend.missingName>0)&&<p className="text-xs text-amber-800">Tidak dimasukkan ke grafik: {trend.missingDate} kegiatan tanpa tanggal lengkap/valid dan {trend.missingName} kegiatan bertanggal tanpa nama. Data tetap tersimpan.</p>}
  </section>;
}
