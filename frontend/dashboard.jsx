import { useState, useEffect, useRef, useCallback } from "react";

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:        "#05080d",
  bgAlt:     "#080c14",
  surface:   "#0b1120",
  surfaceHi: "#0f1a2e",
  border:    "#152035",
  borderHi:  "#1e3050",
  amber:     "#e8a020",
  amberDim:  "#5a3d08",
  green:     "#2dcc7a",
  greenDim:  "#0d4a2a",
  blue:      "#3a9fd8",
  blueDim:   "#0d2e50",
  red:       "#d95f5f",
  teal:      "#2abfbf",
  tealDim:   "#0a3a3a",
  purple:    "#8b67d4",
  text:      "#b8c8dc",
  textDim:   "#445a78",
  textFaint: "#1e2e45",
  white:     "#e8f0f8",
};

// Stack definitions (derived from stage)
const STACKS = {
  manager: {
    id:"manager", label:"MANAGER", icon:"◎", color:T.amber,
    role:"Research · Plan · Delegate",
    model:"codex", desc:"Ingests backlog/inbox and coordinates sessions",
  },
  analyzer: {
    id:"analyzer", label:"ANALYZER", icon:"◈", color:T.teal,
    role:"System · Traces · Architecture",
    model:"codex", desc:"Pre-flight analysis and testing feedback",
  },
  coder: {
    id:"coder", label:"CODER", icon:"◇", color:T.green,
    role:"Implement · Fix · Refactor",
    model:"codex", desc:"Executes active sessions and applies changes",
  },
};

// Backend stages
const STAGES = [
  { id:"inbox",    label:"INBOX",    icon:"⊙", tip:"New signals — not yet reviewed",           color:T.textDim },
  { id:"analysis", label:"ANALYSIS", icon:"↘", tip:"Manager analyzing & splitting",           color:T.purple  },
  { id:"backlog",  label:"BACKLOG",  icon:"═", tip:"Queued and waiting for activation",       color:T.amber   },
  { id:"active",   label:"ACTIVE",   icon:"↑", tip:"Session running right now",               color:T.green   },
  { id:"testing",  label:"TESTING",  icon:"⟲", tip:"Test session verifying the changes",      color:T.blue    },
  { id:"done",     label:"DONE",     icon:"✓", tip:"Completed and verified",                  color:T.teal    },
  { id:"blocked",  label:"BLOCKED",  icon:"⚠", tip:"Needs input or is blocked",               color:T.red     },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmtTime = d => d.toLocaleTimeString("en-US",{hour12:false,hour:"2-digit",minute:"2-digit",second:"2-digit"});
const fmtAge  = d => {
  const s = Math.floor((Date.now()-d)/1000);
  if(s<60) return `${s}s ago`;
  if(s<3600) return `${Math.floor(s/60)}m ago`;
  return `${Math.floor(s/3600)}h ago`;
};

const stageToStack = (stage) => {
  if(stage==="analysis") return "manager";
  if(stage==="active") return "coder";
  if(stage==="testing") return "analyzer";
  if(stage==="blocked") return "manager";
  return "manager";
};

const STATUS_TO_STAGE = {
  radar: "inbox",
  runway: "backlog",
  flight: "active",
  blocked: "blocked",
  done: "done",
};

const STAGE_TO_STATUS = {
  inbox: "radar",
  analysis: "radar",
  backlog: "runway",
  active: "flight",
  testing: "flight",
  blocked: "blocked",
  done: "done",
};

// ─── Micro-components ─────────────────────────────────────────────────────────
const Pill = ({color,children,sm}) => (
  <span style={{
    display:"inline-flex",alignItems:"center",
    padding: sm?"1px 5px":"2px 7px",
    borderRadius:3, fontSize:sm?8:9, fontWeight:700,
    letterSpacing:"0.1em", textTransform:"uppercase",
    background:`${color}20`, color, border:`1px solid ${color}40`,
  }}>{children}</span>
);

const Bar = ({v,max,color,h=3}) => (
  <div style={{height:h,borderRadius:2,background:T.border,overflow:"hidden"}}>
    <div style={{height:"100%",width:`${Math.min(100,(v/max)*100)}%`,background:color,
      boxShadow:`0 0 5px ${color}80`,transition:"width .7s ease"}}/>
  </div>
);

function RadarSweep({ tasks }) {
  const canvasRef = useRef(null);
  const angle = useRef(0);
  const animRef = useRef(null);

  const blips = tasks.filter(t=>t.stage==="inbox"||t.stage==="analysis").map((_,i)=>({
    a: (i * 137.5) % 360,
    r: 0.3 + (i % 5) * 0.12,
    age: Math.random(),
  }));

  useEffect(()=>{
    const canvas = canvasRef.current;
    if(!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height, cx = W/2, cy = H/2, R = W/2-4;

    const draw = () => {
      ctx.clearRect(0,0,W,H);
      // rings
      for(let r=0.25;r<=1;r+=0.25){
        ctx.beginPath(); ctx.arc(cx,cy,R*r,0,Math.PI*2);
        ctx.strokeStyle=`${T.borderHi}`; ctx.lineWidth=0.5; ctx.stroke();
      }
      // crosshairs
      ctx.strokeStyle=T.borderHi; ctx.lineWidth=0.5;
      ctx.beginPath(); ctx.moveTo(cx,4); ctx.lineTo(cx,H-4); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(4,cy); ctx.lineTo(W-4,cy); ctx.stroke();

      // sweep gradient
      const sweep = ctx.createConicalGradient ? null : null;
      const a = angle.current * Math.PI / 180;
      const grad = ctx.createLinearGradient(cx,cy,
        cx+Math.cos(a)*R, cy+Math.sin(a)*R);
      grad.addColorStop(0,`${T.amber}00`);
      grad.addColorStop(1,`${T.amber}35`);
      ctx.save();
      ctx.translate(cx,cy); ctx.rotate(a);
      ctx.beginPath(); ctx.moveTo(0,0); ctx.arc(0,0,R,-0.6,0.6); ctx.closePath();
      ctx.fillStyle=grad; ctx.fill();
      ctx.restore();

      // sweep line
      ctx.beginPath(); ctx.moveTo(cx,cy);
      ctx.lineTo(cx+Math.cos(a)*R, cy+Math.sin(a)*R);
      ctx.strokeStyle=T.amber; ctx.lineWidth=1.2; ctx.stroke();

      // blips
      blips.forEach(b=>{
        const ba = b.a * Math.PI/180;
        const br = b.r * R;
        const bx = cx + Math.cos(ba)*br, by = cy + Math.sin(ba)*br;
        const diff = ((angle.current - b.a) % 360 + 360) % 360;
        const alpha = diff < 60 ? (1 - diff/60)*0.9 : 0.1;
        ctx.beginPath(); ctx.arc(bx,by,3,0,Math.PI*2);
        ctx.fillStyle=`${T.green}${Math.round(alpha*255).toString(16).padStart(2,"0")}`;
        ctx.fill();
        ctx.beginPath(); ctx.arc(bx,by,6,0,Math.PI*2);
        ctx.strokeStyle=`${T.green}${Math.round(alpha*0.5*255).toString(16).padStart(2,"0")}`;
        ctx.lineWidth=0.8; ctx.stroke();
      });

      angle.current = (angle.current + 1.2) % 360;
      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return ()=>cancelAnimationFrame(animRef.current);
  },[blips.length]);

  return <canvas ref={canvasRef} width={160} height={160} style={{borderRadius:"50%",border:`1px solid ${T.border}`}}/>;
}

function TaskCard({ task, onMove, onDragStart, onDragEnd }) {
  const stack = STACKS[stageToStack(task.stage)];
  const [hover, setHover] = useState(false);
  return (
    <div
      draggable
      onDragStart={(e)=>{
        e.dataTransfer.setData("text/plain", task.id);
        e.dataTransfer.effectAllowed = "move";
        onDragStart?.(task.id);
      }}
      onDragEnd={()=>onDragEnd?.()}
      onMouseEnter={()=>setHover(true)}
      onMouseLeave={()=>setHover(false)}
      style={{
        background: hover ? T.surfaceHi : T.surface,
        border:`1px solid ${hover ? stack.color+"60" : T.border}`,
        borderLeft:`3px solid ${stack.color}`,
        borderRadius:6, padding:"8px 10px",
        marginBottom:6, cursor:"grab",
        transition:"all .2s",
        boxShadow: hover ? `0 0 12px ${stack.color}20` : "none",
      }}
    >
      <div style={{display:"flex",alignItems:"flex-start",gap:6,marginBottom:6}}>
        {task.priority==="high" && <span style={{fontSize:8,color:T.red}}>●</span>}
        {task.priority==="critical" && <span style={{fontSize:8,color:T.red}}>◆</span>}
        <span style={{
          fontSize:12,
          color:T.text,
          lineHeight:1.45,
          flex:1,
          overflowWrap:"anywhere",
          wordBreak:"break-word",
        }}>{task.title}</span>
      </div>
      <div style={{display:"flex",gap:4,alignItems:"center",flexWrap:"wrap"}}>
        <Pill color={stack.color} sm>{stack.icon} {stack.id}</Pill>
        <Pill color={T.textDim} sm>{task.task_code || task.id}</Pill>
        <span style={{fontSize:8,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",marginLeft:"auto"}}>{fmtAge(new Date(task.updated))}</span>
      </div>
    </div>
  );
}

function KanbanColumn({ stage, tasks, onMove, onDropTask, onDragStage, isDropTarget, draggingTaskId, onTaskDragStart, onTaskDragEnd }) {
  const count = tasks.length;
  return (
    <div style={{
      display:"flex", flexDirection:"column",
      background:T.bgAlt, borderRadius:8,
      border:`1px solid ${isDropTarget ? stage.color : T.border}`,
      overflow:"hidden",
      maxHeight:"min(52vh, 460px)",
      boxShadow: isDropTarget ? `0 0 0 1px ${stage.color} inset` : "none",
    }}>
      {/* Column header */}
      <div style={{
        padding:"10px 12px", borderBottom:`1px solid ${T.border}`,
        background:`${stage.color}0d`,
        display:"flex",alignItems:"center",gap:6,
      }}>
        <span style={{color:stage.color,fontSize:13}}>{stage.icon}</span>
        <span style={{
          fontFamily:"'IBM Plex Mono',monospace",fontSize:10,fontWeight:700,
          color:stage.color,letterSpacing:"0.1em",
        }}>{stage.label}</span>
        <span style={{
          marginLeft:"auto",background:`${stage.color}25`,color:stage.color,
          borderRadius:10,padding:"1px 7px",fontSize:9,fontWeight:700,
          fontFamily:"'IBM Plex Mono',monospace",
        }}>{count}</span>
      </div>
      <div
        style={{flex:1,overflowY:"auto",padding:"8px",minHeight:0}}
        onDragOver={(e)=>{
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          onDragStage?.(stage.id);
        }}
        onDrop={(e)=>{
          e.preventDefault();
          const taskId = e.dataTransfer.getData("text/plain") || draggingTaskId;
          if (taskId) {
            onDropTask?.(taskId, stage.id);
          }
        }}
      >
        {tasks.map(t=><TaskCard key={t.id} task={t} onMove={onMove} onDragStart={(taskId)=>{
          onTaskDragStart?.(taskId);
          onDragStage?.(stage.id);
        }} onDragEnd={()=>{
          onTaskDragEnd?.();
          onDragStage?.(null);
        }} />)}
        {count===0 && (
          <div style={{textAlign:"center",padding:"20px 0",fontSize:9,color:T.textFaint,fontFamily:"'IBM Plex Mono',monospace"}}>
            — empty —
          </div>
        )}
      </div>
    </div>
  );
}

function StackLane({ stack, tasks, onMove }) {
  const s = STACKS[stack];
  const active = tasks.filter(t=>t.stage==="active");
  const queued = tasks.filter(t=>t.stage==="backlog");
  return (
    <div style={{
      background:T.surface,border:`1px solid ${T.border}`,
      borderTop:`2px solid ${s.color}`,
      borderRadius:8,padding:"12px 14px",
    }}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
        <span style={{fontSize:16,color:s.color}}>{s.icon}</span>
        <div>
          <div style={{fontFamily:"'IBM Plex Mono',monospace",fontSize:12,fontWeight:700,color:s.color}}>{s.label}</div>
          <div style={{fontSize:9,color:T.textDim}}>{s.role}</div>
        </div>
        <div style={{marginLeft:"auto",textAlign:"right"}}>
          <div style={{fontSize:9,color:T.textDim}}>model</div>
          <div style={{fontSize:9,color:T.text,fontFamily:"'IBM Plex Mono',monospace"}}>{s.model}</div>
        </div>
      </div>

      {/* Runway visualization — like planes in line */}
      <div style={{marginBottom:8}}>
        <div style={{fontSize:8,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",marginBottom:4,letterSpacing:"0.08em"}}>
          ══ RUNWAY ({queued.length} queued)
        </div>
        <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
          {queued.length===0 && <span style={{fontSize:8,color:T.textFaint}}>clear</span>}
          {queued.map((t,i)=>(
            <div key={t.id} title={t.title} style={{
              width:28,height:18,borderRadius:3,
              background:`${s.color}20`,border:`1px solid ${s.color}50`,
              display:"flex",alignItems:"center",justifyContent:"center",
              fontSize:7,color:s.color,fontFamily:"'IBM Plex Mono',monospace",
              position:"relative",
            }}>
              {i+1}
              {t.priority==="high" && <span style={{position:"absolute",top:-3,right:-3,fontSize:6,color:T.red}}>●</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Active */}
      {active.map(t=>(
        <div key={t.id} style={{
          background:`${s.color}12`,border:`1px solid ${s.color}40`,
          borderRadius:5,padding:"5px 8px",fontSize:9,
          fontFamily:"'IBM Plex Mono',monospace",color:T.text,
          borderLeft:`3px solid ${s.color}`,
          animation:"breathe 2s ease-in-out infinite",
          marginBottom:4,
        }}>
          <span style={{color:s.color}}>↑ </span>{t.title}
        </div>
      ))}

      <Bar v={tasks.filter(t=>t.stage==="done").length} max={Math.max(6,tasks.length)} color={s.color}/>
      <div style={{fontSize:8,color:T.textDim,marginTop:3,fontFamily:"'IBM Plex Mono',monospace"}}>
        {tasks.filter(t=>t.stage==="done").length} done / {tasks.length} total
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────
export default function RadarRunwayDashboard() {
  const [tasks, setTasks]         = useState([]);
  const [logs,  setLogs]          = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [draggingTaskId, setDraggingTaskId] = useState(null);
  const [dragTargetStage, setDragTargetStage] = useState(null);
  const [copied,setCopied]        = useState(false);
  const [view,  setView]          = useState("kanban"); // kanban | stacks
  const [obSync,setObSync]        = useState(false);
  const [showMd,setShowMd]        = useState(false);
  const [mdContent,setMdContent]  = useState("");
  const logRef = useRef(null);

  const API_BASE = "http://localhost:8000";

  const addLog = useCallback((msg)=>{
    setLogs(l=>[...l,{id:Date.now()+Math.random(),src:"system",msg,ts:new Date()}].slice(-200));
  },[]);

  const fetchMd = useCallback(()=>{
    return fetch(`${API_BASE}/export/obsidian`).then(r=>r.text()).then(text=>{
      setMdContent(text);
      return text;
    });
  },[]);

  const fetchTasks = useCallback(()=>{
    return fetch(`${API_BASE}/tasks/`)
      .then(r => r.json())
      .then((items)=>{
        const mapped = (items || []).map((t)=>({
          ...t,
          stage: STATUS_TO_STAGE[t.status] || "inbox",
        }));
        setTasks(mapped);
      })
      .catch(()=>addLog("Failed to fetch tasks from /tasks"));
  },[addLog]);

  const fetchSyncStatus = useCallback(()=>{
    return fetch(`${API_BASE}/sync/status`)
      .then(r => r.json())
      .then(setSyncStatus)
      .catch(()=>{
        setSyncStatus({
          vault_exists: false,
          parse_error: "Could not load /sync/status",
          vault_path: "(unknown)",
          db_task_count: 0,
        });
      });
  },[]);

  const moveTask = useCallback((id,newStage)=>{
    const newStatus = STAGE_TO_STATUS[newStage] || "radar";
    fetch(`${API_BASE}/tasks/${id}/move?status=${newStatus}`,{
      method:"POST",
    })
      .then(()=>fetchTasks())
      .catch(()=>addLog(`Failed to move ${id} → ${newStage}`));
  },[addLog, fetchTasks]);

  useEffect(()=>{
    fetchTasks();
    fetchSyncStatus();

    const intervalId = setInterval(()=>{
      fetchTasks();
      fetchSyncStatus();
    }, 5000);

    return ()=>clearInterval(intervalId);
  },[fetchTasks, fetchSyncStatus]);

  useEffect(()=>{ logRef.current?.scrollTo({top:logRef.current.scrollHeight,behavior:"smooth"}); },[logs]);

  const copyMd = ()=>{
    fetchMd().then(text=>{
      navigator.clipboard.writeText(text).then(()=>{
        setCopied(true); setTimeout(()=>setCopied(false),2000);
      });
    });
  };

  const srcColor = {manager:T.amber, analyzer:T.teal, coder:T.green, system:T.textDim};
  const srcLabel = {manager:"MNGR", analyzer:"ANLZ", coder:"CODE", system:"SYS "};

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=Epilogue:wght@400;600;800;900&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        :root{color-scheme:dark}
        body{background:${T.bg};color:${T.text};font-family:'Epilogue',sans-serif;overflow-x:hidden}
        ::-webkit-scrollbar{width:3px;height:3px}
        ::-webkit-scrollbar-track{background:${T.bg}}
        ::-webkit-scrollbar-thumb{background:${T.borderHi};border-radius:2px}
        @keyframes breathe{0%,100%{opacity:1}50%{opacity:.55}}
        @keyframes slideIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
        @keyframes sweep{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
        @keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
        @keyframes pulse{0%,100%{box-shadow:0 0 0 0 ${T.amber}40}70%{box-shadow:0 0 0 6px ${T.amber}00}}
      `}</style>

      <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",padding:14,gap:10,background:`radial-gradient(ellipse at 20% 0%,${T.amber}08 0%,transparent 50%),${T.bg}`}}>

        {/* ── HEADER ── */}
        <div style={{display:"flex",alignItems:"center",gap:12,borderBottom:`1px solid ${T.border}`,paddingBottom:10}}>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <div style={{
              width:32,height:32,borderRadius:"50%",
              border:`1.5px solid ${T.amber}`,
              display:"flex",alignItems:"center",justifyContent:"center",
              background:`${T.amber}15`,animation:"pulse 2.5s infinite",
            }}>
              <span style={{fontSize:14,color:T.amber}}>⊙</span>
            </div>
            <div>
              <div style={{fontFamily:"'Epilogue',sans-serif",fontWeight:900,fontSize:17,letterSpacing:"-0.03em",color:T.white}}>
                RADAR<span style={{color:T.amber}}>·</span>RUNWAY
              </div>
              <div style={{fontSize:8,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.15em"}}>
                3-STACK ORCHESTRATOR · OBSIDIAN SYNC
              </div>
            </div>
          </div>

          {/* Stack status pills */}
          <div style={{display:"flex",gap:6}}>
            {Object.values(STACKS).map(s=>{
              const active=tasks.filter(t=>stageToStack(t.stage)===s.id&&t.stage==="active").length;
              return (
                <div key={s.id} style={{
                  display:"flex",alignItems:"center",gap:5,padding:"4px 10px",
                  background:`${s.color}12`,border:`1px solid ${s.color}35`,borderRadius:6,
                }}>
                  <span style={{color:s.color,fontSize:12}}>{s.icon}</span>
                  <span style={{fontSize:9,color:s.color,fontFamily:"'IBM Plex Mono',monospace",fontWeight:700}}>{s.label}</span>
                  {active>0 && <span style={{
                    width:6,height:6,borderRadius:"50%",background:s.color,
                    animation:"breathe 1.2s ease-in-out infinite",
                  }}/>}
                </div>
              );
            })}
          </div>

          <div style={{marginLeft:"auto",display:"flex",gap:6,alignItems:"center"}}>
            {/* Obsidian sync button */}
            <button style={{
              padding:"5px 12px",borderRadius:6,cursor:"pointer",
              background: obSync ? `${T.purple}25` : T.surface,
              border:`1px solid ${obSync ? T.purple : T.borderHi}`,
              color: obSync ? T.purple : T.textDim,
              fontSize:9,fontFamily:"'IBM Plex Mono',monospace",
              display:"flex",alignItems:"center",gap:6,transition:"all .3s",
            }} onClick={()=>{ setShowMd(s=>!s); fetchMd(); }}>
              <span style={{fontSize:11}}>◈</span>
              {obSync ? "SYNCING…" : "OBSIDIAN MD"}
            </button>
            <button onClick={copyMd} style={{
              padding:"5px 12px",borderRadius:6,cursor:"pointer",
              background: copied ? `${T.green}20` : T.surface,
              border:`1px solid ${copied ? T.green : T.borderHi}`,
              color: copied ? T.green : T.textDim,
              fontSize:9,fontFamily:"'IBM Plex Mono',monospace",
            }}>
              {copied ? "✓ COPIED" : "⎘ COPY MD"}
            </button>
            <button onClick={()=>{
              setObSync(true);
              fetch(`${API_BASE}/sync`,{method:"POST"}).finally(()=>{
                setTimeout(()=>setObSync(false),1200);
              });
            }} style={{
              padding:"5px 12px",borderRadius:6,cursor:"pointer",
              background: `${T.blue}15`,
              border:`1px solid ${T.blue}`,
              color:T.blue,
              fontSize:9,fontFamily:"'IBM Plex Mono',monospace",
            }}>⟲ SYNC</button>
            {/* View toggle */}
            <div style={{display:"flex",borderRadius:6,overflow:"hidden",border:`1px solid ${T.borderHi}`}}>
              {["kanban","stacks"].map(v=>(
                <button key={v} onClick={()=>setView(v)} style={{
                  padding:"5px 12px",border:"none",cursor:"pointer",
                  background:view===v?`${T.amber}20`:T.surface,
                  color:view===v?T.amber:T.textDim,
                  fontSize:9,fontFamily:"'IBM Plex Mono',monospace",fontWeight:700,
                  letterSpacing:"0.08em",
                }}>{v.toUpperCase()}</button>
              ))}
            </div>
          </div>
        </div>

        {/* ── MAIN CONTENT ── */}
        <div style={{display:"grid",gridTemplateColumns:"1fr",gap:10,flex:1}}>

          {/* Left: main view */}
          <div style={{display:"flex",flexDirection:"column",gap:10}}>
            {syncStatus && !syncStatus.vault_exists && (
              <div style={{
                border:`1px solid ${T.red}`,
                background:`${T.red}12`,
                color:T.red,
                borderRadius:8,
                padding:"10px 12px",
                fontSize:11,
                fontFamily:"'IBM Plex Mono',monospace",
              }}>
                ⚠ Kanban file not found: {syncStatus.vault_path}
              </div>
            )}

            {syncStatus?.parse_error && (
              <div style={{
                border:`1px solid ${T.red}`,
                background:`${T.red}12`,
                color:T.red,
                borderRadius:8,
                padding:"10px 12px",
                fontSize:11,
                fontFamily:"'IBM Plex Mono',monospace",
              }}>
                ⚠ Failed to parse TODO.md: {syncStatus.parse_error}
              </div>
            )}

            {syncStatus?.vault_exists && tasks.length===0 && (
              <div style={{
                border:`1px solid ${T.amber}`,
                background:`${T.amber}12`,
                color:T.amber,
                borderRadius:8,
                padding:"10px 12px",
                fontSize:11,
                fontFamily:"'IBM Plex Mono',monospace",
              }}>
                ⚠ No tasks found in TODO.md ({syncStatus.vault_path}). Add task lines like: - [ ] My task
              </div>
            )}

            {view==="kanban" && (
              <div style={{
                background:T.bgAlt,borderRadius:10,border:`1px solid ${T.border}`,
                padding:12,overflow:"hidden",
                display:"flex",flexDirection:"column",
              }}>
                <div style={{fontSize:9,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.1em",marginBottom:10,display:"flex",alignItems:"center",gap:8}}>
                  <span style={{color:T.amber}}>◈</span> KANBAN BOARD
                  <span style={{color:T.textFaint}}>— hover card to move stage —</span>
                  <span style={{marginLeft:"auto",color:T.purple,fontSize:8}}>syncs to Obsidian Work/TODO.md</span>
                </div>
                <div style={{
                  display:"grid",
                  gridTemplateColumns:`repeat(${STAGES.length}, minmax(0, 1fr))`,
                  gap:8,
                  paddingBottom:4,
                  alignItems:"stretch",
                  flex:1,
                  minHeight:0,
                }}>
                  {STAGES.map(s=>(
                    <KanbanColumn
                      key={s.id}
                      stage={s}
                      tasks={tasks.filter(t=>t.stage===s.id)}
                      onMove={moveTask}
                      draggingTaskId={draggingTaskId}
                      isDropTarget={dragTargetStage===s.id}
                      onDragStage={(stageId)=>setDragTargetStage(stageId)}
                      onTaskDragStart={(taskId)=>setDraggingTaskId(taskId)}
                      onTaskDragEnd={()=>setDraggingTaskId(null)}
                      onDropTask={(taskId, stageId)=>{
                        const task = tasks.find(t=>t.id===taskId);
                        if (task && task.stage !== stageId) {
                          moveTask(taskId, stageId);
                        }
                        setDraggingTaskId(null);
                        setDragTargetStage(null);
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {view==="stacks" && (
              <div style={{
                background:T.bgAlt,borderRadius:10,border:`1px solid ${T.border}`,padding:12,
              }}>
                <div style={{fontSize:9,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.1em",marginBottom:10}}>
                  <span style={{color:T.amber}}>◈</span> STACK RUNWAYS
                </div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:10}}>
                  {Object.keys(STACKS).map(k=>(
                    <StackLane key={k} stack={k} tasks={tasks.filter(t=>stageToStack(t.stage)===k)} onMove={moveTask}/>
                  ))}
                </div>
                {/* Flow diagram */}
                <div style={{
                  marginTop:10,padding:"10px 14px",
                  background:T.surface,borderRadius:8,border:`1px solid ${T.border}`,
                  fontFamily:"'IBM Plex Mono',monospace",fontSize:10,color:T.textDim,
                  display:"flex",alignItems:"center",justifyContent:"center",gap:8,flexWrap:"wrap",
                }}>
                  <span style={{color:T.amber}}>◎ MANAGER</span>
                  <span>researches & decomposes</span>
                  <span style={{color:T.amber}}>→</span>
                  <span style={{color:T.teal}}>◈ ANALYZER</span>
                  <span>traces & root-causes</span>
                  <span style={{color:T.teal}}>→</span>
                  <span style={{color:T.green}}>◇ CODER</span>
                  <span>implements & ships</span>
                  <span style={{color:T.amber}}>→ feedback loop ↺</span>
                </div>
              </div>
            )}

            {/* Obsidian MD preview */}
            {showMd && (
              <div style={{
                background:T.surface,border:`1px solid ${T.purple}40`,
                borderRadius:10,padding:12,animation:"slideIn .2s ease",
              }}>
                <div style={{fontSize:9,color:T.purple,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.1em",marginBottom:8,display:"flex",alignItems:"center",gap:8}}>
                  <span>◈ OBSIDIAN kanban.md PREVIEW</span>
                  <span style={{color:T.textDim}}>— paste into your vault</span>
                  <button onClick={copyMd} style={{
                    marginLeft:"auto",padding:"2px 8px",borderRadius:4,cursor:"pointer",
                    background:`${T.purple}20`,border:`1px solid ${T.purple}40`,color:T.purple,
                    fontSize:8,fontFamily:"'IBM Plex Mono',monospace",
                  }}>{copied?"✓ COPIED":"⎘ COPY"}</button>
                </div>
                <pre style={{
                  fontSize:9.5,color:T.text,fontFamily:"'IBM Plex Mono',monospace",
                  overflowX:"auto",whiteSpace:"pre",lineHeight:1.6,
                  maxHeight:220,overflowY:"auto",
                }}>{mdContent}</pre>
              </div>
            )}

            {/* Stack breakdown: inbox + analysis detail */}
            <div style={{
              display:"grid",gridTemplateColumns:"160px 1fr",gap:10,
            }}>
              {/* Radar */}
              <div style={{
                background:T.surface,border:`1px solid ${T.border}`,
                borderRadius:10,padding:12,display:"flex",flexDirection:"column",alignItems:"center",gap:8,
              }}>
                <div style={{fontSize:9,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.1em"}}>⊙ RADAR SWEEP</div>
                <RadarSweep tasks={tasks}/>
                <div style={{fontSize:8,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",textAlign:"center"}}>
                  {tasks.filter(t=>t.stage==="inbox").length} signals detected
                </div>
              </div>

              {/* Manager analysis queue */}
              <div style={{
                background:T.surface,border:`1px solid ${T.border}`,
                borderRadius:10,padding:"10px 12px",
              }}>
                <div style={{fontSize:9,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.1em",marginBottom:8}}>
                  <span style={{color:T.amber}}>◎</span> MANAGER — ANALYSIS QUEUE
                  <span style={{marginLeft:6,color:T.textFaint,fontSize:8}}>(decomposing into subtasks)</span>
                </div>
                {tasks.filter(t=>t.stage==="analysis").map(t=>(
                  <div key={t.id} style={{
                    display:"flex",alignItems:"center",gap:8,padding:"5px 8px",
                    borderLeft:`2px solid ${T.amber}`,marginBottom:5,
                    background:`${T.amber}08`,borderRadius:"0 4px 4px 0",
                  }}>
                    <span style={{
                      fontSize:9,fontFamily:"'IBM Plex Mono',monospace",color:T.amber,
                      animation:"blink 1.4s ease-in-out infinite",
                    }}>◎</span>
                    <span style={{fontSize:10,color:T.text,flex:1}}>{t.title}</span>
                    {t.priority==="high" && <Pill color={T.red} sm>HIGH</Pill>}
                    <button onClick={()=>moveTask(t.id,"backlog")} style={{
                      fontSize:8,padding:"2px 7px",borderRadius:3,cursor:"pointer",
                      background:`${T.green}15`,border:`1px solid ${T.green}40`,color:T.green,
                      fontFamily:"'IBM Plex Mono',monospace",
                    }}>→ backlog</button>
                  </div>
                ))}
                {tasks.filter(t=>t.stage==="analysis").length===0 && (
                  <div style={{fontSize:9,color:T.textFaint,fontFamily:"'IBM Plex Mono',monospace",padding:"8px 0"}}>— analysis queue empty —</div>
                )}
              </div>
            </div>
          </div>

          {/* ── Right: Log panel ── */}
          <div style={{display:"flex",flexDirection:"column",gap:10}}>

            {/* Live log */}
            <div style={{
              background:T.surface,border:`1px solid ${T.border}`,
              borderRadius:10,overflow:"hidden",flex:1,display:"flex",flexDirection:"column",
            }}>
              <div style={{
                padding:"9px 12px",borderBottom:`1px solid ${T.border}`,
                display:"flex",alignItems:"center",gap:6,flexShrink:0,
              }}>
                <span style={{width:6,height:6,borderRadius:"50%",background:T.green,animation:"breathe 1s infinite",display:"block"}}/>
                <span style={{fontSize:9,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",letterSpacing:"0.1em"}}>LIVE LOG</span>
                <span style={{marginLeft:"auto",fontSize:8,color:T.textFaint,fontFamily:"'IBM Plex Mono',monospace"}}>{logs.length} entries</span>
              </div>
              <div ref={logRef} style={{flex:1,overflowY:"auto",padding:"8px 10px",minHeight:300,maxHeight:420}}>
                {logs.map(l=>(
                  <div key={l.id} style={{
                    display:"flex",gap:6,padding:"2.5px 0",
                    animation:"slideIn .2s ease",
                    borderBottom:`1px solid ${T.textFaint}`,
                  }}>
                    <span style={{fontSize:8,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",flexShrink:0,lineHeight:1.8}}>{fmtTime(l.ts)}</span>
                    <span style={{
                      fontSize:8,color:srcColor[l.src]||T.textDim,
                      fontFamily:"'IBM Plex Mono',monospace",fontWeight:700,
                      flexShrink:0,width:30,lineHeight:1.8,
                    }}>{srcLabel[l.src]||"SYS "}</span>
                    <span style={{fontSize:9.5,color:T.text,lineHeight:1.6}}>{l.msg}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Obsidian integration tip */}
            <div style={{
              background:`${T.purple}10`,border:`1px solid ${T.purple}30`,
              borderRadius:10,padding:"10px 12px",
            }}>
              <div style={{fontSize:9,color:T.purple,fontFamily:"'IBM Plex Mono',monospace",fontWeight:700,marginBottom:6}}>◈ OBSIDIAN INTEGRATION</div>
              {[
                "Copy MD → paste into vault/kanban.md",
                "Enable Kanban plugin in Obsidian",
                "Use Dataview for cross-stack queries",
                "Tag format: #stack/stage for filters",
                "Watch file with orchestrator for auto-sync",
              ].map((tip,i)=>(
                <div key={i} style={{
                  fontSize:8.5,color:T.textDim,fontFamily:"'IBM Plex Mono',monospace",
                  padding:"2px 0",display:"flex",gap:6,
                }}>
                  <span style={{color:T.purple}}>·</span>{tip}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
