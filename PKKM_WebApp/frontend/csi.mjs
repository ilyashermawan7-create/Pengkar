import schema from '../survey_schema.json' with {type:'json'};
import {average} from './statistics.mjs';

export const csiDivisor=field=>['skorMateri','skorNarasumber'].includes(field)?5:4;
export const questionDivisor=index=>csiDivisor(schema.groups.find(group=>group.items.includes(index+1))?.field);

export const csiCategory=percent=>percent===null?'Belum ada nilai':percent>80?'Sangat puas':percent>65?'Puas':percent>50?'Cukup puas':percent>35?'Kurang puas':'Tidak puas';
export const csiMethod='CSI bobot setara: MSSᵢ = rerata jawaban valid pada pertanyaan i; WFᵢ = 1/k; WSᵢ = WFᵢ × MSSᵢ; CSI = Σ(WFᵢ × MSSᵢ ÷ pembagiᵢ) × 100%. Pemahaman dan relevansi materi serta kepuasan terhadap narasumber memakai pembagi 5; kelompok lainnya memakai pembagi 4. k adalah jumlah pertanyaan yang memiliki jawaban. Bobot setara berlaku per pertanyaan setelah normalisasi, bukan per kelompok. Nilai kepentingan (MIS) belum tersedia, sehingga bobot setara adalah asumsi. Jawaban kosong diabaikan; format lama tidak dicampur. Hasil sementara jika belum semua 20 pertanyaan terwakili. Jawaban asli dipertahankan; hasil dapat melebihi 100% jika rerata melebihi pembagi.';
export function calculateCsi(surveys){
  const full=surveys.filter(row=>row.answers?.length===schema.questions.length);
  const items=schema.questions.map((question,index)=>{
    const values=full.map(row=>row.answers[index]).filter(value=>typeof value==='number'&&Number.isFinite(value)&&value>=1&&value<=5);
    return {question,index,divisor:questionDivisor(index),count:values.length,mss:average(values)};
  });
  const measured=items.filter(item=>item.mss!==null);
  for(const item of items){item.weight=item.mss===null?null:1/measured.length;item.weightedScore=item.weight===null?null:item.weight*item.mss;item.contribution=item.weightedScore===null?null:item.weightedScore/item.divisor*100;}
  const score=average(measured.map(item=>item.mss));
  const percent=score===null?null:measured.reduce((sum,item)=>sum+item.contribution,0);
  const groups=schema.groups.map(group=>{
    const mss=average(group.items.map(number=>items[number-1].mss));
    const percent=mss===null?null:mss/csiDivisor(group.field)*100;
    return {...group,divisor:csiDivisor(group.field),score:mss,percent,status:csiCategory(percent)};
  });
  return {items,groups,score,percent,status:csiCategory(percent),coverage:measured.length,total:schema.questions.length,provisional:measured.length<schema.questions.length,responses:full.length};
}
