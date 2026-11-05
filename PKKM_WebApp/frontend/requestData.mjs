export async function requestData(url,options={},timeoutMs=45000){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),timeoutMs);
 try{
   const response=await fetch(url,{...options,signal:controller.signal});
   const data=response.headers.get('content-type')?.includes('application/json')?await response.json():await response.text();
   return {response,data};
 }catch(error){
   if(controller.signal.aborted)throw new Error('Server belum merespons dalam batas waktu. Silakan coba kembali beberapa saat lagi.');
   if(error instanceof SyntaxError)throw new Error('Data dari server belum termuat lengkap. Muat ulang halaman dan coba kembali.');
   throw error;
 }finally{clearTimeout(timer);}
}
