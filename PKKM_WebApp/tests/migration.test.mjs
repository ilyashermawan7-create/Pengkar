import test from 'node:test';
import assert from 'node:assert/strict';
import * as XLSX from 'xlsx';
import schema from '../survey_schema.json' with {type:'json'};
import {readActivities,readSurveyResponses,matchSurveyActivities,parseScore,readDirectory,readActivityParticipants} from '../frontend/migration.mjs';

function file(rows){
  const book=XLSX.utils.book_new();XLSX.utils.book_append_sheet(book,XLSX.utils.aoa_to_sheet(rows),'Data');
  return new File([XLSX.write(book,{type:'buffer',bookType:'xlsx'})],'migrasi.xlsx');
}
function responseFile(values=Array(20).fill(4),extra={}){
  const record={'Nama Kegiatan':'Kegiatan Uji','Timestamp':'04/11/2026 10:15:00','NIM':'000000000001',
    ...Object.fromEntries(schema.questions.map((question,index)=>[question,values[index]])),[schema.suggestion]:'Topik selanjutnya',...extra};
  return file([Object.keys(record),Object.values(record)]);
}

test('the supplied questionnaire has 20 unchanged rating statements and one suggestion',()=>{
  assert.equal(schema.questions.length,20);
  assert.equal(schema.questions[0],'Kegiatan ini meningkatkan pemahaman saya tentang topik yang dibahas.');
  assert.equal(schema.questions[15],'Secara keseluruhan, saya merasa puas dengan pengalaman yang saya dapatkan dari kegiatan ini.');
  assert.equal(schema.questions[19],'Saya merasa puas terhadap pembicara pada kegiatan ini.');
  assert.equal(schema.suggestion,'Saran Topik untuk Webinar selanjutnya');
  assert.equal(schema.questions[1].codePointAt(0),0x2060);
});

test('imports all original question columns and retains raw answers, timestamp and suggestion',async()=>{
  const answers=[1,2,3,4,5,1,2,3,4,5,1,2,3,4,5,1,2,3,4,5];
  const result=await readSurveyResponses(responseFile(answers));
  const item=result.items[0];
  assert.deepEqual(item.response.answers,answers);
  assert.equal(item.response.skorTotal,3);
  assert.equal(item.response.skorKepuasan,1.5);
  assert.equal(item.response.tanggalSurvey,'2026-11-04');
  assert.equal(item.response.submittedAt,'04/11/2026 10:15:00');
  assert.equal(item.response.saran,'Topik selanjutnya');
  assert.equal(item.response.nim,'000000000001');
});

test('Likert labels map 1 to 5 without changing question text',async()=>{
  const answers=Array.from({length:20},(_,index)=>['Sangat Tidak Setuju','Tidak Setuju','Netral','Setuju','Sangat Setuju'][index%5]);
  const result=await readSurveyResponses(responseFile(answers));
  assert.deepEqual(result.items[0].response.answers,Array.from({length:20},(_,i)=>i%5+1));
  assert.equal(parseScore('5 - Sangat Setuju',2,'Q'),5);
  assert.equal(parseScore('Sangat puas',2,'Q'),5);
});

test('blank answers and missing question columns remain null instead of becoming fabricated scores',async()=>{
  const scores=Array(20).fill(4);scores[3]='';
  const first=await readSurveyResponses(responseFile(scores));
  assert.equal(first.items[0].response.answers[3],null);
  assert.equal(first.items[0].response.skorTotal,4);
  const headers=['NIM','Tanggal Survey',...schema.questions.slice(0,19)];
  const second=await readSurveyResponses(file([headers,['123456789012','2026-11-04',...Array(19).fill(4)]]));
  assert.equal(second.items[0].response.answers[19],null);
});

test('surveys with no NIM are still imported when the original questions identify the header',async()=>{
  const record={Timestamp:'04/11/2026 10:00:00',...Object.fromEntries(schema.questions.map(q=>[q,4]))};
  const result=await readSurveyResponses(file([Object.keys(record),Object.values(record)]));
  assert.equal(result.items[0].response.nim,'');
  assert.equal(result.items[0].response.answers.length,20);
});

test('identical anonymous rows retain distinct stable source identities across repeat file imports',async()=>{
  const record={'Nama Kegiatan':'Kegiatan Uji','Tanggal Survey':'2026-11-04',...Object.fromEntries(schema.questions.map(q=>[q,4]))};
  const source=file([Object.keys(record),Object.values(record),Object.values(record)]);
  const first=await readSurveyResponses(source);
  const second=await readSurveyResponses(source);
  assert.notEqual(first.items[0].response.sourceKey,first.items[1].response.sourceKey);
  assert.equal(first.items[0].response.sourceKey,second.items[0].response.sourceKey);
});

test('activity import reads legacy field names, dates, counts and different urusan',async()=>{
  const data=await readActivities(file([
    ['Nama Kegiatan','Tanggal','Jumlah Peserta','Urusan','Kategori','Honor','TAK Panitia','TAK Peserta','Link Evident'],
    ['Konseling Sebaya','21/02/2024','1.234','Konseling','Konseling','Rp 250.000',10,5,'https://example.test/eviden'],
  ]));
  assert.equal(data[0].tanggal,'2024-02-21');
  assert.equal(data[0].jumlahPeserta,1234);
  assert.equal(data[0].program,'Pengembangan Karakter');
  assert.equal(data[0].honor,'Rp 250.000');
  assert.equal(data[0].targetSurveyKepuasan,null);
});

test('invalid calendar dates and unknown program reject activity migration',async()=>{
  await assert.rejects(readActivities(file([['Nama Kegiatan','Tanggal'],['Uji Kalender','2026-02-30']])),/Tanggal kegiatan wajib/);
  await assert.rejects(readActivities(file([['Nama Kegiatan','Tanggal','Program'],['Uji Program','2026-11-04','Unknown']])),/Program wajib/);
});

test('ambiguous activity names require a date or ID and never silently attach to the first match',()=>{
  const activities=[{id:1,namaKegiatan:'Kegiatan Uji',tanggal:'2026-11-04'},{id:2,namaKegiatan:'Kegiatan Uji',tanggal:'2026-11-05'}];
  const item={namaKegiatan:' kegiatan  uji ',sourceRow:2,response:{}};
  assert.throws(()=>matchSurveyActivities([item],activities),/lebih dari satu/);
  assert.equal(matchSurveyActivities([{...item,tanggalKegiatan:'2026-11-05'}],activities)[0].activityId,2);
  assert.equal(matchSurveyActivities([{...item,activityId:1}],activities)[0].activityId,1);
});

test('selected activity and file metadata must agree',()=>{
  const activities=[{id:1,namaKegiatan:'Satu',tanggal:'2026-11-04'},{id:2,namaKegiatan:'Dua',tanggal:'2026-11-04'}];
  assert.throws(()=>matchSurveyActivities([{activityId:2,namaKegiatan:'Dua',sourceRow:2}],activities,'1'),/tidak sesuai pilihan/);
  assert.throws(()=>matchSurveyActivities([{namaKegiatan:'Tidak Ada',sourceRow:2}],activities),/tidak ditemukan/);
});

test('the legacy four-score format remains distinct from the original 20 questions',async()=>{
  const result=await readSurveyResponses(file([['Tanggal Survey','NIM','Skor Materi','Skor Narasumber','Skor Fasilitas','Skor Dampak'],
    ['2026-11-04','123456789012',4,4,4,4]]));
  assert.equal(result.format,'legacy-4');
  assert.equal(result.items[0].response.answers,undefined);
  assert.equal(result.items[0].response.skorTotal,4);
});

test('master students without NIM or name are processed independently of activities',async()=>{
  const records=await readDirectory(file([['NIM','Nama Mahasiswa','Program Studi','Fakultas'],
    ['','Nama Saja','',''],['000000000001','','Informatika','FIF']]));
  assert.equal(records[0].nim,'');
  assert.equal(records[1].nama,'');
  assert.equal(records[1].nim,'000000000001');
  assert.ok(records.every(record=>record.sourceKey));
  const metadataOnly=await readDirectory(file([['Program Studi','Fakultas'],['Informatika','FIF']]));
  assert.equal(metadataOnly[0].nama,'');
  assert.equal(metadataOnly[0].nim,'');
  assert.equal(metadataOnly[0].prodi,'Informatika');
});

test('year-only activities keep year and missing fields instead of inventing a date',async()=>{
  const rows=await readActivities(file([['Nama Kegiatan','Tahun','Jumlah Peserta'],['Arsip 2024','2024','']]));
  assert.equal(rows[0].tahun,'2024');
  assert.equal(rows[0].tanggal,null);
  assert.equal(rows[0].jumlahPeserta,null);
  assert.equal(rows[0].takPanitia,null);
});

test('empty survey dates and unmatched targets can be preserved as pending',async()=>{
  const parsed=await readSurveyResponses(responseFile([5,...Array(19).fill('')],{'Timestamp':'','Nama Kegiatan':''}));
  assert.equal(parsed.items[0].response.tanggalSurvey,null);
  assert.equal(parsed.items[0].response.skorTotal,5);
  const pending=matchSurveyActivities(parsed.items,[],'',true);
  assert.equal(pending[0].activityId,null);
  assert.ok(pending[0].unresolved);
});

test('participant migration reads activity mapping, preserves NIM zeroes and allows empty identity',async()=>{
  const rows=await readActivityParticipants(file([
    ['Nama Kegiatan','Tanggal Kegiatan','NIM','Nama Mahasiswa','Program Studi'],
    ['Kegiatan Uji','2026-11-04','000000000001','Peserta Pertama','Informatika'],
    ['Kegiatan Uji','','','Peserta Tanpa NIM',''],
  ]));
  assert.equal(rows[0].student.nim,'000000000001');
  assert.equal(rows[1].student.nim,'');
  assert.equal(rows[1].student.nama,'Peserta Tanpa NIM');
  assert.notEqual(rows[0].importKey,rows[1].importKey);
  const matched=matchSurveyActivities(rows,[{id:1,namaKegiatan:'Kegiatan Uji',tanggal:'2026-11-04'}],'',true);
  assert.ok(matched.every(item=>item.activityId===1));
});

test('participant files without activity metadata can use a selected destination',async()=>{
  const rows=await readActivityParticipants(file([['NIM','Nama'],['000000000001','Peserta Uji']]));
  const activities=[{id:4,namaKegiatan:'Kegiatan Pilihan',tanggal:'2026-11-04'}];
  assert.equal(matchSurveyActivities(rows,activities,'4',true)[0].activityId,4);
  assert.equal(matchSurveyActivities(rows,activities,'',true)[0].activityId,null);
});
