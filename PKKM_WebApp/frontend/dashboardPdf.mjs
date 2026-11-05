import {jsPDF} from 'jspdf';
import {reportFont} from './reportPdf.mjs';

// Snapshot only the current dashboard; navigation, login, and report forms are excluded.
export async function downloadDashboardPdf(root,title){
 if(!root)throw Error('Dashboard belum tersedia.');
 const controls=Array.from(root.querySelectorAll('select,input,textarea')).map(node=>node.tagName==='SELECT'?node.selectedOptions[0]?.textContent:node.value);
 const copy=root.cloneNode(true);
 copy.querySelectorAll('select,input,textarea').forEach((node,index)=>{const span=document.createElement('span');span.textContent=controls[index]||'—';node.replaceWith(span);});
 copy.querySelectorAll('[data-pdf-exclude],button,script,canvas,details:not([open])').forEach(node=>node.remove());
 copy.style.cssText='position:fixed;left:-20000px;top:0;width:1100px;';
 document.body.appendChild(copy);
 let text;try{text=copy.innerText;}finally{copy.remove();}
 const charts=Array.from(root.querySelectorAll('canvas')).filter(canvas=>canvas.width&&canvas.height&&canvas.getClientRects().length).map(canvas=>({image:canvas.toDataURL('image/png'),ratio:canvas.height/canvas.width}));
 const doc=new jsPDF({unit:'mm',format:'a4'});
 doc.addFileToVFS('report-sans.ttf',await reportFont());doc.addFont('report-sans.ttf','ReportSans','normal');doc.setFont('ReportSans');
 doc.setProperties({title,author:'Direktorat KKA Telkom University'});
 let y=18;const width=182,bottom=278;
 const line=(value,size=10)=>{doc.setFontSize(size);for(const row of doc.splitTextToSize(value,width)){if(y>bottom){doc.addPage();y=18;}doc.text(row,14,y);y+=size*.48+1;}};
 doc.setTextColor('#a6192e');line(title,18);doc.setTextColor('#334155');
 line('Telkom University • '+new Date().toLocaleString('id-ID'),9);
 line('Ringkasan mengikuti grup, filter, dan halaman tabel yang sedang ditampilkan.',9);y+=4;
 for(const row of text.split('\n').map(value=>value.trim()).filter(Boolean))line(row);
 if(charts.length){doc.addPage();y=18;line('Grafik Dashboard',16);for(const chart of charts){const h=Math.min(110,width*chart.ratio);if(y+h>bottom){doc.addPage();y=18;}doc.addImage(chart.image,'PNG',14,y,h/chart.ratio,h);y+=h+10;}}
 const pages=doc.getNumberOfPages();for(let page=1;page<=pages;page++){doc.setPage(page);doc.setFontSize(8);doc.text(`${title} • ${page}/${pages}`,14,290);}
 doc.save(title.replace(/[^a-z0-9]+/gi,'_')+'.pdf');
}
