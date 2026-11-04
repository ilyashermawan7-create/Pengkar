import test from 'node:test';
import assert from 'node:assert/strict';
import {groupActivities} from '../frontend/navigationGroups.mjs';
test('legacy dorm activities are separated from character and PPKPT even with old Pengkar navigation tag',()=>{
 const rows=[{id:1,program:'Pengembangan Karakter',kategori:'Pengembangan Karakter',navigationGroup:'pengkar'},
 {id:2,program:'Pengembangan Karakter',kategori:'PPKPT'},
 {id:3,program:'Asrama',kategori:'Pengembangan Karakter',navigationGroup:'pengkar'},
 {id:4,program:'Asrama',kategori:'PPKPT'},
 {id:5,program:'Pengembangan Karakter',namaKegiatan:'SR Camp'},
 {id:6,program:'Pengembangan Karakter',navigationGroup:'ppk-telu'},
 {id:7,program:'Asrama',navigationGroup:'asrama'}];
 assert.deepEqual(groupActivities(rows,'pengkar').map(row=>row.id),[1,2]);
 assert.deepEqual(groupActivities(rows,'asrama').map(row=>row.id),[3,4,5,7]);
 assert.deepEqual(groupActivities(rows,'ppk-telu').map(row=>row.id),[6]);
});
test('unknown programs are not automatically counted as character development',()=>{
 assert.deepEqual(groupActivities([{id:1,namaKegiatan:'Tidak terklasifikasi'}],'pengkar'),[]);
});
