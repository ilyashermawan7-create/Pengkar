import {activityGroup} from './dashboardMetrics.mjs';
export const navigationGroups=[{id:'overview',label:'Dashboard'},{id:'pengkar',label:'Pengkar'},{id:'asrama',label:'Asrama'},{id:'ppk-telu',label:'PPK Tel-U'}];
export function navigationGroup(activity){
  // PPK Tel-U is explicitly separate from the existing PPKPT category.
  if(activity.navigationGroup==='ppk-telu')return 'ppk-telu';
  if(activity.navigationGroup==='asrama'||activity.program==='Asrama'||activityGroup(activity)==='asrama')return 'asrama';
  const category=activityGroup(activity);
  if(category==='karakter'||category==='ppkpt'||activity.program==='Pengembangan Karakter')return 'pengkar';
  return null;
}
export const groupActivities=(activities,group)=>activities.filter(activity=>group==='overview'?['pengkar','asrama'].includes(navigationGroup(activity)):navigationGroup(activity)===group);
