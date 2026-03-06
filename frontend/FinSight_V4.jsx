import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

/* ================================================================
   DATA
   ================================================================ */
const STOCKS = {
  BABA: { ticker:"BABA",name:"阿里巴巴",exchange:"NYSE",currency:"USD",price:85.32,change_1d:1.45,change_7d:-2.15,change_30d:8.73,volume:"12.3M",marketCap:"208.5B",pe:18.7,trend:"震荡偏强",chart:mkC(85,90,.02),
    news:[{title:"阿里云宣布新一轮降价，AI推理成本下降40%",source:"华尔街见闻",date:"03-05"},{title:"蔡崇信：阿里将持续加大AI基础设施投入",source:"Reuters",date:"03-04"},{title:"阿里国际数字商业Q4收入超预期",source:"Bloomberg",date:"03-01"}],
    followUps:["阿里巴巴PE在同行中算高吗","阿里最近财报摘要","特斯拉对比阿里走势"]},
  TSLA: { ticker:"TSLA",name:"特斯拉",exchange:"NASDAQ",currency:"USD",price:342.18,change_1d:-1.81,change_7d:5.22,change_30d:-3.41,volume:"45.7M",marketCap:"1.09T",pe:62.3,trend:"下跌调整",chart:mkC(342,90,.035),
    news:[{title:"特斯拉FSD V13在中国获批有限测试许可",source:"华尔街见闻",date:"03-05"},{title:"Optimus量产延期至2027年Q2",source:"CNBC",date:"03-03"}],
    followUps:["特斯拉最新财报数据","TSLA和苹果走势对比","什么是市盈率"]},
  AAPL: { ticker:"AAPL",name:"苹果",exchange:"NASDAQ",currency:"USD",price:228.45,change_1d:0.73,change_7d:1.89,change_30d:4.12,volume:"38.2M",marketCap:"3.48T",pe:31.5,trend:"稳步上涨",chart:mkC(228,90,.015),
    news:[{title:"Apple Intelligence中国版合作方确认为百度",source:"华尔街见闻",date:"03-04"},{title:"iPhone 17 Pro Max预期搭载自研5G基带",source:"9to5Mac",date:"03-02"}],
    followUps:["苹果最新季度营收","苹果和腾讯市值对比","什么是市净率"]},
  "0700.HK": { ticker:"0700.HK",name:"腾讯控股",exchange:"HKEX",currency:"HKD",price:418.60,change_1d:1.60,change_7d:3.88,change_30d:11.25,volume:"18.9M",marketCap:"3.92T",pe:22.1,trend:"强势上涨",chart:mkC(418,90,.018),
    news:[{title:"腾讯混元大模型开源版下载量突破500万",source:"华尔街见闻",date:"03-05"},{title:"微信小店GMV同比增长超200%",source:"36氪",date:"03-03"}],
    followUps:["腾讯最近财报表现","腾讯和阿里走势对比","收入和净利润的区别"]},
};
const KNOW = {
  "市盈率":{answer:`**市盈率（Price-to-Earnings Ratio, PE）**是衡量股票估值最常用的指标之一。\n\n**计算公式：**\n- 市盈率 = 股价 ÷ 每股收益（EPS）\n\n**如何理解：**\n- PE = 20 意味着投资者愿意为每1元利润支付20元\n- PE越高，通常说明市场对未来增长预期越高\n- 不同行业PE差异大：科技股30-50x，银行股8-15x\n\n**两种类型：**\n- **静态PE（TTM）：** 基于过去12个月实际收益\n- **动态PE（Forward）：** 基于分析师对未来12个月预测\n\n**注意：**\n- PE为负说明公司亏损，失去参考意义\n- 应同行业横向对比，勿跨行业比较`,sources:[{label:"知识库",ref:"glossary/valuation.md"}],followUps:["什么是市净率","PE和PEG有什么区别","阿里巴巴当前PE是多少"]},
  "收入净利润":{answer:`**收入（Revenue）与净利润（Net Income）**是财务报表最核心的两个指标。\n\n**收入（Top Line）：**\n- 公司主营业务总销售额\n- 位于利润表最顶部\n- 反映市场规模和增长势头\n\n**净利润（Bottom Line）：**\n- 减去所有成本、费用、税收后的最终利润\n- 位于利润表最底部\n- 反映真实盈利能力\n\n**传导链：**\n- 收入 → 毛利润 → 营业利润 → 净利润\n\n**投资启示：**\n- 高收入+低净利润 → 成本控制有问题\n- 净利润增速 > 收入增速 → 利润率扩张`,sources:[{label:"知识库",ref:"glossary/financial_statements.md"}],followUps:["什么是毛利率","EBITDA是什么","苹果最新季度营收"]},
};
function mkC(b,d,v){const r=[];let p=b*(1-v*d*.15);for(let i=d;i>=0;i--){const t=new Date();t.setDate(t.getDate()-i);p*=(1+(Math.random()-.48)*v);r.push({date:`${t.getMonth()+1}/${t.getDate()}`,price:Math.round(p*100)/100})}return r}
function resolve(msg){const u=msg.toUpperCase();if(u.includes("BABA")||msg.includes("阿里"))return{type:"market",data:STOCKS.BABA};if(u.includes("TSLA")||msg.includes("特斯拉"))return{type:"market",data:STOCKS.TSLA};if(u.includes("AAPL")||msg.includes("苹果"))return{type:"market",data:STOCKS.AAPL};if(u.includes("0700")||msg.includes("腾讯"))return{type:"market",data:STOCKS["0700.HK"]};if(msg.includes("市盈率")||msg.includes("PE")||msg.includes("P/E"))return{type:"knowledge",data:KNOW["市盈率"]};if(msg.includes("收入")||msg.includes("净利润")||msg.includes("营收"))return{type:"knowledge",data:KNOW["收入净利润"]};return{type:"fallback"}}

/* ================================================================
   TOKENS
   ================================================================ */
const C={bg:"#F4F6FA",white:"#FFFFFF",border:"#E3E8F0",borderL:"#EEF1F6",text:"#1A2332",ts:"#5A6B80",td:"#94A3B8",
  accent:"#1A6EF5",accentL:"#EBF3FE",
  up:"#D93A3A",upL:"rgba(217,58,58,.08)",
  dn:"#0D9B53",dnL:"rgba(13,155,83,.08)",
  warn:"#D97706",warnBg:"#FFFBEB",
  purple:"#7C3AED",purpleL:"#F3EFFE",
  sk:"#E6EAF0"};
const F={s:"'PingFang SC','Helvetica Neue',system-ui,sans-serif",m:"'JetBrains Mono','SF Mono',monospace"};
const cc=v=>v>=0?C.up:C.dn;
const pf=d=>(d.currency==="HKD"?"HK$":"$")+d.price.toFixed(2);

/* ================================================================
   TINY COMPONENTS
   ================================================================ */
function LoadSteps(){
  const[s,setS]=useState(0);
  const steps=["识别问题类型...","获取市场数据...","生成分析报告..."];
  useEffect(()=>{const a=setTimeout(()=>setS(1),500);const b=setTimeout(()=>setS(2),1100);return()=>{clearTimeout(a);clearTimeout(b)}},[]);
  return(<div style={{padding:"10px 0"}}>{steps.map((t,i)=>(<div key={i} style={{fontSize:12,color:i<=s?C.accent:C.td,display:"flex",alignItems:"center",gap:5,marginBottom:3,opacity:i<=s?1:.4,transition:"all .3s"}}>{i<s?<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>:i===s?<span style={{width:13,height:13,display:"flex",alignItems:"center",justifyContent:"center"}}><span style={{width:5,height:5,borderRadius:"50%",background:C.accent,animation:"pls 1s infinite"}}/></span>:<span style={{width:13,height:13,display:"flex",alignItems:"center",justifyContent:"center"}}><span style={{width:4,height:4,borderRadius:"50%",background:C.td}}/></span>}{t}</div>))}</div>);
}
function Skel(){
  return(<div style={{display:"flex",flexDirection:"column",gap:8}}><div style={{background:C.white,borderRadius:12,padding:18,border:`1px solid ${C.border}`}}><div style={{display:"flex",justifyContent:"space-between"}}><div><div style={{width:55,height:12,background:C.sk,borderRadius:4,marginBottom:7}}/><div style={{width:90,height:16,background:C.sk,borderRadius:4}}/></div><div style={{textAlign:"right"}}><div style={{width:80,height:22,background:C.sk,borderRadius:4,marginBottom:5}}/><div style={{width:50,height:10,background:C.sk,borderRadius:4,marginLeft:"auto"}}/></div></div><div style={{display:"flex",gap:10,marginTop:14,paddingTop:12,borderTop:`1px solid ${C.borderL}`}}>{[1,2,3,4,5].map(i=><div key={i} style={{flex:1}}><div style={{width:"55%",height:8,background:C.sk,borderRadius:3,marginBottom:5}}/><div style={{width:"75%",height:12,background:C.sk,borderRadius:3}}/></div>)}</div></div><div style={{background:C.white,borderRadius:12,padding:16,border:`1px solid ${C.border}`,height:120}}><div style={{width:100,height:10,background:C.sk,borderRadius:3}}/></div></div>);
}

/* ================================================================
   ANSWER COMPONENTS
   ================================================================ */
function DataCard({d}){
  const u1=d.change_1d>=0;const c1=cc(d.change_1d);
  const St=({l,v,col})=>(<div style={{minWidth:0}}><div style={{fontSize:9.5,color:C.td,fontWeight:500,letterSpacing:".04em",textTransform:"uppercase",marginBottom:2}}>{l}</div><div style={{fontSize:12.5,fontWeight:600,fontFamily:F.m,color:col!==undefined?cc(col):C.text,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{col!==undefined?(col>=0?"+":"")+col.toFixed(2)+"%":v}</div></div>);
  return(
    <div style={{background:C.white,borderRadius:12,padding:"15px 18px",border:`1px solid ${C.border}`,boxShadow:"0 1px 3px rgba(0,0,0,.04)"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div><div style={{display:"flex",alignItems:"center",gap:5,marginBottom:2}}><span style={{fontSize:10,fontWeight:700,fontFamily:F.m,padding:"2px 6px",borderRadius:4,background:C.accentL,color:C.accent}}>{d.ticker}</span><span style={{fontSize:10,color:C.td}}>{d.exchange}</span></div><div style={{fontSize:15,fontWeight:800,color:C.text}}>{d.name}</div></div>
        <div style={{textAlign:"right"}}><div style={{fontSize:22,fontWeight:800,fontFamily:F.m,color:c1,lineHeight:1}}>{pf(d)}</div><div style={{fontSize:11,fontFamily:F.m,color:c1,marginTop:2}}>{u1?"▲":"▼"} {u1?"+":""}{d.change_1d.toFixed(2)}% 今日</div></div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(65px,1fr))",gap:6,marginTop:10,paddingTop:10,borderTop:`1px solid ${C.borderL}`}}>
        <St l="7日" col={d.change_7d}/><St l="30日" col={d.change_30d}/><St l="成交量" v={d.volume}/><St l="市值" v={d.marketCap}/><St l="PE" v={d.pe+"x"}/>
      </div>
      <div style={{display:"flex",alignItems:"center",gap:5,marginTop:8}}>
        <span style={{fontSize:10.5,fontWeight:700,padding:"2px 8px",borderRadius:10,background:d.trend.includes("上涨")||d.trend.includes("强")?C.upL:d.trend.includes("下跌")?C.dnL:C.warnBg,color:d.trend.includes("上涨")||d.trend.includes("强")?C.up:d.trend.includes("下跌")?C.dn:C.warn}}>{d.trend}</span>
        <span style={{fontSize:9,color:C.td,marginLeft:"auto",fontFamily:F.m}}>Yahoo Finance</span>
      </div>
    </div>
  );
}

function Chart({data,ticker}){
  const[range,setR]=useState(30);
  const sl=useMemo(()=>data.slice(-range),[data,range]);
  const up=sl[sl.length-1].price>=sl[0].price;const col=up?C.up:C.dn;
  return(
    <div style={{background:C.white,borderRadius:12,padding:"12px 16px",border:`1px solid ${C.border}`,boxShadow:"0 1px 3px rgba(0,0,0,.04)"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}>
        <span style={{fontSize:11.5,fontWeight:600,color:C.ts}}>{ticker} · 价格走势</span>
        <div style={{display:"flex",gap:1,background:C.bg,borderRadius:6,padding:1}}>
          {[{l:"7日",v:7},{l:"30日",v:30},{l:"90日",v:90}].map(r=>(<button key={r.v} onClick={()=>setR(r.v)} style={{fontSize:10,fontWeight:600,padding:"3px 8px",borderRadius:5,border:"none",cursor:"pointer",background:range===r.v?C.white:"transparent",color:range===r.v?C.accent:C.td,transition:"all .15s",boxShadow:range===r.v?"0 1px 2px rgba(0,0,0,.06)":"none"}}>{r.l}</button>))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={sl} margin={{top:4,right:2,left:-22,bottom:0}}>
          <defs><linearGradient id={`g${ticker}${range}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={col} stopOpacity={.12}/><stop offset="100%" stopColor={col} stopOpacity={0}/></linearGradient></defs>
          <XAxis dataKey="date" tick={{fill:C.td,fontSize:9,fontFamily:F.m}} axisLine={false} tickLine={false} interval={range<=7?0:range<=30?5:14}/>
          <YAxis tick={{fill:C.td,fontSize:9,fontFamily:F.m}} axisLine={false} tickLine={false} domain={["auto","auto"]}/>
          <Tooltip contentStyle={{background:C.white,border:`1px solid ${C.border}`,borderRadius:8,fontSize:11,fontFamily:F.m,color:C.text,boxShadow:"0 4px 12px rgba(0,0,0,.08)",padding:"5px 9px"}} formatter={v=>[`$${v.toFixed(2)}`,"价格"]}/>
          <Area type="monotone" dataKey="price" stroke={col} strokeWidth={1.8} fill={`url(#g${ticker}${range})`} dot={false}/>
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function Analysis({text,news,type}){
  const m=type==="market";
  return(
    <div style={{background:m?"#FAFCFF":"#FAFAFF",borderRadius:12,padding:"18px 18px 14px",border:`1px solid ${m?"#D6E4F7":"#E2DBF5"}`,position:"relative"}}>
      <div style={{position:"absolute",top:-9,left:12,background:m?C.accentL:C.purpleL,color:m?C.accent:C.purple,fontSize:9.5,fontWeight:700,padding:"2px 8px",borderRadius:8,border:`1px solid ${m?"#BFD5F0":"#D0C5ED"}`}}>{m?"AI 行情分析":"AI 知识回答"}</div>
      <div style={{fontSize:13,lineHeight:1.85,color:C.text,whiteSpace:"pre-wrap"}}>
        {text.split("\n").map((l,i)=>{
          if(l.startsWith("**")&&l.endsWith("**"))return<div key={i} style={{fontWeight:700,marginTop:7,marginBottom:2,fontSize:13}}>{l.replace(/\*\*/g,"")}</div>;
          if(l.startsWith("- "))return<div key={i} style={{paddingLeft:13,position:"relative",marginBottom:1}}><span style={{position:"absolute",left:0,color:C.accent,fontWeight:700}}>·</span>{l.slice(2)}</div>;
          if(!l.trim())return<div key={i} style={{height:4}}/>;
          return<div key={i}>{l}</div>;
        })}
      </div>
      {m&&news?.length>0&&(
        <div style={{marginTop:12,paddingTop:8,borderTop:`1px solid ${C.borderL}`}}>
          <div style={{fontSize:10,fontWeight:600,color:C.td,marginBottom:5}}>相关新闻</div>
          {news.map((n,i)=>(<div key={i} style={{display:"flex",alignItems:"center",padding:"4px 0",borderBottom:i<news.length-1?`1px solid ${C.borderL}`:"none",gap:6}}><span style={{fontSize:11.5,color:C.text,flex:1,minWidth:0,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{n.title}</span><span style={{fontSize:9.5,color:C.accent,fontWeight:600,flexShrink:0}}>{n.source}</span><span style={{fontSize:9.5,color:C.td,fontFamily:F.m,flexShrink:0}}>{n.date}</span></div>))}
        </div>
      )}
    </div>
  );
}

function Src({items}){return(<div style={{display:"flex",gap:4,flexWrap:"wrap"}}>{items.map((s,i)=>(<span key={i} style={{fontSize:9.5,padding:"3px 8px",borderRadius:10,background:C.bg,border:`1px solid ${C.border}`,color:C.ts,fontFamily:F.m}}><span style={{color:C.accent,marginRight:2}}>●</span>{s.label}{s.provider?`: ${s.provider}`:""}{s.ref?` · ${s.ref}`:""}</span>))}</div>)}
function Disc(){return(<div style={{fontSize:10.5,color:C.warn,padding:"7px 11px",background:C.warnBg,borderRadius:7,borderLeft:`3px solid ${C.warn}`,lineHeight:1.5}}>⚠️ 行情数据来自公开API，AI分析仅供参考，不构成投资建议。</div>)}
function FU({items,onSend}){return(<div style={{display:"flex",gap:5,flexWrap:"wrap"}}>{items.map((q,i)=>(<button key={i} onClick={()=>onSend(q)} style={{fontSize:11,padding:"5px 11px",borderRadius:12,cursor:"pointer",background:C.white,border:`1px solid ${C.border}`,color:C.ts,fontFamily:F.s,transition:"all .15s"}} onMouseEnter={e=>{e.target.style.borderColor=C.accent;e.target.style.color=C.accent;e.target.style.background=C.accentL}} onMouseLeave={e=>{e.target.style.borderColor=C.border;e.target.style.color=C.ts;e.target.style.background=C.white}}>↗ {q}</button>))}</div>)}

function Collapsed({msg,onExpand}){
  const r=msg.result;
  if(r.type==="market"){const d=r.data;const u=d.change_1d>=0;
    return(<div onClick={onExpand} style={{background:C.white,borderRadius:10,padding:"9px 14px",border:`1px solid ${C.border}`,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"space-between",transition:"all .15s"}} onMouseEnter={e=>e.currentTarget.style.borderColor=C.accent} onMouseLeave={e=>e.currentTarget.style.borderColor=C.border}>
      <div style={{display:"flex",alignItems:"center",gap:8,minWidth:0}}><span style={{fontSize:10,fontWeight:700,fontFamily:F.m,padding:"2px 5px",borderRadius:3,background:C.accentL,color:C.accent,flexShrink:0}}>{d.ticker}</span><span style={{fontSize:12.5,fontWeight:600,color:C.text,flexShrink:0}}>{d.name}</span><span style={{fontSize:12.5,fontWeight:700,fontFamily:F.m,color:cc(d.change_1d),flexShrink:0}}>{pf(d)}</span><span style={{fontSize:10.5,fontWeight:600,fontFamily:F.m,color:cc(d.change_1d),flexShrink:0}}>{u?"▲":"▼"}{u?"+":""}{d.change_1d.toFixed(2)}%</span></div>
      <span style={{fontSize:10.5,color:C.accent,flexShrink:0,marginLeft:8}}>展开 ↓</span></div>);}
  if(r.type==="knowledge"){const p=r.data.answer.slice(0,50).replace(/\*\*/g,"");
    return(<div onClick={onExpand} style={{background:C.white,borderRadius:10,padding:"9px 14px",border:`1px solid ${C.border}`,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"space-between",transition:"all .15s"}} onMouseEnter={e=>e.currentTarget.style.borderColor=C.purple} onMouseLeave={e=>e.currentTarget.style.borderColor=C.border}>
      <div style={{display:"flex",alignItems:"center",gap:6,minWidth:0}}><span style={{fontSize:9.5,fontWeight:700,padding:"2px 5px",borderRadius:3,background:C.purpleL,color:C.purple,flexShrink:0}}>知识</span><span style={{fontSize:12.5,color:C.text,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{p}...</span></div>
      <span style={{fontSize:10.5,color:C.purple,flexShrink:0,marginLeft:8}}>展开 ↓</span></div>);}
  return null;
}

function FullAns({result,onSend}){
  if(result.type==="market"){const d=result.data;const ud=v=>v>=0?"上涨":"下跌";const ab=v=>Math.abs(v).toFixed(2);
    const txt=`近期${d.name}（${d.ticker}）呈${d.trend}态势。\n\n**客观数据：**\n- 当前价 ${pf(d)}，今日${ud(d.change_1d)}${ab(d.change_1d)}%\n- 7日${ud(d.change_7d)}${ab(d.change_7d)}%，30日${ud(d.change_30d)}${ab(d.change_30d)}%\n\n**可能影响因素：**\n${d.news.map(n=>`- [${n.source}] ${n.title}（${n.date}）`).join("\n")}\n\n**趋势总结：**\n综合近期数据与公开新闻，${d.name}短期处于${d.trend}状态。`;
    return(<div style={{display:"flex",flexDirection:"column",gap:7}}><DataCard d={d}/><Chart data={d.chart} ticker={d.ticker}/><Analysis text={txt} news={d.news} type="market"/><Src items={[{label:"行情",provider:"Yahoo Finance"},{label:"新闻",provider:"Tavily"}]}/><Disc/>{d.followUps&&<FU items={d.followUps} onSend={onSend}/>}</div>);}
  if(result.type==="knowledge"){return(<div style={{display:"flex",flexDirection:"column",gap:7}}><Analysis text={result.data.answer} type="knowledge"/><Src items={result.data.sources}/>{result.data.followUps&&<FU items={result.data.followUps} onSend={onSend}/>}</div>);}
  /* Fallback with clickable stocks */
  const stocks=Object.values(STOCKS);
  return(<div style={{background:C.white,border:`1px solid ${C.border}`,borderRadius:12,padding:"15px 18px",fontSize:13,color:C.text,lineHeight:1.7}}>
    抱歉，暂时无法识别您的问题。请尝试以下查询：
    <div style={{display:"flex",flexWrap:"wrap",gap:6,marginTop:10}}>
      {stocks.map(s=>(<button key={s.ticker} onClick={()=>onSend(`${s.name}最近走势`)} style={{display:"flex",alignItems:"center",gap:5,padding:"6px 12px",borderRadius:8,border:`1px solid ${C.border}`,background:C.bg,cursor:"pointer",fontFamily:F.s,fontSize:12,color:C.text,transition:"all .15s"}} onMouseEnter={e=>{e.currentTarget.style.borderColor=C.accent;e.currentTarget.style.background=C.accentL}} onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border;e.currentTarget.style.background=C.bg}}>
        <span style={{fontWeight:700,fontFamily:F.m,fontSize:10,color:C.accent}}>{s.ticker}</span><span>{s.name}</span><span style={{fontFamily:F.m,fontSize:11,fontWeight:600,color:cc(s.change_1d)}}>{s.change_1d>=0?"+":""}{s.change_1d.toFixed(2)}%</span>
      </button>))}
    </div>
    <div style={{marginTop:10,display:"flex",gap:6}}>
      <button onClick={()=>onSend("什么是市盈率")} style={{padding:"6px 12px",borderRadius:8,border:`1px solid ${C.border}`,background:C.bg,cursor:"pointer",fontFamily:F.s,fontSize:12,color:C.text,transition:"all .15s"}} onMouseEnter={e=>{e.currentTarget.style.borderColor=C.purple;e.currentTarget.style.background=C.purpleL}} onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border;e.currentTarget.style.background=C.bg}}>📚 什么是市盈率</button>
      <button onClick={()=>onSend("收入和净利润的区别")} style={{padding:"6px 12px",borderRadius:8,border:`1px solid ${C.border}`,background:C.bg,cursor:"pointer",fontFamily:F.s,fontSize:12,color:C.text,transition:"all .15s"}} onMouseEnter={e=>{e.currentTarget.style.borderColor=C.purple;e.currentTarget.style.background=C.purpleL}} onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border;e.currentTarget.style.background=C.bg}}>📚 收入和净利润的区别</button>
    </div>
  </div>);
}

/* ================================================================
   MARKET SNAPSHOT
   ================================================================ */
function Snap({onQ,compact}){
  const tks=["BABA","TSLA","AAPL","0700.HK"];
  if(compact){return(<div style={{display:"flex",gap:6,overflowX:"auto",padding:"8px 20px",borderBottom:`1px solid ${C.border}`,background:C.white}}>
    {tks.map(t=>{const s=STOCKS[t];const u=s.change_1d>=0;return(
      <button key={t} onClick={()=>onQ(`${s.name}最近走势如何`)} style={{display:"flex",alignItems:"center",gap:6,padding:"5px 10px",background:C.bg,border:`1px solid ${C.border}`,borderRadius:7,cursor:"pointer",whiteSpace:"nowrap",flexShrink:0,transition:"all .15s",fontFamily:F.s,fontSize:0}} onMouseEnter={e=>e.currentTarget.style.borderColor=C.accent} onMouseLeave={e=>e.currentTarget.style.borderColor=C.border}>
        <span style={{fontSize:11.5,fontWeight:700,color:C.text}}>{s.name}</span>
        <span style={{fontSize:11.5,fontWeight:700,fontFamily:F.m,color:cc(s.change_1d)}}>{u?"+":""}{s.change_1d.toFixed(2)}%</span>
      </button>)})}
  </div>);}
  return(
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(155px,1fr))",gap:8}}>
      {tks.map(t=>{const s=STOCKS[t];const u=s.change_1d>=0;const col=cc(s.change_1d);const mini=s.chart.slice(-8);
        return(<div key={t} onClick={()=>onQ(`${s.name}最近走势如何`)} style={{background:C.white,borderRadius:10,padding:"12px 14px",border:`1px solid ${C.border}`,cursor:"pointer",transition:"all .2s",boxShadow:"0 1px 3px rgba(0,0,0,.03)"}} onMouseEnter={e=>{e.currentTarget.style.borderColor=C.accent;e.currentTarget.style.boxShadow="0 2px 8px rgba(26,110,245,.1)"}} onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border;e.currentTarget.style.boxShadow="0 1px 3px rgba(0,0,0,.03)"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:3}}>
            <span style={{fontSize:12.5,fontWeight:700,color:C.text}}>{s.name}</span>
            <span style={{fontSize:9.5,color:C.td,fontFamily:F.m}}>{s.ticker}</span>
          </div>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end"}}>
            <span style={{fontSize:17,fontWeight:800,fontFamily:F.m,color:col,lineHeight:1}}>{s.currency==="HKD"?"HK$":"$"}{s.price.toFixed(2)}</span>
            <span style={{fontSize:10.5,fontWeight:700,fontFamily:F.m,color:col,padding:"2px 5px",borderRadius:4,background:u?C.upL:C.dnL}}>{u?"+":""}{s.change_1d.toFixed(2)}%</span>
          </div>
          <div style={{height:24,marginTop:5}}><ResponsiveContainer width="100%" height="100%"><AreaChart data={mini} margin={{top:2,right:0,left:0,bottom:0}}><defs><linearGradient id={`sm${t}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={col} stopOpacity={.15}/><stop offset="100%" stopColor={col} stopOpacity={0}/></linearGradient></defs><Area type="monotone" dataKey="price" stroke={col} strokeWidth={1.3} fill={`url(#sm${t})`} dot={false}/></AreaChart></ResponsiveContainer></div>
        </div>)})}
    </div>
  );
}

/* ================================================================
   INPUT BOX (shared between home + chat)
   ================================================================ */
function InputBox({value,onChange,onSend,onClear,mode,setMode,loading,centered}){
  const ph=mode==="market"?"输入股票名称或代码，如 BABA、阿里巴巴、腾讯...":"输入金融概念或问题，如「什么是市盈率」...";
  return(
    <div style={{maxWidth:centered?580:740,width:"100%",margin:centered?"0 auto":undefined}}>
      <div style={{background:C.white,borderRadius:14,border:`1px solid ${C.border}`,boxShadow:centered?"0 2px 12px rgba(0,0,0,.06)":"0 2px 8px rgba(0,0,0,.04)",overflow:"hidden"}}>
        {/* Mode tabs */}
        <div style={{display:"flex",borderBottom:`1px solid ${C.borderL}`,padding:"0 4px"}}>
          {[{key:"market",icon:"📈",label:"查行情"},{key:"knowledge",icon:"📚",label:"学知识"}].map(m=>(
            <button key={m.key} onClick={()=>setMode(m.key)} style={{flex:1,display:"flex",alignItems:"center",justifyContent:"center",gap:5,padding:"10px 0",fontSize:12.5,fontWeight:mode===m.key?700:500,color:mode===m.key?C.accent:C.td,background:"transparent",border:"none",cursor:"pointer",borderBottom:mode===m.key?`2px solid ${C.accent}`:"2px solid transparent",transition:"all .15s",fontFamily:F.s}}>
              <span>{m.icon}</span>{m.label}
            </button>
          ))}
        </div>
        {/* Input row */}
        <div style={{display:"flex",alignItems:"center",padding:"4px 5px 4px 16px",gap:6}}>
          <input value={value} onChange={e=>onChange(e.target.value)} onKeyDown={e=>e.key==="Enter"&&onSend()} placeholder={ph}
            style={{flex:1,background:"transparent",border:"none",outline:"none",color:C.text,fontSize:13.5,fontFamily:F.s,padding:"9px 0"}}/>
          {value&&(<button onClick={onClear} style={{width:24,height:24,borderRadius:"50%",border:"none",background:C.bg,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,transition:"all .15s"}} onMouseEnter={e=>e.currentTarget.style.background=C.border} onMouseLeave={e=>e.currentTarget.style.background=C.bg}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={C.ts} strokeWidth="3" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>)}
          <button onClick={onSend} disabled={!value?.trim()||loading} style={{width:36,height:36,borderRadius:10,border:"none",background:value?.trim()&&!loading?`linear-gradient(135deg,${C.accent},#3B82F6)`:C.bg,cursor:value?.trim()&&!loading?"pointer":"default",display:"flex",alignItems:"center",justifyContent:"center",transition:"all .2s",flexShrink:0,opacity:value?.trim()&&!loading?1:.35}}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke={value?.trim()&&!loading?"#fff":C.td} strokeWidth="2.5" strokeLinecap="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   MAIN APP
   ================================================================ */
export default function App(){
  const[msgs,setMsgs]=useState([]);
  const[input,setInput]=useState("");
  const[loading,setLoading]=useState(false);
  const[expIdx,setExpIdx]=useState(null);
  const[mode,setMode]=useState("market");
  const[showTop,setShowTop]=useState(false);
  const endRef=useRef(null);
  const scrollRef=useRef(null);
  const inChat=msgs.length>0;

  useEffect(()=>{setTimeout(()=>endRef.current?.scrollIntoView({behavior:"smooth"}),100)},[msgs,expIdx]);
  useEffect(()=>{const el=scrollRef.current;if(!el)return;const h=()=>setShowTop(el.scrollTop>350);el.addEventListener("scroll",h);return()=>el.removeEventListener("scroll",h)},[]);
  useEffect(()=>{const last=msgs.map((m,i)=>m.role==="ai"?i:-1).filter(i=>i>=0).pop();if(last!==undefined)setExpIdx(last)},[msgs]);

  const send=useCallback(async(text)=>{
    const q=(text||input).trim();if(!q||loading)return;
    setMsgs(p=>[...p,{role:"user",text:q}]);setInput("");setLoading(true);
    await new Promise(r=>setTimeout(r,1400+Math.random()*400));
    setMsgs(p=>[...p,{role:"ai",result:resolve(q)}]);setLoading(false);
  },[input,loading]);

  const goHome=useCallback(()=>{setMsgs([]);setExpIdx(null);setInput("")},[]);

  const lastR=msgs.filter(m=>m.role==="ai").slice(-1)[0]?.result;
  const pills=lastR?.type==="market"?(lastR.data.followUps||[]).slice(0,3):lastR?.type==="knowledge"?(lastR.data.followUps||[]).slice(0,3):["阿里巴巴走势","TSLA行情","什么是市盈率"];

  /* Home suggestions by mode */
  const homeMkt=["阿里巴巴最近7天涨跌","特斯拉近期走势","腾讯控股行情","AAPL最近为什么涨了"];
  const homeKnow=["什么是市盈率","收入和净利润的区别"];

  return(
    <div style={{width:"100vw",height:"100vh",background:C.bg,fontFamily:F.s,display:"flex",flexDirection:"column",overflow:"hidden"}}>
      <style>{`@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}@keyframes pls{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}*{box-sizing:border-box;margin:0;padding:0}::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:10px}input::placeholder{color:${C.td}}`}</style>

      {/* HEADER */}
      <header style={{background:C.white,borderBottom:`1px solid ${C.border}`,padding:"0 20px",height:48,display:"flex",alignItems:"center",justifyContent:"space-between",flexShrink:0,zIndex:10}}>
        <div style={{display:"flex",alignItems:"center",gap:6}}>
          {inChat&&<button onClick={goHome} style={{display:"flex",alignItems:"center",gap:3,background:"none",border:"none",cursor:"pointer",color:C.accent,fontSize:11.5,fontWeight:600,fontFamily:F.s,padding:"4px 6px",borderRadius:5,transition:"all .15s"}} onMouseEnter={e=>e.target.style.background=C.accentL} onMouseLeave={e=>e.target.style.background="transparent"}><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>首页</button>}
          <div onClick={goHome} style={{display:"flex",alignItems:"center",gap:7,cursor:"pointer"}}>
            <div style={{width:26,height:26,borderRadius:6,background:`linear-gradient(135deg,${C.accent},#3B82F6)`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:900,color:"#fff"}}>F</div>
            <span style={{fontSize:14,fontWeight:800,color:C.text}}>FinSight AI</span>
          </div>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          {inChat&&<button onClick={goHome} style={{display:"flex",alignItems:"center",gap:3,background:C.bg,border:`1px solid ${C.border}`,cursor:"pointer",color:C.ts,fontSize:10.5,fontWeight:600,fontFamily:F.s,padding:"4px 9px",borderRadius:5,transition:"all .15s"}} onMouseEnter={e=>{e.currentTarget.style.borderColor=C.accent;e.currentTarget.style.color=C.accent}} onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border;e.currentTarget.style.color=C.ts}}><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>新对话</button>}
          <span style={{fontSize:9.5,padding:"3px 6px",borderRadius:3,background:C.upL,color:C.up,fontWeight:700,fontFamily:F.m}}>● LIVE</span>
        </div>
      </header>

      {inChat&&<Snap onQ={send} compact/>}

      {/* CONTENT */}
      <div ref={scrollRef} style={{flex:1,overflowY:"auto",padding:inChat?"14px 0 115px":"0"}}>
        <div style={{maxWidth:740,margin:"0 auto",padding:"0 20px"}}>

          {/* ===== HOME ===== */}
          {!inChat&&(
            <div style={{display:"flex",flexDirection:"column",justifyContent:"center",minHeight:"calc(100vh - 48px)",padding:"0 0 40px",animation:"fadeUp .4s ease-out"}}>
              {/* Hero */}
              <div style={{textAlign:"center",marginBottom:24}}>
                <div style={{width:44,height:44,borderRadius:12,margin:"0 auto 12px",background:`linear-gradient(135deg,${C.accent},#6366f1)`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,fontWeight:900,color:"#fff",boxShadow:"0 4px 16px rgba(26,110,245,.18)"}}>F</div>
                <h1 style={{fontSize:20,fontWeight:800,color:C.text,marginBottom:4}}>金融资产智能问答</h1>
                <p style={{fontSize:13,color:C.ts}}>实时行情查询 · 涨跌原因分析 · 金融知识问答</p>
              </div>

              {/* Market Snapshot */}
              <div style={{marginBottom:20}}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
                  <span style={{fontSize:13,fontWeight:700,color:C.text}}>市场快照</span>
                  <span style={{fontSize:10,color:C.td,fontFamily:F.m}}>{new Date().toLocaleDateString("zh-CN")}</span>
                </div>
                <Snap onQ={send}/>
              </div>

              {/* Centered Input Box */}
              <InputBox value={input} onChange={setInput} onSend={()=>send()} onClear={()=>setInput("")} mode={mode} setMode={setMode} loading={loading} centered/>

              {/* Mode-specific suggestions */}
              <div style={{maxWidth:580,margin:"14px auto 0",display:"flex",flexWrap:"wrap",gap:6,justifyContent:"center"}}>
                {(mode==="market"?homeMkt:homeKnow).map((q,i)=>(<button key={i} onClick={()=>send(q)} style={{fontSize:11.5,padding:"6px 14px",borderRadius:18,border:`1px solid ${C.border}`,background:C.white,color:C.text,cursor:"pointer",fontFamily:F.s,transition:"all .15s"}} onMouseEnter={e=>{e.target.style.borderColor=mode==="market"?C.accent:C.purple;e.target.style.color=mode==="market"?C.accent:C.purple;e.target.style.background=mode==="market"?C.accentL:C.purpleL}} onMouseLeave={e=>{e.target.style.borderColor=C.border;e.target.style.color=C.text;e.target.style.background=C.white}}>{mode==="market"?"📈":"📚"} {q}</button>))}
              </div>
            </div>
          )}

          {/* ===== MESSAGES ===== */}
          {msgs.map((msg,i)=>(
            <div key={i} style={{marginBottom:10,animation:"fadeUp .3s ease-out"}}>
              {msg.role==="user"?(
                <div style={{display:"flex",justifyContent:"flex-end"}}><div style={{background:C.accent,color:"#fff",borderRadius:"14px 14px 4px 14px",padding:"8px 14px",maxWidth:"75%",fontSize:13,lineHeight:1.5,boxShadow:"0 1px 3px rgba(26,110,245,.15)"}}>{msg.text}</div></div>
              ):(
                expIdx===i?(
                  <div><div style={{display:"flex",justifyContent:"flex-end",marginBottom:3}}><button onClick={()=>setExpIdx(null)} style={{fontSize:10,color:C.td,background:"none",border:"none",cursor:"pointer",padding:"2px 5px"}}>收起 ↑</button></div><FullAns result={msg.result} onSend={send}/></div>
                ):(<Collapsed msg={msg} onExpand={()=>setExpIdx(i)}/>)
              )}
            </div>
          ))}

          {loading&&<div style={{animation:"fadeUp .3s ease-out"}}><LoadSteps/><Skel/></div>}
          <div ref={endRef}/>
        </div>
      </div>

      {/* SCROLL TOP */}
      {showTop&&<button onClick={()=>scrollRef.current?.scrollTo({top:0,behavior:"smooth"})} style={{position:"fixed",bottom:130,right:20,width:34,height:34,borderRadius:"50%",background:C.white,border:`1px solid ${C.border}`,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",boxShadow:"0 2px 6px rgba(0,0,0,.08)",zIndex:20}}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.ts} strokeWidth="2.5" strokeLinecap="round"><polyline points="18 15 12 9 6 15"/></svg></button>}

      {/* BOTTOM INPUT (chat mode only) */}
      {inChat&&(
        <div style={{position:"fixed",bottom:0,left:0,right:0,background:"rgba(244,246,250,.92)",backdropFilter:"blur(12px)",borderTop:`1px solid ${C.border}`,padding:"8px 20px 12px",zIndex:10}}>
          <div style={{maxWidth:740,margin:"0 auto"}}>
            {/* Context pills */}
            <div style={{display:"flex",gap:4,marginBottom:6,overflowX:"auto",paddingBottom:2}}>
              {pills.map((q,i)=>(<button key={i} onClick={()=>send(q)} style={{background:C.white,border:`1px solid ${C.border}`,borderRadius:11,padding:"3px 9px",fontSize:10.5,color:C.ts,cursor:"pointer",fontFamily:F.s,whiteSpace:"nowrap",flexShrink:0,transition:"all .15s"}} onMouseEnter={e=>{e.target.style.borderColor=C.accent;e.target.style.color=C.accent}} onMouseLeave={e=>{e.target.style.borderColor=C.border;e.target.style.color=C.ts}}>↗ {q}</button>))}
            </div>
            <InputBox value={input} onChange={setInput} onSend={()=>send()} onClear={()=>setInput("")} mode={mode} setMode={setMode} loading={loading}/>
            <div style={{textAlign:"center",marginTop:4,fontSize:9,color:C.td}}>FinSight AI · 数据来自 Yahoo Finance · AI分析不构成投资建议</div>
          </div>
        </div>
      )}
    </div>
  );
}
