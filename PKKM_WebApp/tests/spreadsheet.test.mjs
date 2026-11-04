import test from 'node:test';
import assert from 'node:assert/strict';
import * as XLSX from 'xlsx';
import {readParticipants} from '../frontend/spreadsheet.mjs';

function spreadsheet(rows, options={}) {
  const workbook=XLSX.utils.book_new();
  if(options.instructions)XLSX.utils.book_append_sheet(workbook,XLSX.utils.aoa_to_sheet([['Petunjuk pengisian'],['Isi data pada sheet Peserta']]),'Petunjuk');
  const sheet=XLSX.utils.aoa_to_sheet(rows);
  if(options.formatNim)sheet.A2.z='000000000000';
  XLSX.utils.book_append_sheet(workbook,sheet,'Peserta');
  return new File([XLSX.write(workbook,{type:'buffer',bookType:'xlsx'})],'peserta.xlsx');
}

test('reads standard template without changing NIM text',async()=>{
  const {students}=await readParticipants(spreadsheet([
    ['Nama Lengkap','NIM','Program Studi','Fakultas','Asal Kampus'],
    ['Peserta Uji','000000000001','S1 Informatika','FIF','Bandung'],
  ]));
  assert.deepEqual(students,[{nim:'000000000001',nama:'Peserta Uji',prodi:'S1 Informatika',fakultas:'FIF',kampus:'Bandung'}]);
});

test('recognizes common campus headers that the previous reader rejected',async()=>{
  const {students}=await readParticipants(spreadsheet([
    ['No.','Nama Mahasiswa','NIM / NPM','Program Studi (Prodi)','Nama Fakultas','Lokasi Kampus'],
    [1,'Peserta Uji',123456789012,'Informatika','FIF','Jakarta'],
  ]));
  assert.equal(students[0].nama,'Peserta Uji');
  assert.equal(students[0].nim,'123456789012');
  assert.equal(students[0].prodi,'Informatika');
  assert.equal(students[0].fakultas,'FIF');
  assert.equal(students[0].kampus,'Jakarta');
});

test('finds participant data after instruction sheet, title, and blank rows',async()=>{
  const result=await readParticipants(spreadsheet([
    ['DAFTAR PESERTA KEGIATAN'],[],['Tanggal: 4 November 2026'],[],
    ['Nama Peserta','Nomor Induk Mahasiswa','Prodi'],
    ['Peserta Uji','123456789012','Informatika'],
  ],{instructions:true}));
  assert.equal(result.sheetName,'Peserta');
  assert.equal(result.students.length,1);
});

test('preserves leading zeroes from numeric Excel formatting',async()=>{
  const {students}=await readParticipants(spreadsheet([['NIM','Nama'],[1234,'Peserta Uji']],{formatNim:true}));
  assert.equal(students[0].nim,'000000001234');
});

test('semicolon CSV, UTF-8 header, and duplicate NIM are handled',async()=>{
  const file=new File(['\uFEFFNama Mahasiswa;NIM;Fakultas\nPeserta Uji;123456789012;FIF\nPeserta Uji;123456789012;FIF\n'],'peserta.csv');
  const result=await readParticipants(file);
  assert.equal(result.students.length,1);
  assert.equal(result.duplicateCount,1);
});

test('reports the actual spreadsheet row instead of applying a partial import',async()=>{
  const file=spreadsheet([['Judul'],[],['NIM','Nama'],['123456789012','Peserta Uji'],[],['BAD','Peserta Salah']]);
  await assert.rejects(readParticipants(file),/Baris 6/);
});

test('rejects headers without a student name column',async()=>{
  await assert.rejects(readParticipants(spreadsheet([['NIM','Fakultas'],['123456789012','FIF']])),/Kolom Nama Mahasiswa/);
});

test('does not silently round unsafe numeric NIM values',async()=>{
  await assert.rejects(readParticipants(spreadsheet([['NIM','Nama'],[123456789012345678,'Peserta Uji']])),/Simpan kolom NIM sebagai teks/);
});

test('rejects oversized files before parsing',async()=>{
  await assert.rejects(readParticipants({size:10*1024*1024+1}),/maksimal 10 MB/);
});

test('rejects more than 10,000 participant rows instead of truncating',async()=>{
  const rows=[['NIM','Nama'],...Array.from({length:10001},(_,i)=>[String(100000000000+i),'Peserta '+i])];
  await assert.rejects(readParticipants(spreadsheet(rows)),/10.000 baris/);
});
