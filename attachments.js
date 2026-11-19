/* File bodies and thumbnail URLs stay in this tab's memory. Stored rows are descriptors only. */
(() => {
  'use strict';
  const bytesPerMiB=1024*1024, countLimit=3;
  const types={txt:'text/plain',md:'text/markdown',csv:'text/csv',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    pdf:'application/pdf',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp'};
  const pool=new Map();
  const available=row=>pool.has(row.ref);
  const accept=Object.keys(types).map(ext=>'.'+ext).join(',');
  function sizeLabel(bytes){
    return bytes>=bytesPerMiB?(bytes/bytesPerMiB).toFixed(1)+' MiB':bytes>=1024?Math.ceil(bytes/1024)+' KiB':bytes+' B';
  }
  function checkImage(buffer,mime) {
    const b=new Uint8Array(buffer), v=new DataView(buffer);
    const ascii=(at,len)=>String.fromCharCode(...b.subarray(at,at+len));
    let width=0,height=0,animated=false;
    if(mime==='image/png' && b.length>=33 && b[0]===137 && ascii(1,3)==='PNG' && ascii(12,4)==='IHDR'){
      width=v.getUint32(16);height=v.getUint32(20);
      for(let i=8;i+12<=b.length;i+=v.getUint32(i)+12){
        if(ascii(i+4,4)==='acTL')animated=true;
        if(ascii(i+4,4)==='IDAT')break;
      }
    }else if(mime==='image/jpeg' && b[0]===255 && b[1]===216){
      for(let pos=2;pos+8<b.length;){
        if(b[pos++]!==255)break;
        while(b[pos]===255)pos++;
        const tag=b[pos++];
        if(tag===218 || tag===217 || pos+7>b.length)break;
        if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(tag)){
          height=v.getUint16(pos+3);width=v.getUint16(pos+5);break;
        }
        const length=v.getUint16(pos);if(length<2)break;pos+=length;
      }
    }else if(mime==='image/webp' && b.length>=30 && ascii(0,4)==='RIFF' && ascii(8,4)==='WEBP'){
      const type=ascii(12,4);
      if(type==='VP8X'){
        width=1+b[24]+256*b[25]+65536*b[26];height=1+b[27]+256*b[28]+65536*b[29];animated=Boolean(b[20]&2);
      }else if(type==='VP8 ' && b[23]===157 && b[24]===1 && b[25]===42){
        width=v.getUint16(26,true)&16383;height=v.getUint16(28,true)&16383;
      }else if(type==='VP8L' && b[20]===47){
        const bits=v.getUint32(21,true);width=1+(bits&16383);height=1+((bits>>>14)&16383);
      }
    }
    if(!width || !height)throw Error('图片内容与格式不符或无法读取，请重新导出为 PNG、JPEG 或 WebP。');
    if(animated || width*height>12000000)throw Error('请选择不超过 1200 万像素的单帧图片。');
  }
  async function select(current,files) {
    const result=current.slice(), pending=new Map();
    for(const file of files) {
      const ext=file.name.split('.').at(-1).toLowerCase(), mime=Object.hasOwn(types,ext)?types[ext]:null;
      if(!mime || !file.name.includes('.'))throw Error('支持 TXT、MD、CSV、DOCX、PDF、PNG、JPEG 和 WebP 文件。');
      if(!file.size || file.size>3*bytesPerMiB)throw Error('每份附件须大于 0 字节且不超过 3 MiB。');
      if(Array.from(file.name).length>120 || /[\\/\p{C}]/u.test(file.name))throw Error('请将文件重命名为 120 字以内的普通文件名。');
      const buffer=await file.arrayBuffer();
      if(mime.startsWith('image/'))checkImage(buffer,mime);
      const digest=await crypto.subtle.digest('SHA-256',buffer);
      const hash=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
      const existing=result.find(item=>item.name===file.name && item.sha256===hash);
      if(existing && (available(existing) || pending.has(existing.ref)))continue;
      if(!existing && result.length>=countLimit)throw Error('每条消息最多可添加 3 份附件，请先移除一份。');
      const row=existing || {ref:crypto.randomUUID(),name:file.name,mime,size:file.size,sha256:hash};
      if(!existing)result.push(row);
      if(result.reduce((sum,r)=>sum+r.size,0)>6*bytesPerMiB)throw Error('本条消息的附件合计超过 6 MiB，请减少附件。');
      pending.set(row.ref,{file});
    }
    // Commit only a fully valid selection, preserving the prior draft on any error.
    for(const [ref,entry] of pending)pool.set(ref,entry);
    return result;
  }
  function thumbnail(row) {
    const entry=pool.get(row.ref);
    if(!entry || !row.mime.startsWith('image/'))return '';
    if(!entry.url)entry.url=URL.createObjectURL(entry.file.slice(0,entry.file.size,row.mime));
    return entry.url;
  }
  function prune(references) {
    const keep=new Set(references.map(row=>row.ref));
    for(const [key,entry] of pool){
      if(keep.has(key))continue;
      if(entry.url)URL.revokeObjectURL(entry.url);
      pool.delete(key);
    }
  }
  function same(a=[],b=[]){
    return a.length===b.length && a.every((row,index)=>row.name===b[index].name && row.mime===b[index].mime && row.sha256===b[index].sha256);
  }
  async function packet(rows){
    const result=[];
    for(const row of rows) {
      const entry=pool.get(row.ref);
      if(!entry)throw Error('请重新选择本条消息的原附件，或从草稿中移除后重新发送。');
      const bytes=new Uint8Array(await entry.file.arrayBuffer());
      let binary='';
      for(let start=0;start<bytes.length;start+=32768)binary+=String.fromCharCode(...bytes.subarray(start,start+32768));
      result.push({name:row.name,mime:row.mime,data:btoa(binary)});
    }
    return result;
  }
  window.YincaiAttachments=Object.freeze({accept,sizeLabel,select,available,thumbnail,same,packet,prune});
})();
