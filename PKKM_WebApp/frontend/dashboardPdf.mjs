import {jsPDF} from 'jspdf';
import html2canvas from 'html2canvas';

// Render the active dashboard itself, preserving its responsive layout and charts.
export async function downloadDashboardPdf(root,title){
 if(!root)throw Error('Dashboard belum tersedia.');
 await document.fonts.ready;
 await Promise.all(Array.from(root.querySelectorAll('img')).map(image=>image.decode().catch(()=>{})));
 const rect=root.getBoundingClientRect();
 const controls=Array.from(root.querySelectorAll('select,input,textarea')).map(node=>({text:node.tagName==='SELECT'?node.selectedOptions[0]?.textContent:(node.value||node.placeholder||''),height:node.getBoundingClientRect().height}));
 const canvas=await html2canvas(root,{
  backgroundColor:'#f5f6f8',scale:Math.min(1.5,16000/Math.max(root.scrollHeight,rect.width)),
  useCORS:true,logging:false,windowWidth:window.innerWidth,windowHeight:window.innerHeight,
  ignoreElements:element=>element.hasAttribute('data-pdf-exclude'),
  onclone:documentCopy=>{
   // Keep banner photographs above their backgrounds in the canvas renderer.
   documentCopy.querySelectorAll('main select,main input,main textarea').forEach((control,index)=>{
    const value=controls[index];if(!value)return;
    const replacement=documentCopy.createElement('div');replacement.className=control.className;
    replacement.style.cssText=`height:${value.height}px;box-sizing:border-box;display:flex;align-items:center;line-height:1.4;`;
    replacement.textContent=value.text;control.replaceWith(replacement);
   });
   documentCopy.querySelectorAll('main details:not([open])').forEach(detail=>{
    Array.from(detail.children).filter(child=>child.tagName!=='SUMMARY').forEach(child=>child.remove());
    const summary=detail.querySelector('summary');if(summary){summary.style.listStyle='none';summary.textContent='▸ '+summary.textContent;}
   });
   documentCopy.querySelectorAll('.telu-banner-photo').forEach(image=>{
    const layer=documentCopy.createElement('div');layer.className=image.className;
    layer.style.cssText=`position:absolute;inset:0;background-image:url("${image.src}");background-size:cover;background-position:66% 55%;z-index:0;`;image.replaceWith(layer);
   });
  }
 });
 const doc=new jsPDF({unit:'mm',format:'a4',compress:true});
 doc.setProperties({title,author:'Direktorat KKA Telkom University'});
 const width=190,pageHeight=277,pixelsPerPage=Math.floor(pageHeight*canvas.width/width);
 const slice=document.createElement('canvas');slice.width=canvas.width;
 try{
  for(let offset=0,page=0;offset<canvas.height;offset+=pixelsPerPage,page++){
   slice.height=Math.min(pixelsPerPage,canvas.height-offset);
   const context=slice.getContext('2d');
   context.fillStyle='#fff';context.fillRect(0,0,slice.width,slice.height);
   context.drawImage(canvas,0,offset,slice.width,slice.height,0,0,slice.width,slice.height);
   if(page)doc.addPage();
   doc.addImage(slice.toDataURL('image/jpeg',.94),'JPEG',10,10,width,slice.height*width/slice.width);
  }
  doc.save(title.replace(/[^a-z0-9]+/gi,'_')+'.pdf');
 }finally{canvas.width=canvas.height=slice.width=slice.height=0;}
}
