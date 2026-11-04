import test from 'node:test';
import assert from 'node:assert/strict';
import {activityGroup,dashboardMetrics} from '../frontend/dashboardMetrics.mjs';

test('ratio uses total attendance and can exceed 100 percent',()=>{
  const metrics=dashboardMetrics([{jumlahPeserta:57109,program:'Pengembangan Karakter'}]);
  assert.equal(metrics.participants,57109);
  assert.equal(metrics.ratio.toFixed(2),'126.91');
});

test('the screenshot overlap becomes an exclusive partition of 88 activities',()=>{
  const character=Array.from({length:42},()=>({kategori:'Pengembangan Karakter',urusan:'Pengembangan karakter',program:'Pengembangan Karakter'}));
  const dorm=Array.from({length:36},(_,index)=>({namaKegiatan:'Pengkar Asrama',kategori:'Asrama',urusan:index<15?'Pengembangan karakter':'Asrama',program:'Asrama'}));
  const ppkpt=Array.from({length:10},()=>({kategori:'PPKPT',program:'Pengembangan Karakter'}));
  const rows=[...character,...dorm,...ppkpt];
  rows[0].jumlahPeserta=57109;
  const oldCount=pattern=>rows.filter(a=>pattern.test(`${a.kategori} ${a.namaKegiatan} ${a.urusan}`)).length;
  assert.equal(oldCount(/karakter|wawasan|bela negara/i),57);
  assert.equal(oldCount(/asrama|resident/i),36);
  assert.equal(oldCount(/ppkpt|ppks|kekerasan/i),10);
  const metrics=dashboardMetrics(rows);
  assert.equal(metrics.total,88);
  assert.deepEqual(metrics.groups,{karakter:42,ppkpt:10,asrama:36,lainnya:0});
  assert.equal(Object.values(metrics.groups).reduce((sum,n)=>sum+n,0),metrics.total);
});

test('specific categories are prioritized and every record counts exactly once',()=>{
  assert.equal(activityGroup({namaKegiatan:'Pengembangan Karakter Asrama: Sosialisasi PPKPT',program:'Asrama'}),'ppkpt');
  assert.equal(activityGroup({namaKegiatan:'SR Camp',kategori:'Pengembangan Karakter',program:'Pengembangan Karakter'}),'asrama');
  assert.equal(activityGroup({namaKegiatan:'Diskusi Presidential Leadership',program:'Pengembangan Karakter'}),'karakter');
  assert.equal(activityGroup({namaKegiatan:'Data tanpa klasifikasi'}),'lainnya');
});

test('empty or unknown counts do not corrupt attendance or ratio',()=>{
  assert.equal(dashboardMetrics([]).ratio,0);
  const metrics=dashboardMetrics([{jumlahPeserta:null},{jumlahPeserta:undefined},{jumlahPeserta:0},{jumlahPeserta:45000,program:'Pengembangan Karakter'}]);
  assert.equal(metrics.participants,45000);
  assert.equal(metrics.ratio,100);
  assert.equal(metrics.unknownParticipants,2);
  assert.equal(metrics.groups.lainnya,3);
  assert.equal(Object.values(metrics.groups).reduce((sum,n)=>sum+n,0),4);
});
