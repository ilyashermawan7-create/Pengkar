import test from 'node:test';
import assert from 'node:assert/strict';
import {calculateCsi,csiCategory} from '../frontend/csi.mjs';
const row=answers=>({answers});
test('complete equal-weight CSI follows MSS, WF, WS and configured divisor of four',()=>{
  const csi=calculateCsi([row(Array(20).fill(3)),row(Array(20).fill(5))]);
  assert.equal(csi.percent,100);assert.equal(csi.status,'Sangat puas');assert.equal(csi.provisional,false);
  assert.equal(csi.items[0].weight,.05);assert.equal(csi.items[0].weightedScore,.2);
  assert.ok(Math.abs(csi.items.reduce((sum,item)=>sum+item.weightedScore,0)/4*100-csi.percent)<1e-10);
});
test('each attribute has equal weight even when respondent completion differs',()=>{
  const csi=calculateCsi([row([1,...Array(19).fill(null)]),row(Array(20).fill(5))]);
  // First attribute MSS=3, nineteen other attributes MSS=5; not mean of respondent averages (3).
  assert.equal(csi.score,4.9);assert.ok(Math.abs(csi.percent-122.5)<1e-10);
  assert.equal(csi.items[0].count,2);assert.equal(csi.items[1].count,1);
});
test('unanswered attributes are reported explicitly as provisional, never zero-filled',()=>{
  const answers=[null,4,...Array(18).fill(null)];const csi=calculateCsi([row(answers)]);
  assert.equal(csi.percent,100);assert.equal(csi.coverage,1);assert.equal(csi.provisional,true);
  assert.equal(csi.items[0].weight,null);assert.equal(csi.items[1].weight,1);
  assert.deepEqual(answers,[null,4,...Array(18).fill(null)]);
});
test('legacy records, invalid scores and empty answers never create CSI scores',()=>{
  const csi=calculateCsi([{skorTotal:5},row(Array(20).fill(null)),row([0,6,'5',NaN,...Array(16).fill(null)])]);
  assert.equal(csi.percent,null);assert.equal(csi.coverage,0);assert.equal(csi.status,'Belum ada nilai');
});
test('category boundaries are explicit without premature rounding',()=>{
  for(const [score,label] of [[35,'Tidak puas'],[35.01,'Kurang puas'],[50,'Kurang puas'],[50.01,'Cukup puas'],[65,'Cukup puas'],[65.01,'Puas'],[80,'Puas'],[80.01,'Sangat puas']])assert.equal(csiCategory(score),label);
});

test('MSS 3.30 becomes 82.50 percent with divisor four',()=>{
  const csi=calculateCsi(Array.from({length:10},(_,i)=>row(Array(20).fill(i<3?4:3))));
  assert.ok(Math.abs(csi.percent-82.5)<1e-10);
});
