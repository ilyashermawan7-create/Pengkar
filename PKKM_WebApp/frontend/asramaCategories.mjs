export const asramaCategories=['Adaptif','Spiritual','Akademik','Sosial'];
export function asramaCategory(value){
 const key=String(value||'').normalize('NFKC').trim().toLowerCase().replace(/\s+/g,' ');
 return ({adaptif:'Adaptif',adaktif:'Adaptif',spiritual:'Spiritual',spritual:'Spiritual',akademik:'Akademik',sosial:'Sosial'})[key]||null;
}
