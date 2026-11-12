import test from 'node:test';
import assert from 'node:assert/strict';
import * as XLSX from 'xlsx';
import {readCaseFile,caseFields} from '../frontend/ppktCases.mjs';
function file(rows){const b=XLSX.utils.book_new();XLSX.utils.book_append_sheet(b,XLSX.utils.json_to_sheet(rows),'Data');const bytes=XLSX.write(b,{type:'buffer',bookType:'xlsx'});return {size:bytes.length,arrayBuffer:async()=>bytes};}
test('reads the 19 case columns, DD/MM/YYYY, checkbox booleans and counseling without inventing blanks',async()=>{
 const rows=await readCaseFile(file([{'Tahun':2024,'Tanggal Laporan Masuk':'05/11/2024','Nomor Kasus':'TEST-1','Kategori':'Psikis','Status Pelaporan (Pembuatan BAP)':true,'Status Pembuatan Surat Tugas':false,'Konseling Pelapor':'YA','Konseling Terlapor':'TIDAK','Keterangan':'Catatan uji'}, {'Tahun':2025,'Nomor Kasus':'TEST-2'}]));
 assert.equal(caseFields.length,19);assert.equal(rows[0].reportDate,'2024-11-05');assert.equal(rows[0].bap,true);assert.equal(rows[0].assignmentLetter,false);assert.equal(rows[0].reporterCounseling,true);assert.equal(rows[0].reportedCounseling,false);
 assert.equal(rows[1].reportDate,null);assert.equal(rows[1].bap,null);assert.equal(rows[1].category,'');
});
test('missing case numbers and conflicting report years are rejected without partial import',async()=>{
 await assert.rejects(readCaseFile(file([{'Tahun':2024,'Nomor Kasus':''}])),/Nomor Kasus wajib/);
 await assert.rejects(readCaseFile(file([{'Tahun':2024,'Nomor Kasus':'TEST','Tanggal Laporan Masuk':'01/01/2025'}])),/Tahun berbeda/);
});

test('CSV preserves DD/MM/YYYY instead of guessing US month/day before monthly aggregation',async()=>{
 const bytes=Buffer.from('Tahun,Tanggal Laporan Masuk,Nomor Kasus\n2024,05/11/2024,CSV-NOV\n2024,11/05/2024,CSV-MAY\n');
 const rows=await readCaseFile({size:bytes.length,arrayBuffer:async()=>bytes});
 assert.equal(rows[0].reportDate,'2024-11-05');assert.equal(rows[1].reportDate,'2024-05-11');
});
