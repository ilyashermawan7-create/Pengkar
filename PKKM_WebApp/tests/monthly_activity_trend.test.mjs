import test from 'node:test';
import assert from 'node:assert/strict';
import {monthlyActivityTrend} from '../frontend/monthlyActivityTrend.mjs';
import {groupActivities} from '../frontend/navigationGroups.mjs';
test('same name counts once per month/year, ignoring case and whitespace',()=>{
 const result=monthlyActivityTrend([{namaKegiatan:' Webinar   A ',tanggal:'2024-01-01'},
 {namaKegiatan:'webinar a',tanggal:'2024-01-20'},{namaKegiatan:'Webinar A',tanggal:'2024-02-01'},
 {namaKegiatan:'Webinar A',tanggal:'2025-01-01'},{namaKegiatan:'Webinar B',tanggal:'2024-01-02'}]);
 assert.deepEqual(result.series,[{year:'2024',counts:[2,1,0,0,0,0,0,0,0,0,0,0]},{year:'2025',counts:[1,0,0,0,0,0,0,0,0,0,0,0]}]);
});
test('missing dates, invalid calendar dates, and blank names are never assigned invented months',()=>{
 const result=monthlyActivityTrend([{namaKegiatan:'Tahun saja',tahun:'2024'}, {namaKegiatan:'Tanggal salah',tanggal:'2025-02-29'},
 {namaKegiatan:'Bulan salah',tanggal:'2024-13-01'},{namaKegiatan:'Leap',tanggal:'2024-02-29'},{namaKegiatan:' ',tanggal:'2024-01-01'}]);
 assert.equal(result.missingDate,3);assert.equal(result.missingName,1);assert.equal(result.series[0].counts[1],1);
 assert.deepEqual(monthlyActivityTrend([]),{series:[],missingDate:0,missingName:0});
});
test('all groups including the overall dashboard count names from their own filtered datasets',()=>{
 const rows=[{namaKegiatan:'Sama',tanggal:'2026-11-01',program:'Pengembangan Karakter'},
 {namaKegiatan:'Sama',tanggal:'2026-11-02',program:'Asrama'},
 {namaKegiatan:'PPK',tanggal:'2026-11-01',program:'Pengembangan Karakter',navigationGroup:'ppk-telu'},
 {namaKegiatan:'PPKPT',tanggal:'2026-11-01',kategori:'PPKPT'}];
 for(const [group,count] of [['pengkar',2],['asrama',1],['ppk-telu',1],['overview',2]])assert.equal(monthlyActivityTrend(groupActivities(rows,group)).series[0].counts[10],count);
 assert.equal(rows.length,4);
});
