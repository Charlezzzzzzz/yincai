const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

test('compact teacher review opens with bookmarks, preserves pending count, and verifies saved decisions', async()=>{
  const rows = ['S1','S2','S3'].map(student_id=>({
    student_id, source_hash:'fixture', revision:0, action:'pending',
    current:'原始建议', original:'原始建议'
  }));
  const host = {
    html:'', controls:new Map(),
    set innerHTML(html){this.html=html; this.controls.clear();},
    querySelector(selector){
      if(!this.controls.has(selector)) this.controls.set(selector,{
        addEventListener(name,handler){this['on'+name]=handler;}, focus(){}
      });
      return this.controls.get(selector);
    },
    querySelectorAll(selector){
      const field = selector.match(/^\[data-(student|save)\]$/)?.[1];
      if (!field) return [];
      return Array.from(this.html.matchAll(new RegExp('data-'+field+'="([^"]+)"','g')), match=>{
        const button=this.querySelector('['+'data-'+field+'="'+match[1]+'"]');
        button.dataset={[field]:match[1]};
        return button;
      });
    }
  };
  const plans = rows.map(r=>({student_id:r.student_id,recommendation:r.original,evidence:[]}));
  const requests = [];
  const window = {
    EVIDENCE:Object.fromEntries(['plan_xiaoan','plan_xiaohe','plan_xiaoyuan'].map((key,i)=>[key,plans[i]])),
    addEventListener(){}
  };
  const fetch = async(url,init)=>{
    requests.push([url,init.method||'GET']);
    const response = payload=>({ok:true,json:async()=>structuredClone(payload)});
    if(url==='/api/teacher/overview') return response({plans,classroom:{
      total_people:30,top_three_count:23,cause_distribution:[]
    }});
    assert.equal(url,'/api/v7/reviews');
    if(!init.method) return response({teacher_only:true,reviews:rows});
    const input=JSON.parse(init.body);
    const row=rows.find(r=>r.student_id===input.student_id);
    assert.equal(input.expected_revision,row.revision);
    row.revision++; row.action=input.action;
    if(input.action==='modified') row.current=input.current;
    return response({review:row});
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'review.js'),'utf8'),{
    window, location:{protocol:'http:'}, document:{body:{dataset:{view:'teacher'}},querySelectorAll:()=>[]}, fetch
  });
  window.YincaiReview.render(host);
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(host.html, /任课教师 · 最终决定/);
  assert.match(host.html, /待审 3 条/);
  assert.equal(host.querySelectorAll('[data-student]').length,3);
  assert.ok(host.html.indexOf('class="bookmarks"') < host.html.indexOf('id="review-paper"'));
  assert.ok(host.html.indexOf('class="review-copy"') < host.html.indexOf('class="decision-rail"'));
  assert.ok(host.html.indexOf('class="decision-rail"') < host.html.indexOf('class="review-margin"'));
  assert.match(host.html,/id="review-evidence">批阅依据/);
  assert.match(host.html,/模拟班级 30 人，前三类错因共 23 人/);
  assert.doesNotMatch(host.html,/teacher-desk|data-look|<canvas|teacher-puppet/);
  host.querySelector('[data-edit]').onclick();
  host.querySelector('textarea').oninput({target:{value:'我的教师稿'}});
  await host.querySelector('[data-save="modified"]').onclick();
  assert.match(host.html,/我的教师稿/);
  assert.match(host.html,/待审 2 条/);
  host.querySelector('[data-student="1"]').onclick();
  await host.querySelector('[data-save="adopted"]').onclick();
  await host.querySelector('[data-save="rejected"]').onclick();
  assert.match(host.html,/待审 0 条/);
  assert.match(host.html,/小远第三段微课的旁白与公式仍待复核/);
  assert.deepEqual(rows.map(r=>r.action),['modified','adopted','rejected']);
  const writes=requests.map((item,index)=>item[1]==='POST'?index:-1).filter(index=>index>=0);
  assert.equal(writes.length,3);
  for(const index of writes) assert.deepEqual(requests[index+1],['/api/v7/reviews','GET']);
});
