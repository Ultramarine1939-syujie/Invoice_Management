// ═══════════════════════════════════════════════
// 状态
// ═══════════════════════════════════════════════
let selFiles=[], allRec=[], filtRec=[], fields=[];
let sortCol="开票日期", sortDir="desc", charts={};
const STATUS_STORE_KEY="invoice_reimb_status_v1";
const API={
  records:"/api/records",
  status:"/api/records/status",
  parseOne:"/api/parse_one",
  csv:"/api/download_csv",
  excel:"/api/download_excel",
};

const COLS=[
  {key:"文件名",      label:"文件名",      sortable:true},
  {key:"发票号码",    label:"发票号码",     sortable:true},
  {key:"订单号",      label:"订单号",       sortable:true},
  {key:"开票日期",    label:"开票日期",     sortable:true},
  {key:"项目类别",    label:"项目类别",     sortable:true},
  {key:"项目名称",    label:"项目名称",     sortable:true},
  {key:"金额",        label:"金额(¥)",      sortable:true},
  {key:"税率",        label:"税率",         sortable:true},
  {key:"税额",        label:"税额(¥)",      sortable:true},
  {key:"价税合计",    label:"合计(¥)",      sortable:true},
  {key:"销售方名称",  label:"销售方",       sortable:true},
  {key:"解析状态",    label:"解析",         sortable:true},
  {key:"报销状态",    label:"状态",         sortable:false},
  {key:"_action",     label:"操作",         sortable:false},
];

// ═══════════════════════════════════════════════
// DOM
// ═══════════════════════════════════════════════
const $=id=>document.getElementById(id);
const dz=$("dropzone"),fi=$("file-input"),flist=$("file-list");
const btnParse=$("btn-parse"),btnCsv=$("btn-dl-csv"),
      btnXls=$("btn-dl-excel"),btnClear=$("btn-clear");
const statusMsg=$("status-msg"),pbWrap=$("prog-wrap"),
      pbFill=$("pb-fill"),pbText=$("prog-text");
const summaryRow=$("summary-row"),chartSec=$("chart-sec"),resultCard=$("result-card");
const searchBar=$("search-bar"),searchInput=$("search-input");
const fCat=$("f-cat"),fReimb=$("f-reimb");
const thead=$("t-head"),tbody=$("t-body");
const rowCount=$("row-count"),fCount=$("f-count"),fSum=$("f-sum");
const overlay=$("overlay"),moTitle=$("mo-title"),moBody=$("mo-body");

// ═══════════════════════════════════════════════
// 文件选择
// ═══════════════════════════════════════════════
fi.addEventListener("change",()=>addFiles([...fi.files]));
dz.addEventListener("dragover",e=>{e.preventDefault();dz.classList.add("over")});
dz.addEventListener("dragleave",()=>dz.classList.remove("over"));
dz.addEventListener("drop",e=>{
  e.preventDefault();dz.classList.remove("over");
  addFiles([...e.dataTransfer.files].filter(f=>f.name.toLowerCase().endsWith(".pdf")));
});
function addFiles(files){
  for(const f of files)
    if(!selFiles.find(x=>x.name===f.name&&x.size===f.size)) selFiles.push(f);
  renderFList();fi.value="";
}
function removeFile(i){selFiles.splice(i,1);renderFList()}
function renderFList(){
  flist.innerHTML="";
  selFiles.forEach((f,i)=>{
    const d=document.createElement("div");d.className="fi";
    d.innerHTML=`<span>📄</span><span class="fi-name" title="${esc(f.name)}">${esc(f.name)}</span>
      <span class="fi-size">${fmtSz(f.size)}</span>
      <span class="fi-st" id="fs${i}"></span>
      <button class="fi-rm" onclick="removeFile(${i})">✕</button>`;
    flist.appendChild(d);
  });
  btnParse.disabled=selFiles.length===0;
  statusMsg.textContent=selFiles.length?`已选 ${selFiles.length} 个文件`:"";
}

// ═══════════════════════════════════════════════
// 逐文件解析
// ═══════════════════════════════════════════════
btnParse.addEventListener("click",async()=>{
  if(!selFiles.length)return;
  btnParse.disabled=true;btnCsv.disabled=true;btnXls.disabled=true;
  pbWrap.style.display="block";pbFill.style.width="0%";
  statusMsg.textContent="";allRec=[];

  for(let i=0;i<selFiles.length;i++){
    const f=selFiles[i];
    pbFill.style.width=Math.round(i/selFiles.length*100)+"%";
    pbText.textContent=`解析中 (${i+1}/${selFiles.length}): ${f.name}`;
    const st=$("fs"+i);
    if(st){st.textContent="…";st.style.color="var(--muted)"}
    try{
      const fd=new FormData();fd.append("file",f);
      const r=await fetch(API.parseOne,{method:"POST",body:fd});
      const d=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(d.error||("HTTP "+r.status));
      fields=d.fields;
      const rec=d.record;rec["报销状态"]=rec["报销状态"]||"未报销";
      applySavedStatus(rec);
      allRec.push(rec);
      if(st){st.textContent=rec["发票号码"]?"✓":"⚠";
        st.style.color=rec["发票号码"]?"var(--green)":"var(--orange)"}
    }catch(e){
      const rec={};(fields.length?fields:["文件名","备注"]).forEach(k=>rec[k]="");
      rec["文件名"]=f.name;rec["备注"]="解析失败:"+e.message;rec["报销状态"]="未报销";
      applySavedStatus(rec);
      allRec.push(rec);
      if(st){st.textContent="✗";st.style.color="var(--red)"}
    }
  }
  pbFill.style.width="100%";pbText.textContent="全部解析完成";
  setTimeout(()=>pbWrap.style.display="none",800);

  buildCatOpts(allRec);
  renderSummary(allRec);
  applyFilter();
  renderCharts(allRec);
  btnCsv.disabled=false;btnXls.disabled=false;
  statusMsg.textContent=`解析完成，共 ${allRec.length} 条`;
});

async function loadRecordsFromServer(){
  try{
    const r=await fetch(API.records+"?limit=500");
    if(!r.ok)return;
    const d=await r.json();
    if(!d.records||!d.records.length)return;
    fields=d.fields||[];
    allRec=d.records.map(rec=>{rec["报销状态"]=rec["报销状态"]||"未报销";return rec});
    buildCatOpts(allRec);
    renderSummary(allRec);
    applyFilter();
    renderCharts(allRec);
    btnCsv.disabled=false;btnXls.disabled=false;
    statusMsg.textContent=`已载入历史记录 ${allRec.length} 条`;
  }catch(e){
    console.warn("载入历史记录失败",e);
  }
}

// ═══════════════════════════════════════════════
// 清空
// ═══════════════════════════════════════════════
btnClear.addEventListener("click",()=>{
  selFiles=[];allRec=[];filtRec=[];fields=[];
  renderFList();thead.innerHTML="";tbody.innerHTML="";
  resultCard.style.display="none";summaryRow.style.display="none";
  chartSec.style.display="none";searchBar.style.display="none";
  btnCsv.disabled=true;btnXls.disabled=true;statusMsg.textContent="";
  Object.values(charts).forEach(c=>c&&c.destroy&&c.destroy());charts={};
  searchInput.value="";fCat.innerHTML='<option value="">全部类别</option>';fReimb.value="";
});

// ═══════════════════════════════════════════════
// 汇总
// ═══════════════════════════════════════════════
function renderSummary(recs){
  const total=recs.reduce((s,r)=>s+(parseFloat(r["价税合计"])||0),0);
  const amount=recs.reduce((s,r)=>s+(parseFloat(r["金额"])||0),0);
  const tax=recs.reduce((s,r)=>s+(parseFloat(r["税额"])||0),0);
  const doneT=recs.filter(r=>r["报销状态"]==="已报销")
    .reduce((s,r)=>s+(parseFloat(r["价税合计"])||0),0);
  const pendT=total-doneT;
  $("s-count").textContent=recs.length;
  $("s-total").textContent="¥"+total.toFixed(2);
  $("s-amount").textContent="¥"+amount.toFixed(2);
  $("s-tax").textContent="¥"+tax.toFixed(2);
  $("s-pending").textContent="¥"+pendT.toFixed(2);
  $("s-done").textContent="¥"+doneT.toFixed(2);
  summaryRow.style.display="flex";
}

// ═══════════════════════════════════════════════
// 筛选
// ═══════════════════════════════════════════════
function buildCatOpts(recs){
  const cats=[...new Set(recs.map(r=>r["项目类别"]).filter(Boolean))].sort();
  fCat.innerHTML='<option value="">全部类别</option>';
  cats.forEach(c=>fCat.insertAdjacentHTML("beforeend",
    `<option value="${esc(c)}">${esc(c)}</option>`));
}
searchInput.addEventListener("input",applyFilter);
fCat.addEventListener("change",applyFilter);
fReimb.addEventListener("change",applyFilter);

function applyFilter(){
  const kw=searchInput.value.trim().toLowerCase();
  const fc=fCat.value,fr=fReimb.value;
  filtRec=allRec.filter(r=>{
    if(fc&&r["项目类别"]!==fc)return false;
    if(fr){
      if(fr==="done"&&r["报销状态"]!=="已报销")return false;
      if(fr==="pending"&&r["报销状态"]==="已报销")return false;
    }
    if(kw){
      const hay=[r["文件名"],r["发票号码"],r["开票日期"],r["项目名称"],
        r["项目类别"],r["销售方名称"],r["购买方名称"],r["备注"]].join(" ").toLowerCase();
      if(!hay.includes(kw))return false;
    }
    return true;
  });
  sortRec();renderTable();renderSummary(filtRec);
}
function sortRec(){
  filtRec.sort((a,b)=>{
    let av=a[sortCol]||"",bv=b[sortCol]||"";
    if(["金额","税额","价税合计"].includes(sortCol)){
      av=parseFloat(av)||0;bv=parseFloat(bv)||0;
      return sortDir==="asc"?av-bv:bv-av;
    }
    return sortDir==="asc"?String(av).localeCompare(String(bv),"zh")
                          :String(bv).localeCompare(String(av),"zh");
  });
}

// ═══════════════════════════════════════════════
// 表格
// ═══════════════════════════════════════════════
function renderTable(){
  thead.innerHTML="<tr>"+COLS.map(c=>{
    if(!c.sortable) return `<th style="cursor:default">${esc(c.label)}</th>`;
    const cls=c.key===sortCol?sortDir:"";
    return `<th class="${cls}" onclick="setSort('${c.key}')">${esc(c.label)}<span class="sa"></span></th>`;
  }).join("")+"</tr>";

  if(!filtRec.length){
    tbody.innerHTML=`<tr><td colspan="${COLS.length}" class="no-data">暂无数据</td></tr>`;
  }else{
    tbody.innerHTML=filtRec.map((row,i)=>"<tr>"+COLS.map(col=>{
      const v=row[col.key]||"";
      if(col.key==="_action") return `<td><button class="btn btn-ghost" style="padding:3px 10px;font-size:12px" onclick="showDetail(${allRec.indexOf(row)})">详情</button></td>`;
      if(col.key==="报销状态") return `<td>${reimbBtn(allRec.indexOf(row),v)}</td>`;
      if(col.key==="文件名") return `<td class="td-file" title="${esc(v)}">${esc(v)}</td>`;
      if(col.key==="金额") return `<td class="td-price">¥${esc(v)}</td>`;
      if(col.key==="税额") return `<td class="td-tax">¥${esc(v)}</td>`;
      if(col.key==="价税合计") return `<td class="td-total">¥${esc(v)}</td>`;
      if(col.key==="项目类别") return `<td>${catBadge(v)}</td>`;
      if(col.key==="解析状态") return `<td>${parseBadge(v)}</td>`;
      if(col.key==="销售方名称") return `<td style="max-width:180px;overflow:hidden;text-overflow:ellipsis" title="${esc(v)}">${esc(v)}</td>`;
      return `<td>${esc(v)||"-"}</td>`;
    }).join("")+"</tr>").join("");
  }

  const tot=filtRec.reduce((s,r)=>s+(parseFloat(r["价税合计"])||0),0);
  rowCount.textContent=`共 ${allRec.length} 张`;
  fCount.textContent=`筛选 ${filtRec.length} 张`;
  fSum.textContent=filtRec.length?`合计 ¥${tot.toFixed(2)}`:"";
  resultCard.style.display="block";searchBar.style.display="flex";
}
function setSort(col){
  sortDir=sortCol===col?(sortDir==="asc"?"desc":"asc"):"asc";
  sortCol=col;applyFilter();
}

function reimbBtn(idx,status){
  const isDone=status==="已报销";
  return `<button class="reimb-btn ${isDone?"done":"pending"}" onclick="toggleReimb(${idx})">${isDone?"已报销":"未报销"}</button>`;
}
function toggleReimb(idx){
  const r=allRec[idx];
  r["报销状态"]=r["报销状态"]==="已报销"?"未报销":"已报销";
  persistStatus(r);
  applyFilter();
}

function statusKey(rec){
  return rec["发票号码"]||rec["订单号"]||rec["文件名"]||"";
}
function loadStatusStore(){
  try{return JSON.parse(localStorage.getItem(STATUS_STORE_KEY)||"{}")}
  catch{return {}}
}
function saveStatusStore(store){
  localStorage.setItem(STATUS_STORE_KEY,JSON.stringify(store));
}
function applySavedStatus(rec){
  const key=statusKey(rec);
  if(!key)return;
  const saved=loadStatusStore()[key];
  if(saved)rec["报销状态"]=saved;
}
function persistStatus(rec){
  const key=statusKey(rec);
  if(!key)return;
  const store=loadStatusStore();
  store[key]=rec["报销状态"];
  saveStatusStore(store);
  fetch(API.status,{
    method:"PATCH",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({key,status:rec["报销状态"]})
  }).catch(e=>console.warn("保存报销状态失败",e));
}

function catBadge(cat){
  if(!cat)return `<span class="badge bg-gray">-</span>`;
  const cls=cat.includes("旅游")?"bg-blue":cat.includes("代理")?"bg-purple":
    cat.includes("住宿")?"bg-teal":cat.includes("交通")?"bg-orange":"bg-gray";
  return `<span class="badge ${cls}">${esc(cat)}</span>`;
}
function parseBadge(status){
  if(!status)return `<span class="badge bg-gray">-</span>`;
  const cls=status==="已解析"?"bg-green":status==="需复核"?"bg-orange":
    status==="需OCR"?"bg-purple":status==="解析错误"?"bg-orange":"bg-gray";
  return `<span class="badge ${cls}">${esc(status)}</span>`;
}

// ═══════════════════════════════════════════════
// 详情弹窗
// ═══════════════════════════════════════════════
function showDetail(i){
  const r=allRec[i];
  moTitle.textContent="📄 "+(r["文件名"]||"发票详情").replace(/\.pdf$/,"");
  const items=[
    {sec:"基本信息"},
    {l:"发票类型",v:r["发票类型"]},{l:"发票号码",v:r["发票号码"],f:1},
    {l:"订单号",v:r["订单号"]},{l:"开票日期",v:r["开票日期"]},
    {l:"项目名称",v:r["项目名称"],f:1},{l:"项目类别",v:r["项目类别"]},
    {sec:"金额信息"},
    {l:"金额",v:"¥"+r["金额"],cls:"money"},{l:"税率",v:r["税率"]},
    {l:"税额",v:"¥"+r["税额"]},{l:"价税合计",v:"¥"+r["价税合计"],f:1,cls:"money"},
    {l:"合计（大写）",v:r["合计大写"],f:1},
    {sec:"购买方"},
    {l:"名称",v:r["购买方名称"],f:1},{l:"纳税人识别号",v:r["购买方税号"],f:1},
    {sec:"销售方"},
    {l:"名称",v:r["销售方名称"],f:1},{l:"纳税人识别号",v:r["销售方税号"],f:1},
    {sec:"其他"},
    {l:"开票人",v:r["开票人"]},{l:"报销状态",v:r["报销状态"]},
    {l:"解析状态",v:r["解析状态"]},{l:"置信度",v:r["置信度"]},
    {l:"解析备注",v:r["解析备注"],f:1},
    {l:"备注",v:r["备注"]||"-",f:1},
  ];
  moBody.innerHTML=`<div class="dg">`+items.map(it=>{
    if(it.sec) return `<div class="di-sec">${esc(it.sec)}</div>`;
    return `<div class="di${it.f?" full":""}">
      <div class="lbl">${esc(it.l)}</div>
      <div class="val${it.cls?" "+it.cls:""}">${esc(it.v||"-")}</div></div>`;
  }).join("")+"</div>";
  overlay.classList.add("open");
}
$("mo-close").onclick=()=>overlay.classList.remove("open");
overlay.addEventListener("click",e=>{if(e.target===overlay)overlay.classList.remove("open")});
document.addEventListener("keydown",e=>{if(e.key==="Escape")overlay.classList.remove("open")});

// ═══════════════════════════════════════════════
// 图表
// ═══════════════════════════════════════════════
function renderCharts(recs){
  chartSec.style.display="block";
  Object.values(charts).forEach(c=>c&&c.destroy&&c.destroy());charts={};
  const PIE_C=["#1677ff","#fa8c16","#52c41a","#ff4d4f","#722ed1","#13c2c2","#8c8c8c"];
  const labels=recs.map(r=>{
    const n=r["项目名称"]||"";
    return n.length>10?n.substring(0,10)+"…":n;
  });

  // 金额 vs 税额
  charts.amt=new Chart($("c-amount"),{type:"bar",data:{
    labels,datasets:[
      {label:"金额",data:recs.map(r=>+(parseFloat(r["金额"])||0).toFixed(2)),
        backgroundColor:"rgba(22,119,255,.75)",borderRadius:5,borderSkipped:false},
      {label:"税额",data:recs.map(r=>+(parseFloat(r["税额"])||0).toFixed(2)),
        backgroundColor:"rgba(82,196,26,.75)",borderRadius:5,borderSkipped:false}
    ]},options:barOpts()});

  // 价税合计对比
  charts.tot=new Chart($("c-total"),{type:"bar",data:{
    labels,datasets:[{label:"价税合计",
      data:recs.map(r=>+(parseFloat(r["价税合计"])||0).toFixed(2)),
      backgroundColor:PIE_C.slice(0,recs.length),borderRadius:5,borderSkipped:false}
    ]},options:barOpts()});

  // 项目类别分布
  const catMap={};
  recs.forEach(r=>{const c=r["项目类别"]||"其他";catMap[c]=(catMap[c]||0)+parseFloat(r["价税合计"])||0;});
  const catK=Object.keys(catMap);
  charts.cat=new Chart($("c-cat"),{type:"doughnut",data:{
    labels:catK,datasets:[{data:catK.map(k=>+catMap[k].toFixed(2)),
      backgroundColor:PIE_C.slice(0,catK.length),borderWidth:2,borderColor:"#fff"}]
  },options:donutOpts()});

  // 销售方统计
  const sellerMap={};
  recs.forEach(r=>{
    const n=(r["销售方名称"]||"未知");
    const short=n.length>12?n.substring(0,12)+"…":n;
    sellerMap[short]=(sellerMap[short]||0)+parseFloat(r["价税合计"])||0;
  });
  const sK=Object.keys(sellerMap);
  charts.seller=new Chart($("c-seller"),{type:"doughnut",data:{
    labels:sK,datasets:[{data:sK.map(k=>+sellerMap[k].toFixed(2)),
      backgroundColor:PIE_C.slice(0,sK.length),borderWidth:2,borderColor:"#fff"}]
  },options:donutOpts()});
}

function barOpts(){
  return{responsive:true,maintainAspectRatio:false,
    plugins:{legend:{position:"top",labels:{boxWidth:12,font:{size:12}}}},
    scales:{y:{beginAtZero:true,grid:{color:"#f0f0f0"},ticks:{callback:v=>"¥"+v}},
      x:{grid:{display:false}}}};
}
function donutOpts(){
  return{responsive:true,maintainAspectRatio:false,
    plugins:{legend:{position:"right",labels:{boxWidth:12,font:{size:12}}},
      tooltip:{callbacks:{label:ctx=>ctx.label+": ¥"+ctx.parsed.toFixed(2)}}}};
}

// ═══════════════════════════════════════════════
// 导出
// ═══════════════════════════════════════════════
btnCsv.addEventListener("click",async()=>{
  if(!allRec.length)return;
  const r=await fetch(API.csv,{method:"POST",
    headers:{"Content-Type":"application/json"},body:JSON.stringify({records:allRec})});
  if(!r.ok){const j=await r.json().catch(()=>({error:"导出失败"}));alert("导出失败："+j.error);return}
  dlBlob(await r.blob(),"发票报销信息.csv");
});
btnXls.addEventListener("click",async()=>{
  if(!allRec.length)return;
  const orig=btnXls.innerHTML;
  btnXls.disabled=true;btnXls.textContent="⏳ 生成中...";
  try{
    const r=await fetch(API.excel,{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({records:allRec})});
    if(!r.ok){const j=await r.json().catch(()=>({error:"导出失败"}));alert("导出失败："+j.error);return}
    dlBlob(await r.blob(),"发票报销信息.xlsx");
  }finally{btnXls.disabled=false;btnXls.innerHTML=orig}
});
function dlBlob(blob,name){
  const u=URL.createObjectURL(blob);
  Object.assign(document.createElement("a"),{href:u,download:name}).click();
  setTimeout(()=>URL.revokeObjectURL(u),2000);
}

// ═══════════════════════════════════════════════
// 工具
// ═══════════════════════════════════════════════
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
function fmtSz(b){if(b<1024)return b+" B";if(b<1048576)return(b/1024).toFixed(1)+" KB";return(b/1048576).toFixed(1)+" MB"}

loadRecordsFromServer();
