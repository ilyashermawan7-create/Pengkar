import schema from '../survey_schema.json' with {type:'json'};
import {average} from './statistics.mjs';

export const csiCategory=percent=>percent===null?'Belum ada nilai':percent>80?'Sangat puas':percent>65?'Puas':percent>50?'Cukup puas':percent>35?'Kurang puas':'Tidak puas';
export const csiMethod='CSI bobot setara: MSSᵢ = rerata jawaban valid pada pertanyaan i; WFᵢ = 1/k; WSᵢ = WFᵢ × MSSᵢ; CSI = ΣWSᵢ ÷ 5 × 100%. k adalah jumlah pertanyaan yang memiliki jawaban. Belum tersedia penilaian kepentingan (MIS), sehingga bobot setara adalah asumsi, bukan CSI berbobot kepentingan hasil survei. Jawaban kosong diabaikan; format lama tidak dicampur. Jika belum semua 20 pertanyaan terisi, hasil bersifat sementara.';
export function calculateCsi(surveys){
  const full=surveys.filter(row=>row.answers?.length===schema.questions.length);
  const items=schema.questions.map((question,index)=>{
    const values=full.map(row=>row.answers[index]).filter(value=>typeof value==='number'&&Number.isFinite(value)&&value>=1&&value<=5);
    return {question,index,count:values.length,mss:average(values)};
  });
  const measured=items.filter(item=>item.mss!==null);
  for(const item of items){item.weight=item.mss===null?null:1/measured.length;item.weightedScore=item.weight===null?null:item.weight*item.mss;}
  const score=average(measured.map(item=>item.mss));
  const percent=score===null?null:score/5*100;
  const groups=schema.groups.map(group=>{
    const mss=average(group.items.map(number=>items[number-1].mss));
    const percent=mss===null?null:mss/5*100;
    return {...group,score:mss,percent,status:csiCategory(percent)};
  });
  return {items,groups,score,percent,status:csiCategory(percent),coverage:measured.length,total:schema.questions.length,provisional:measured.length<schema.questions.length,responses:full.length};
}
