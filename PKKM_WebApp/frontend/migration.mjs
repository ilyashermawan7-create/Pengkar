import * as XLSX from 'xlsx';
import schema from '../survey_schema.json' with {type:'json'};
import {readSpreadsheet} from './spreadsheet.mjs';

export const normalizeName=value=>String(value||'').normalize('NFKC').trim().toLocaleLowerCase('id').replace(/\s+/g,' ');
const today=()=>new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Jakarta'});
export function parseDate(value,row,label='Tanggal') {
  let result=String(value||'').trim();
  if(/^\d{4}-\d{2}-\d{2}(?:[T\s]|$)/.test(result))result=result.slice(0,10);
  else {
    const matched=result.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})(?:\s|$)/);
    if(matched)result=`${matched[3]}-${matched[2].padStart(2,'0')}-${matched[1].padStart(2,'0')}`;
  }
  const date=new Date(result+'T00:00:00Z');
  if(!/^\d{4}-\d{2}-\d{2}$/.test(result)||!Number.isFinite(date.valueOf())||date.toISOString().slice(0,10)!==result)
    throw Error(`Baris ${row}: ${label} wajib berupa YYYY-MM-DD atau DD/MM/YYYY.`);
  return result;
}

export function parseScore(raw,row,label) {
  const value=String(raw??'').replace(/[\u200b-\u200f\u2060\ufeff]/g,'').trim().toLowerCase();
  const likert={'sangat tidak setuju':1,'tidak setuju':2,'netral':3,'ragu-ragu':3,'ragu ragu':3,'setuju':4,'sangat setuju':5,
    'sangat tidak puas':1,'tidak puas':2,'cukup puas':3,'puas':4,'sangat puas':5};
  let score=likert[value];
  if(score===undefined&&value){
    const labeled=value.match(/^([1-5])\s*[-–:.(]\s*[^\d].*/);
    score=labeled?Number(labeled[1]):Number(value.replace(',','.'));
  }
  if(!value||!Number.isFinite(score)||score<1||score>5)throw Error(`Baris ${row}: ${label} wajib diisi skor 1–5 atau label skala yang sesuai. Tidak ada nilai otomatis untuk jawaban kosong.`);
  return score;
}

export function summarizeAnswers(answers) {
  return Object.fromEntries([...schema.groups.map(group=>[group.field,group.items.reduce((sum,index)=>sum+answers[index-1],0)/group.items.length]),
    ['skorTotal',answers.reduce((sum,value)=>sum+value,0)/20],['instrument',schema.version]]);
}

export async function readSurveyResponses(file) {
  const {data,get,has,rowNumber}=await readSpreadsheet(file);
  const full=schema.questions.some((question,index)=>has(question,`q${String(index+1).padStart(2,'0')}`));
  if(full){
    schema.questions.forEach((question,index)=>{
      if(!has(question,`q${String(index+1).padStart(2,'0')}`))throw Error(`Kolom pertanyaan ${index+1} tidak ditemukan: ${question}`);
    });
  }
  const items=data.map(row=>{
    const sourceRow=rowNumber(row);
      const submittedAt=get(row,'timestamp','stempelwaktu','waktupengisian');
    const response={tanggalSurvey:parseDate(get(row,'tanggalsurvey','tanggal','timestamp','stempelwaktu','waktupengisian'),sourceRow,'Tanggal survei'),
      submittedAt,sourceKey:get(row,'idsumber','sourcekey'),nim:get(row,'nim'),nama:get(row,'nama'),fakultas:get(row,'fakultas'),kampus:get(row,'kampus'),saran:get(row,schema.suggestion,'saran','kritiksaran')};
    if(full){
      response.answers=schema.questions.map((question,index)=>parseScore(get(row,question,`q${String(index+1).padStart(2,'0')}`),sourceRow,`Pertanyaan ${index+1}`));
      Object.assign(response,summarizeAnswers(response.answers));
    }else{
      for(const [key,alias] of [['skorMateri','skormateri'],['skorNarasumber','skornarasumber'],['skorFasilitas','skorfasilitas'],['skorDampakKarakter','skordampak']])
        response[key]=parseScore(get(row,key,alias),sourceRow,key);
      response.skorTotal=(response.skorMateri+response.skorNarasumber+response.skorFasilitas+response.skorDampakKarakter)/4;
      response.instrument='legacy-4';
    }
    const ident=get(row,'idkegiatan','activityid');
    if(ident&&(!/^\d+$/.test(ident)||Number(ident)<1))throw Error(`Baris ${sourceRow}: ID kegiatan tidak valid.`);
    const activityDate=get(row,'tanggalkegiatan','tanggalpelaksanaan');
    return {activityId:ident?Number(ident):null,namaKegiatan:get(row,'namakegiatan'),tanggalKegiatan:activityDate?parseDate(activityDate,sourceRow,'Tanggal kegiatan'):'',sourceRow,response};
  });
  const anonymous=items.filter(item=>!item.response.nim&&!item.response.submittedAt&&!item.response.sourceKey);
  if(anonymous.length){
    const hash=await globalThis.crypto.subtle.digest('SHA-256',await file.arrayBuffer());
    const fingerprint=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
    for(const item of anonymous)item.response.sourceKey=fingerprint+':'+item.sourceRow;
  }
  return {format:full?schema.version:'legacy-4',items};
}

export function matchSurveyActivities(items,activities,selectedActivityId='') {
  return items.map(item=>{
    let candidates=activities;
    if(selectedActivityId&&item.activityId&&item.activityId!==Number(selectedActivityId))throw Error(`Baris ${item.sourceRow}: ID kegiatan di file tidak sesuai pilihan kegiatan tujuan.`);
    const id=item.activityId||Number(selectedActivityId);
    if(id)candidates=candidates.filter(a=>a.id===id);
    if(item.namaKegiatan)candidates=candidates.filter(a=>normalizeName(a.namaKegiatan)===normalizeName(item.namaKegiatan));
    if(item.tanggalKegiatan)candidates=candidates.filter(a=>a.tanggal===item.tanggalKegiatan);
    if(!id&&!item.namaKegiatan)throw Error(`Baris ${item.sourceRow}: isi Nama Kegiatan/ID Kegiatan di file atau pilih kegiatan tujuan.`);
    if(candidates.length!==1)throw Error(`Baris ${item.sourceRow}: kegiatan "${item.namaKegiatan||id}" ${candidates.length?'memiliki lebih dari satu kecocokan. Isi ID Kegiatan atau Tanggal Kegiatan.':'tidak ditemukan atau tidak sesuai pilihan. Impor kegiatan terlebih dahulu.'}`);
    return {...item,activityId:candidates[0].id,namaKegiatan:candidates[0].namaKegiatan};
  });
}

export async function readActivities(file) {
  const {data,get,rowNumber}=await readSpreadsheet(file,'activities');
  const integer=(row,keys,fallback=0)=>{
    const raw=get(row,...keys);if(!raw)return fallback;
    const value=Number(/^\d{1,3}(\.\d{3})+$/.test(raw)?raw.replace(/\./g,''):raw);
    if(!Number.isSafeInteger(value)||value<0)throw Error(`Baris ${rowNumber(row)}: ${keys[0]} wajib angka bulat nonnegatif.`);
    return value;
  };
  return data.map(row=>{
    const namaKegiatan=get(row,'namakegiatan');
    if(namaKegiatan.length<3)throw Error(`Baris ${rowNumber(row)}: Nama Kegiatan minimal 3 karakter.`);
    const explicitProgram=get(row,'program');
    const programRaw=explicitProgram||get(row,'urusan');
    if(explicitProgram&&!/asrama|karakter|pengkar/i.test(explicitProgram))throw Error(`Baris ${rowNumber(row)}: Program wajib Pengembangan Karakter atau Asrama.`);
    const program=/asrama/i.test(programRaw)?'Asrama':'Pengembangan Karakter';
    const score=get(row,'targetsurveykepuasan','skorsurvey','indekskepuasan');
    return {namaKegiatan,tanggal:parseDate(get(row,'tanggalkegiatan','tanggal','tanggalpelaksanaan'),rowNumber(row),'Tanggal kegiatan'),program,
      kategori:get(row,'kategori')||'Pengembangan Karakter',jenis:get(row,'jenis','jeniskegiatan'),urusan:get(row,'urusan')||program,
      jumlahPeserta:integer(row,['jumlahpeserta','peserta']),tempat:get(row,'tempat','tempatpelaksanaan'),unitKerjasama:get(row,'unitkerjasama'),
      pembicara:get(row,'pembicara','narasumber'),honor:get(row,'honor','honorpembicara'),takPanitia:integer(row,['takpanitia'],10),takPeserta:integer(row,['takpeserta'],5),
      laporan:get(row,'laporan','ringkasanlaporan'),linkEvident:get(row,'linkevident','linkeviden','eviden'),
      targetSurveyKepuasan:score?parseScore(score,rowNumber(row),'Skor survei'):null};
  });
}

function download(rows,sheetName,filename) {
  const book=XLSX.utils.book_new();XLSX.utils.book_append_sheet(book,XLSX.utils.json_to_sheet(rows),sheetName);XLSX.writeFile(book,filename);
}
export function downloadActivityTemplate() {
  download([{'Nama Kegiatan':'Kegiatan Contoh','Tanggal Kegiatan':today(),'Program':'Pengembangan Karakter','Kategori':'Pengembangan Karakter','Jenis Kegiatan':'Seminar','Urusan':'Pengembangan karakter','Jumlah Peserta':0,'Tempat':'','Unit Kerjasama':'','Pembicara':'','Honor':'','TAK Panitia':10,'TAK Peserta':5,'Laporan':'','Link Evident':''}], 'Kegiatan','Template_Migrasi_Kegiatan.xlsx');
}
export function downloadSatisfactionTemplate(activityName='') {
  download([{'ID Kegiatan':'','Nama Kegiatan':activityName||'Isi sesuai daftar kegiatan','Tanggal Kegiatan':'','Tanggal Survey':today(),'NIM':'','Nama':'',
    ...Object.fromEntries(schema.questions.map(question=>[question,''])),[schema.suggestion]:''}], 'Survey Kepuasan','Template_Survey_Kepuasan_20_Pertanyaan.xlsx');
}
