import * as XLSX from 'xlsx';
import schema from '../survey_schema.json' with {type:'json'};
import {readSpreadsheet} from './spreadsheet.mjs';
import {average} from './statistics.mjs';

export const normalizeName=value=>String(value||'').normalize('NFKC').trim().toLocaleLowerCase('id').replace(/\s+/g,' ');
const today=()=>new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Jakarta'});
export function parseDate(value,row,label='Tanggal') {
  let result=String(value||'').trim();
  if(!result)return null;
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
  if(!value)return null;
  const likert={'sangat tidak setuju':1,'tidak setuju':2,'netral':3,'ragu-ragu':3,'ragu ragu':3,'setuju':4,'sangat setuju':5,
    'sangat tidak puas':1,'tidak puas':2,'cukup puas':3,'puas':4,'sangat puas':5};
  let score=likert[value];
  if(score===undefined&&value){
    const labeled=value.match(/^([1-5])\s*[-–:.(]\s*[^\d].*/);
    score=labeled?Number(labeled[1]):Number(value.replace(',','.'));
  }
  if(!Number.isFinite(score)||score<1||score>5)throw Error(`Baris ${row}: ${label} harus berupa skor 1–5 atau label skala yang sesuai; nilai kosong tetap kosong.`);
  return score;
}

export function summarizeAnswers(answers) {
  return Object.fromEntries([...schema.groups.map(group=>[group.field,average(group.items.map(index=>answers[index-1]))]),
    ['skorTotal',average(answers)],['instrument',schema.version]]);
}

export async function readSurveyResponses(file) {
  const {data,get,has,rowNumber}=await readSpreadsheet(file);
  const full=schema.questions.some((question,index)=>has(question,`q${String(index+1).padStart(2,'0')}`));
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
      response.skorTotal=average([response.skorMateri,response.skorNarasumber,response.skorFasilitas,response.skorDampakKarakter]);
      response.instrument='legacy-4';
    }
    const ident=get(row,'idkegiatan','activityid');
    if(ident&&(!/^\d+$/.test(ident)||Number(ident)<1))throw Error(`Baris ${sourceRow}: ID kegiatan tidak valid.`);
    const activityDate=get(row,'tanggalkegiatan','tanggalpelaksanaan');
    return {activityId:ident?Number(ident):null,namaKegiatan:get(row,'namakegiatan'),tanggalKegiatan:activityDate?parseDate(activityDate,sourceRow,'Tanggal kegiatan'):'',sourceRow,response};
  });
  const hash=await globalThis.crypto.subtle.digest('SHA-256',await file.arrayBuffer());
  const fingerprint=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
  for(const item of items){
    item.importKey=fingerprint+':'+item.sourceRow;
    if(!item.response.nim&&!item.response.submittedAt&&!item.response.sourceKey)item.response.sourceKey=item.importKey;
  }
  return {format:full?schema.version:'legacy-4',items};
}

export function matchSurveyActivities(items,activities,selectedActivityId='',allowPending=false) {
  return items.map(item=>{
    try {
    let candidates=activities;
    if(selectedActivityId&&item.activityId&&item.activityId!==Number(selectedActivityId))throw Error(`Baris ${item.sourceRow}: ID kegiatan di file tidak sesuai pilihan kegiatan tujuan.`);
    const id=item.activityId||Number(selectedActivityId);
    if(id)candidates=candidates.filter(a=>a.id===id);
    if(item.namaKegiatan)candidates=candidates.filter(a=>normalizeName(a.namaKegiatan)===normalizeName(item.namaKegiatan));
    if(item.tanggalKegiatan)candidates=candidates.filter(a=>a.tanggal===item.tanggalKegiatan);
    if(!id&&!item.namaKegiatan)throw Error(`Baris ${item.sourceRow}: isi Nama Kegiatan/ID Kegiatan di file atau pilih kegiatan tujuan.`);
    if(candidates.length!==1)throw Error(`Baris ${item.sourceRow}: kegiatan "${item.namaKegiatan||id}" ${candidates.length?'memiliki lebih dari satu kecocokan. Isi ID Kegiatan atau Tanggal Kegiatan.':'tidak ditemukan atau tidak sesuai pilihan. Impor kegiatan terlebih dahulu.'}`);
    return {...item,activityId:candidates[0].id,namaKegiatan:candidates[0].namaKegiatan};
    }catch(error){if(!allowPending)throw error;return {...item,activityId:null,unresolved:error.message};}
  });
}

export async function readActivities(file) {
  const {data,get,rowNumber}=await readSpreadsheet(file,'activities');
  const hash=await globalThis.crypto.subtle.digest('SHA-256',await file.arrayBuffer());
  const fingerprint=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
  const integer=(row,keys,fallback=null)=>{
    const raw=get(row,...keys);if(!raw)return fallback;
    const value=Number(/^\d{1,3}(\.\d{3})+$/.test(raw)?raw.replace(/\./g,''):raw);
    if(!Number.isSafeInteger(value)||value<0)throw Error(`Baris ${rowNumber(row)}: ${keys[0]} wajib angka bulat nonnegatif.`);
    return value;
  };
  return data.map(row=>{
    const namaKegiatan=get(row,'namakegiatan');
    const rawYear=get(row,'tahun','tahun kegiatan');
    if(rawYear&&!/^\d{4}$/.test(rawYear))throw Error(`Baris ${rowNumber(row)}: Tahun harus empat angka atau kosong.`);
    const date=parseDate(get(row,'tanggalkegiatan','tanggal','tanggalpelaksanaan'),rowNumber(row),'Tanggal kegiatan');
    if(date&&rawYear&&date.slice(0,4)!==rawYear)throw Error(`Baris ${rowNumber(row)}: Tahun tidak sama dengan tanggal kegiatan.`);
    const explicitProgram=get(row,'program');
    const programRaw=explicitProgram||get(row,'urusan');
    if(explicitProgram&&!/asrama|karakter|pengkar/i.test(explicitProgram))throw Error(`Baris ${rowNumber(row)}: Program wajib Pengembangan Karakter atau Asrama.`);
    const program=/asrama/i.test(programRaw)?'Asrama':'Pengembangan Karakter';
    const score=get(row,'targetsurveykepuasan','skorsurvey','indekskepuasan');
    return {namaKegiatan,tanggal:date,tahun:date?date.slice(0,4):rawYear,sourceKey:fingerprint+':'+rowNumber(row),program,
      kategori:get(row,'kategori'),jenis:get(row,'jenis','jeniskegiatan'),urusan:get(row,'urusan')||program,
      jumlahPeserta:integer(row,['jumlahpeserta','peserta']),tempat:get(row,'tempat','tempatpelaksanaan'),unitKerjasama:get(row,'unitkerjasama'),
      pembicara:get(row,'pembicara','narasumber'),honor:get(row,'honor','honorpembicara'),takPanitia:integer(row,['takpanitia']),takPeserta:integer(row,['takpeserta']),
      laporan:get(row,'laporan','ringkasanlaporan'),linkEvident:get(row,'linkevident','linkeviden','eviden'),
      targetSurveyKepuasan:score?parseScore(score,rowNumber(row),'Skor survei'):null};
  });
}

function download(rows,sheetName,filename) {
  const book=XLSX.utils.book_new();XLSX.utils.book_append_sheet(book,XLSX.utils.json_to_sheet(rows),sheetName);XLSX.writeFile(book,filename);
}
export function downloadActivityTemplate() {
  download([{'Nama Kegiatan':'Kegiatan Contoh','Tanggal Kegiatan':today(),'Tahun':today().slice(0,4),'Program':'Pengembangan Karakter','Kategori':'Pengembangan Karakter','Jenis Kegiatan':'Seminar','Urusan':'Pengembangan karakter','Jumlah Peserta':0,'Tempat':'','Unit Kerjasama':'','Pembicara':'','Honor':'','TAK Panitia':10,'TAK Peserta':5,'Laporan':'','Link Evident':''}], 'Kegiatan','Template_Migrasi_Kegiatan.xlsx');
}
export function downloadSatisfactionTemplate(activityName='') {
  download([{'ID Kegiatan':'','Nama Kegiatan':activityName||'Isi sesuai daftar kegiatan','Tanggal Kegiatan':'','Tanggal Survey':today(),'NIM':'','Nama':'',
    ...Object.fromEntries(schema.questions.map(question=>[question,''])),[schema.suggestion]:''}], 'Survey Kepuasan','Template_Survey_Kepuasan_20_Pertanyaan.xlsx');
}

export async function readDirectory(file){
  const {data,get,rowNumber}=await readSpreadsheet(file,'directory');
  const hash=await globalThis.crypto.subtle.digest('SHA-256',await file.arrayBuffer());
  const fingerprint=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
  return data.map(row=>{
    const item=Object.fromEntries(['nim','nama','prodi','fakultas','kampus'].map(key=>[key,get(row,key)]));
    if(item.nim&&!/^\d{6,30}$/.test(item.nim))throw Error(`Baris ${rowNumber(row)}: NIM terisi harus 6–30 angka; kosong diperbolehkan.`);
    return {...item,directoryId:get(row,'idmaster','directoryid'),sourceKey:fingerprint+':'+rowNumber(row)};
  });
}
export function downloadDirectoryTemplate(){
  download([{'NIM':'','Nama Mahasiswa':'','Program Studi':'','Fakultas':'','Kampus':''}],'Master Mahasiswa','Template_Master_Mahasiswa.xlsx');
}

export async function readActivityParticipants(file){
  const {data,get,rowNumber}=await readSpreadsheet(file,'directory');
  const hash=await globalThis.crypto.subtle.digest('SHA-256',await file.arrayBuffer());
  const fingerprint=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
  return data.map(row=>{
    const student=Object.fromEntries(['nim','nama','prodi','fakultas','kampus'].map(key=>[key,get(row,key)]));
    if(student.nim&&!/^\d{6,30}$/.test(student.nim))throw Error(`Baris ${rowNumber(row)}: NIM terisi harus 6–30 angka; kosong diperbolehkan.`);
    const ident=get(row,'idkegiatan','activityid');
    if(ident&&(!/^\d+$/.test(ident)||Number(ident)<1))throw Error(`Baris ${rowNumber(row)}: ID kegiatan tidak valid.`);
    const date=get(row,'tanggalkegiatan','tanggalpelaksanaan');
    const importKey=fingerprint+':'+rowNumber(row);
    return {activityId:ident?Number(ident):null,namaKegiatan:get(row,'namakegiatan'),tanggalKegiatan:date?parseDate(date,rowNumber(row),'Tanggal kegiatan'):'',sourceRow:rowNumber(row),importKey,
      student:{...student,directoryId:get(row,'idmaster'),sourceKey:importKey}};
  });
}

export function downloadParticipantTemplate(){
  download([{'ID Kegiatan':'','Nama Kegiatan':'','Tanggal Kegiatan':'','NIM':'','Nama Mahasiswa':'','Program Studi':'','Fakultas':'','Kampus':''}],
    'Peserta Kegiatan','Template_Migrasi_Peserta_Kegiatan.xlsx');
}
