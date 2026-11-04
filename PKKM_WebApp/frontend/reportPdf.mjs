import {jsPDF} from 'jspdf';
import {autoTable} from 'jspdf-autotable';
import surveySchema from '../survey_schema.json';
import {average} from './statistics.mjs';

let fontPromise;
async function reportFont() {
  if (!fontPromise) fontPromise=(async()=>{
    const response=await fetch('/static/fonts/report-sans.ttf');
    if(!response.ok)throw Error('Font laporan gagal dimuat. Muat ulang aplikasi dan coba lagi.');
    const bytes=new Uint8Array(await response.arrayBuffer());
    let binary='';
    for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
    return btoa(binary);
  })().catch(error=>{fontPromise=undefined;throw error;});
  return fontPromise;
}

export async function downloadReportPdf({activities,students,surveys,filters,preparedBy}) {
  const doc=new jsPDF({orientation:'landscape',unit:'mm',format:'a4'});
  doc.addFileToVFS('report-sans.ttf',await reportFont());
  doc.addFont('report-sans.ttf','ReportSans','normal');
  doc.addFont('report-sans.ttf','ReportSans','bold');
  doc.setFont('ReportSans','normal');
  doc.setProperties({title:'Laporan Kegiatan dan Rekap Mahasiswa PKKM',author:preparedBy});
  const names=new Map(activities.map(activity=>[activity.id,activity.namaKegiatan]));
  const grouped=new Map();
  for(const student of students){
    const identity=student.nim||student.directoryId;
    if(!grouped.has(identity))grouped.set(identity,{...student,kegiatan:new Map()});
    grouped.get(identity).kegiatan.set(student.activityId,names.get(student.activityId)||'Kegiatan');
  }
  const people=[...grouped.values()].sort((a,b)=>a.nama.localeCompare(b.nama,'id'));
  const timestamp=new Intl.DateTimeFormat('id-ID',{dateStyle:'long',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date());
  doc.setFontSize(16);
  doc.text('Laporan Kegiatan dan Rekap Mahasiswa PKKM',12,17);
  doc.setFontSize(9);
  doc.text('Telkom University · Pengembangan Karakter dan Asrama',12,23);
  doc.setDrawColor(153,27,27);doc.line(12,27,285,27);
  let y=33;
  for(const text of [
    `Filter: ${filters.year} · ${filters.quarter} · ${filters.category}${filters.search?` · Pencarian: ${filters.search}`:''}`,
    `Dibuat: ${timestamp} WIB · Oleh: ${preparedBy}`,
    `Ringkasan: ${activities.length} kegiatan · ${activities.reduce((sum,a)=>sum+a.jumlahPeserta,0)} kehadiran · ${people.filter(student=>student.nim).length} mahasiswa unik · ${surveys.length} respons survei.`,
  ]){
    const lines=doc.splitTextToSize(text,273);doc.text(lines,12,y);y+=lines.length*4+2;
  }
  const table=(title,head,body)=>{
    if(y>177){doc.addPage();y=17;}
    doc.setFontSize(12);doc.text(title,12,y);y+=4;
    autoTable(doc,{
      startY:y,head:[head],body:body.length?body:[[ {content:'Tidak ada data sesuai filter.',colSpan:head.length} ]],
      theme:'grid',margin:{left:12,right:12,top:14,bottom:15},
      styles:{font:'ReportSans',fontStyle:'normal',fontSize:8,cellPadding:2,overflow:'linebreak',lineColor:[180,185,195],lineWidth:.15},
      headStyles:{fontStyle:'bold',fillColor:[153,27,27],textColor:255},
      rowPageBreak:'avoid',showHead:'everyPage',
    });
    y=doc.lastAutoTable.finalY+12;
  };
  table('Data Kegiatan',['No.','Tanggal / TW','Nama Kegiatan','Program / Kategori','Peserta','Skor Survei','Narasumber','Eviden / Laporan'],activities.map((a,index)=>[
    index+1,`${a.tanggal||'—'} / ${a.triwulan||'—'} (Tahun ${a.tahun||'—'})`,a.namaKegiatan,`${a.program} / ${a.kategori}`,a.jumlahPeserta,
    a.skorSurvey==null?'Belum ada nilai':Number(a.skorSurvey).toFixed(2),a.pembicara||'—',[a.linkEvident,a.laporan].filter(Boolean).join('\n')||'—',
  ]));
  table('Rekap Data Mahasiswa',['No.','NIM','Nama Mahasiswa','Program Studi','Fakultas','Kampus','Kegiatan'],people.map((s,index)=>[
    index+1,s.nim,s.nama,s.prodi||'—',s.fakultas||'—',s.kampus||'—',[...s.kegiatan.values()].join('; '),
  ]));
  if(surveys.length)table('Rekap Respons Survei',['Tanggal','Kegiatan','NIM','Pemahaman','Narasumber','Pelaksanaan','Pengembangan diri','Saran'],surveys.map(s=>[
    s.tanggalSurvey,names.get(s.activityId),s.nim||'—',s.skorMateri,s.skorNarasumber,s.skorFasilitas,s.skorDampakKarakter,s.saran||'—',
  ]));
  const satisfaction=surveys.filter(response=>response.answers?.length===20);
  if(satisfaction.length)table('Survei Kepuasan — Pertanyaan Asli',['No.','Pertanyaan','Respons','Rerata / 5','Persentase'],surveySchema.questions.map((question,index)=>{
    const values=satisfaction.map(response=>response.answers[index]).filter(value=>value!==null);
    const mean=average(values);
    return [index+1,question,values.length,mean===null?'—':mean.toFixed(2),mean===null?'—':(mean*20).toFixed(1)+'%'];
  }));
  const pages=doc.getNumberOfPages();
  for(let page=1;page<=pages;page++){
    doc.setPage(page);doc.setFontSize(8);doc.setTextColor(90);
    doc.text(`PKKM · Halaman ${page} dari ${pages}`,285,202,{align:'right'});
  }
  doc.save('Laporan_PKKM.pdf');
}
