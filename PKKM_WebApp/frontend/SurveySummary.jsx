import React from 'react';
import * as XLSX from 'xlsx';
import schema from '../survey_schema.json' with {type:'json'};

export default function SurveySummary({surveys,activities}) {
  const full=surveys.filter(response=>response.answers?.length===20);
  const names=new Map(activities.map(a=>[a.id,a.namaKegiatan]));
  const averages=schema.questions.map((_,index)=>full.length?full.reduce((sum,s)=>sum+s.answers[index],0)/full.length:null);
  const exportResponses=()=>{
    const safe=value=>typeof value==='string'&&/^[=+@-]/.test(value)?"'"+value:value;
    const rows=full.map(response=>Object.fromEntries(Object.entries({
      'ID Kegiatan':response.activityId,'Nama Kegiatan':names.get(response.activityId),'Tanggal Survey':response.tanggalSurvey,
      'Timestamp':response.submittedAt||'','ID Sumber':response.sourceKey||'','NIM':response.nim,'Nama':response.nama,'Fakultas':response.fakultas,'Kampus':response.kampus,
      ...Object.fromEntries(schema.questions.map((question,index)=>[question,response.answers[index]])),[schema.suggestion]:response.saran,
    }).map(([key,value])=>[key,safe(value)])));
    const workbook=XLSX.utils.book_new();XLSX.utils.book_append_sheet(workbook,XLSX.utils.json_to_sheet(rows),'Survei Kepuasan');XLSX.writeFile(workbook,'Hasil_Survei_Kepuasan_PKKM.xlsx');
  };
  return <section aria-label="Survei kepuasan 20 pertanyaan" className="bg-white p-6 border rounded-2xl space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-bold text-lg">Survei Kepuasan Kegiatan — Pertanyaan Asli</h2><button disabled={!full.length} onClick={exportResponses} className="text-xs border p-2 rounded-lg">Ekspor Jawaban Survei Kepuasan</button></div>
    <p className="text-xs text-slate-600">{full.length} respons instrumen 20 pertanyaan sesuai filter. Skala 1–5; indeks kepuasan = rerata seluruh jawaban pada 20 pertanyaan. Skor persentase = rerata ÷ 5 × 100%. Format lama 4 skor tetap disimpan terpisah dan tidak dianggap menjawab pertanyaan berikut.</p>
    <div className="overflow-x-auto"><table className="w-full text-xs text-left"><thead className="bg-slate-800 text-white"><tr><th className="p-3">No.</th><th className="p-3">Pertanyaan (tidak diubah)</th><th className="p-3">Respons</th><th className="p-3">Rerata / 5</th><th className="p-3">Persentase</th></tr></thead><tbody>{schema.questions.map((question,index)=><tr key={question} className="border-b"><td className="p-3">{index+1}</td><td className="p-3">{question}</td><td className="p-3">{full.length}</td><td className="p-3">{averages[index]===null?'—':averages[index].toFixed(2)}</td><td className="p-3">{averages[index]===null?'—':(averages[index]*20).toFixed(1)+'%'}</td></tr>)}</tbody></table></div>
    <details><summary className="font-semibold text-sm cursor-pointer">{schema.suggestion}</summary><ul className="text-xs space-y-2 mt-3">{full.filter(s=>s.saran).map(s=><li key={s.id} className="border p-3 rounded-lg"><b>{names.get(s.activityId)}</b> · {s.tanggalSurvey}: {s.saran}</li>)}{!full.some(s=>s.saran)&&<li>Belum ada saran tersimpan.</li>}</ul></details>
  </section>;
}
