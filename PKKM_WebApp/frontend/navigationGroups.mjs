export const navigationGroups=[{id:'pengkar',label:'Pengkar'},{id:'asrama',label:'Asrama'},{id:'ppk-telu',label:'PPK Tel-U'}];
// Existing records stay in Pengkar, independent of their old program/category.
export const navigationGroup=activity=>activity.navigationGroup||'pengkar';
export const groupActivities=(activities,group)=>activities.filter(activity=>navigationGroup(activity)===group);
