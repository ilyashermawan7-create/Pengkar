import React from 'react';
import {createPortal} from 'react-dom';
import surveySchema from '../survey_schema.json';
import {average} from './statistics.mjs';
import {calculateCsi,csiMethod} from './csi.mjs';

function Table({columns,rows,empty}) {
  return <table><thead><tr>{columns.map(column=><th key={column}>{column}</th>)}</tr></thead><tbody>
    {rows.length?rows.map((row,i)=><tr key={i}>{row.map((value,j)=><td key={j}>{value??'—'}</td>)}</tr>):<tr><td colSpan={columns.length}>{empty}</td></tr>}
  </tbody></table>;
}

export default function PrintReport({activities,students,surveys,filters,preparedBy}) {
  const csi=calculateCsi(surveys);
  const names=new Map(activities.map(a=>[a.id,a.namaKegiatan]));
  const grouped=new Map();
  for(const student of students){
    const identity=student.nim||student.directoryId;
    if(!grouped.has(identity))grouped.set(identity,{...student,kegiatan:new Map()});
    grouped.get(identity).kegiatan.set(student.activityId,names.get(student.activityId)||'Kegiatan');
  }
  const people=[...grouped.values()].sort((a,b)=>a.nama.localeCompare(b.nama,'id'));
  const generatedAt=new Intl.DateTimeFormat('id-ID',{dateStyle:'long',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date());
  return createPortal(<article id="pkkm-print-report" aria-label="Dokumen laporan PDF">
    <div className="report-heading"><h1>Laporan Kegiatan dan Rekap Mahasiswa PKKM</h1><p>Telkom University · Pengembangan Karakter dan Asrama</p></div>
    <p>Filter: {filters.year} · {filters.quarter} · {filters.category}{filters.search?` · Pencarian: ${filters.search}`:''}</p>
    <p>Dicetak: {generatedAt} WIB · Oleh: {preparedBy}</p>
    <p className="report-summary">Ringkasan: {activities.length} kegiatan · {activities.reduce((sum,a)=>sum+a.jumlahPeserta,0)} kehadiran · {people.filter(student=>student.nim).length} mahasiswa unik teridentifikasi · {surveys.length} respons survei.</p>
    <h2>CSI Bobot Setara{csi.provisional?' (sementara)':''}</h2><p>{csi.percent===null?'—':csi.percent.toFixed(2)+'%'} · {csi.status} · {csi.coverage}/20 pertanyaan terwakili.</p><p>{csiMethod}</p>
    <h2>Data Kegiatan</h2>
    <Table columns={['No.','Tanggal / TW','Nama Kegiatan','Program / Kategori','Peserta','Skor Survei','Narasumber','Eviden / Laporan']} empty="Tidak ada kegiatan sesuai filter yang dipilih." rows={activities.map((a,index)=>[
      index+1,`${a.tanggal||'—'} / ${a.triwulan||'—'} (Tahun ${a.tahun||'—'})`,a.namaKegiatan,`${a.program} / ${a.kategori}`,a.jumlahPeserta,
      a.skorSurvey===null||a.skorSurvey===undefined?'Belum ada nilai':Number(a.skorSurvey).toFixed(2),a.pembicara||'—',
      [a.linkEvident,a.laporan].filter(Boolean).join('\n')||'—',
    ])}/>
    <h2>Rekap Data Mahasiswa</h2>
    <p>Mahasiswa dikelompokkan berdasarkan NIM. Seluruh hasil sesuai filter dicetak, termasuk baris di luar pratinjau layar.</p>
    <Table columns={['No.','NIM','Nama Mahasiswa','Program Studi','Fakultas','Kampus','Kegiatan']} empty="Belum ada daftar mahasiswa tersimpan untuk kegiatan pada filter ini." rows={people.map((student,index)=>[
      index+1,student.nim,student.nama,student.prodi||'—',student.fakultas||'—',student.kampus||'—',[...student.kegiatan.values()].join('; '),
    ])}/>
    {surveys.length>0&&<><h2>Rekap Respons Survei</h2><Table columns={['Tanggal','Kegiatan','NIM','Pemahaman','Narasumber','Pelaksanaan','Pengembangan diri','Saran']} rows={surveys.map(s=>[
      s.tanggalSurvey,names.get(s.activityId),s.nim||'—',s.skorMateri,s.skorNarasumber,s.skorFasilitas,s.skorDampakKarakter,s.saran||'—',
    ])}/></>}
    {surveys.some(response=>response.answers?.length===20)&&<><h2>Survei Kepuasan — Pertanyaan Asli</h2><Table columns={['No.','Pertanyaan','Respons','Rerata / 5']} rows={surveySchema.questions.map((question,index)=>{
      const responses=surveys.filter(response=>response.answers?.length===20);
      const values=responses.map(response=>response.answers[index]).filter(value=>value!==null);
      return [index+1,question,values.length,average(values)?.toFixed(2)??'—'];
    })}/></>}
  </article>,document.body);
}
