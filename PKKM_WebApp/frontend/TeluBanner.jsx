import React from 'react';
export default function TeluBanner({group='overview',title,subtitle}){
 const second=group==='asrama'||group==='ppk-telu';
 return <section className="telu-banner" aria-label="Banner Telkom University">
  <img className="telu-banner-photo" src={second?'/static/images/telu-bangkit.jpg':'/static/images/telu-tower.jpg'} alt="" decoding="async" fetchPriority="low"/>
  <div className="telu-banner-shade" aria-hidden="true"/>
  <div className="telu-banner-copy"><span className="telu-eyebrow">TELKOM UNIVERSITY <span aria-hidden="true">/</span> DIREKTORAT KKA</span><h1>{title}</h1><p>{subtitle}</p><div className="telu-banner-tags"><span>Pengembangan Karakter &amp; Asrama</span><span>Pencegahan Kekerasan</span><span>Kemahasiswaan</span></div></div>
  <span className="telu-banner-mark" aria-hidden="true">TEL-U<span>Creating the Future</span></span>
 </section>;
}
