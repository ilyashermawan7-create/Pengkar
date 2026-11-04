export const monthLabels=['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
export function monthlyActivityTrend(activities){
  const years=new Map();
  let missingDate=0,missingName=0;
  for(const activity of activities){
    const name=String(activity.namaKegiatan||'').normalize('NFKC').trim().toLocaleLowerCase('id').replace(/\s+/gu,' ');
    const match=/^(\d{4})-(\d{2})-(\d{2})$/.exec(activity.tanggal||'');
    const valid=match&&Number(match[1])>=1000&&Number(match[2])>=1&&Number(match[2])<=12&&Number(match[3])>=1&&Number(match[3])<=new Date(Date.UTC(Number(match[1]),Number(match[2]),0)).getUTCDate();
    if(!valid){missingDate++;continue;}
    if(!name){missingName++;continue;}
    const year=match[1],month=Number(match[2])-1;
    if(!years.has(year))years.set(year,Array.from({length:12},()=>new Set()));
    years.get(year)[month].add(name);
  }
  const series=[...years.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([year,months])=>({year,counts:months.map(names=>names.size)}));
  return {series,missingDate,missingName};
}
