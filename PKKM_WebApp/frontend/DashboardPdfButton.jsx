import React,{useState} from 'react';
import {downloadDashboardPdf} from './dashboardPdf.mjs';
export default function DashboardPdfButton({title,disabled=false}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 return <div data-pdf-exclude className="flex flex-wrap items-center justify-end gap-3"><button disabled={disabled||busy} className="rounded-xl bg-red-700 text-white px-4 py-2.5 text-sm font-bold disabled:opacity-50" onClick={async event=>{
  const root=event.currentTarget.closest('main');setBusy(true);setError('');
  try{await downloadDashboardPdf(root,title);}catch(err){setError('PDF gagal dibuat: '+err.message);}finally{setBusy(false);}
 }}>{busy?'Menyiapkan PDF…':'Ekspor PDF Dashboard'}</button>{error&&<p role="alert" className="text-sm text-red-700">{error}</p>}</div>;
}
