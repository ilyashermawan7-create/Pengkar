export const activityGroupLabels={karakter:'Kegiatan Karakter',ppkpt:'PPKPT',asrama:'Kegiatan Asrama',lainnya:'Lainnya / Belum Diklasifikasikan'};

export function activityGroup(activity){
  const text=[activity.kategori,activity.urusan,activity.jenis,activity.namaKegiatan,activity.program]
    .map(value=>String(value||'').normalize('NFKC').toLowerCase().replace(/[_-]/g,' ')).join(' ');
  // Specific programs take precedence over generic character-development labels.
  if(/\bppkpt\b|\bppks\b|kekerasan/.test(text))return 'ppkpt';
  if(/\basrama\b|\bresidents?\b|\bresiden\b|\bsr\b/.test(text))return 'asrama';
  if(/karakter|pengkar|wawasan|bela negara|konseling|kesehatan mental/.test(text))return 'karakter';
  return 'lainnya';
}

export function dashboardMetrics(activities){
  const groups={karakter:0,ppkpt:0,asrama:0,lainnya:0};
  let participants=0,unknownParticipants=0;
  for(const activity of activities){
    groups[activityGroup(activity)]+=1;
    if(typeof activity.jumlahPeserta==='number'&&Number.isFinite(activity.jumlahPeserta))participants+=activity.jumlahPeserta;
    else unknownParticipants+=1;
  }
  return {participants,unknownParticipants,total:activities.length,ratio:participants/45000*100,groups};
}
