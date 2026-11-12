import * as XLSX from 'xlsx';
import {parseDate} from './migration.mjs';
export const caseFields=[
 ['year','Tahun','number'],['reportDate','Tanggal Laporan Masuk','date'],['caseNumber','Nomor Kasus'],
 ['reporterInstitution','Instansi Pelapor'],['reporterStudyProgram','Program Studi Pelapor'],['reporterFaculty','Fakultas Pelapor'],
 ['category','Kategori'],['bap','Status Pelaporan (Pembuatan BAP)','bool'],['assignmentLetter','Status Pembuatan Surat Tugas','bool'],
 ['facultyAction','Status Fakultas (Menghubungi Mahasiswa Bersangkutan)','bool'],['directorateAction','Status Direktorat (Memberikan Sanksi berdasarkan SK/Keputusan yang Berlaku)','bool'],
 ['reporterCounseling','Konseling Pelapor','bool'],['status','Status Kasus'],['positionNotes','Keterangan Posisi'],
 ['reportedInstitution','Asal Universitas Terlapor'],['reportedStudyProgram','Program Studi Terlapor'],['reportedFaculty','Fakultas Terlapor'],['reportedCounseling','Konseling Terlapor','bool'],['notes','Keterangan']];
export const emptyCase=()=>Object.fromEntries(caseFields.map(([key,,type])=>[key,type==='bool'||type==='number'||type==='date'?null:'']));
const normalize=value=>String(value??'').normalize('NFKC').toLowerCase().replace(/[^a-z0-9]/g,'');
function bool(value,row,label){
 if(value===true||value===false)return value;
 if(value===''||value===undefined||value===null)return null;
 const key=String(value).trim().toLowerCase();if(!key)return null;
 if(['true','ya','yes','1','sudah'].includes(key))return true;
 if(['false','tidak','no','0','belum'].includes(key))return false;
 throw Error(`Baris ${row}: ${label} harus TRUE/FALSE, YA/TIDAK, atau kosong.`);
}
export async function readCaseFile(file){
 if(file.size>10*1024*1024)throw Error('Ukuran berkas maksimal 10 MB.');
 const b=XLSX.read(await file.arrayBuffer(),{type:'array',raw:true,cellDates:false,sheetRows:10032});
 for(const name of b.SheetNames){
  const rows=XLSX.utils.sheet_to_json(b.Sheets[name],{header:1,defval:'',blankrows:false});
  const start=rows.findIndex((row,index)=>index<30&&row.map(normalize).includes('nomorkasus'));
  if(start<0)continue;
  const heads=rows[start].map(normalize),items=[];
  for(let index=start+1;index<rows.length;index++){
   const row=rows[index];if(row.every(value=>value===''||value===null))continue;
   const item=emptyCase();
   for(const [key,label,type] of caseFields){
    const column=heads.indexOf(normalize(label)),value=column<0?'':row[column]??'';
    if(type==='bool')item[key]=bool(value,index+1,label);
    else if(type==='number'){
     item[key]=value===''?null:Number(value);
     if(item[key]!==null&&(!Number.isInteger(item[key])||item[key]<1900||item[key]>2200))throw Error(`Baris ${index+1}: Tahun tidak valid.`);
    }else if(type==='date'){
     const parsed=typeof value==='number'?XLSX.SSF.parse_date_code(value):null;
     item[key]=parseDate(parsed?`${parsed.y}-${String(parsed.m).padStart(2,'0')}-${String(parsed.d).padStart(2,'0')}`:value,index+1,label);
    }else item[key]=String(value).trim();
   }
   if(!item.caseNumber)throw Error(`Baris ${index+1}: Nomor Kasus wajib diisi agar tidak tercatat ganda.`);
   if(item.reportDate&&item.year&&Number(item.reportDate.slice(0,4))!==item.year)throw Error(`Baris ${index+1}: Tahun berbeda dari tanggal laporan masuk.`);
   if(item.reportDate&&!item.year)item.year=Number(item.reportDate.slice(0,4));
   items.push(item);
  }
  if(!items.length||items.length>10000)throw Error('Berkas harus berisi 1–10.000 kasus.');
  return items;
 }
 throw Error('Kolom Nomor Kasus tidak ditemukan. Gunakan struktur Kasus PPKPT.xlsx.');
}
export function exportCases(items,template=false){
 const safe=value=>typeof value==='string'&&/^[=+@-]/.test(value)?"'"+value:value;
 const rows=items.map(item=>Object.fromEntries(caseFields.map(([key,label,type])=>[label,safe(type==='bool'?(item[key]===null?'':item[key]?'YA':'TIDAK'):item[key]??'')])));
 const b=XLSX.utils.book_new();XLSX.utils.book_append_sheet(b,XLSX.utils.json_to_sheet(rows,{header:caseFields.map(([,label])=>label)}),'Data');XLSX.writeFile(b,template?'Template_Kasus_PPKPT.xlsx':'Laporan_Kasus_PPKPT.xlsx');
}
