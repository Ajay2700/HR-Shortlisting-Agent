/**
 * HR Shortlisting Agent — React Frontend
 * Industry-grade UI with toast notifications, form validation,
 * sample data demo, score override panel, and structured error display.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";

/* ── Error code → user-friendly messages ─────────────────────── */
const ERROR_MESSAGES = {
  CONFIG_ERROR:
    "Server configuration issue: the Google API key is missing or invalid. Contact your administrator.",
  VALIDATION_ERROR: null,          // use message from server directly
  PARSE_ERROR:
    "Could not read one of your uploaded files. Make sure it is a valid, non-password-protected PDF, DOCX, or JSON.",
  QUOTA_EXCEEDED:
    "Your Gemini API free-tier quota is exhausted. The pipeline ran using the offline fallback scorer. Results are heuristic — add billing at aistudio.google.com for full AI scoring.",
  PIPELINE_ERROR:
    "The AI pipeline encountered an unexpected error. Check that your files contain valid content and try again.",
  NOT_FOUND: "The requested resource was not found on the server.",
};

const REC_META = {
  "STRONG HIRE": { color: "#00e5b0", bg: "rgba(0,229,176,0.12)", icon: "🏆" },
  "HIRE":        { color: "#60c4ff", bg: "rgba(96,196,255,0.12)", icon: "✅" },
  "MAYBE":       { color: "#ffcc55", bg: "rgba(255,204,85,0.12)",  icon: "🤔" },
  "NO HIRE":     { color: "#ff6b7c", bg: "rgba(255,107,124,0.12)", icon: "❌" },
};

const DIM_ICONS = {
  "Skills Match": "⚡",
  "Experience Relevance": "📈",
  "Education & Certifications": "🎓",
  "Project / Portfolio": "🚀",
  "Communication Quality": "💬",
};

const PIPE_STEPS = ["JD Parsing", "Profile Extraction", "AI Scoring", "Ranking", "Report Ready"];

/* ══════════════════════════════════════════════════════════
   Toast System
══════════════════════════════════════════════════════════ */
let _toastId = 0;
let _addToast = () => {};

export function useToast() {
  return { toast: _addToast };
}

function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    _addToast = (message, type = "info", duration = 5000) => {
      const id = ++_toastId;
      setToasts((prev) => [...prev, { id, message, type }]);
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration);
    };
    return () => { _addToast = () => {}; };
  }, []);

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span className="toast-icon">
            {{ success: "✓", error: "✕", warning: "⚠", info: "ℹ" }[t.type] || "ℹ"}
          </span>
          <span>{t.message}</span>
          <button className="toast-close" onClick={() =>
            setToasts((p) => p.filter((x) => x.id !== t.id))}>×</button>
        </div>
      ))}
    </div>
  );
}

/* ── Animated score ring ──────────────────────────────────────── */
function ScoreRing({ score, size = 88, stroke = 8 }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct  = (score / 10) * circ;
  const [dash, setDash] = useState(0);
  useEffect(() => { const t = setTimeout(() => setDash(pct), 80); return () => clearTimeout(t); }, [pct]);
  const meta = score >= 8 ? REC_META["STRONG HIRE"] : score >= 6.5 ? REC_META["HIRE"] : score >= 4.5 ? REC_META["MAYBE"] : REC_META["NO HIRE"];
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)", flexShrink: 0 }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={stroke}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={meta.color} strokeWidth={stroke}
        strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ - dash}
        style={{ transition:"stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)" }}/>
      <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle"
        fill={meta.color} fontSize={size*0.2} fontWeight="700"
        style={{ transform:"rotate(90deg)", transformOrigin:"50% 50%" }}>
        {score.toFixed(1)}
      </text>
    </svg>
  );
}

/* ── Animated score bar ───────────────────────────────────────── */
function ScoreBar({ value, color }) {
  const [w, setW] = useState(0);
  useEffect(() => { const t = setTimeout(() => setW((value/10)*100), 80); return () => clearTimeout(t); }, [value]);
  return (
    <div className="sbar-track">
      <div className="sbar-fill" style={{ width:`${w}%`, background: color || "var(--accent)" }}/>
    </div>
  );
}

/* ── Stat card with counter ───────────────────────────────────── */
function StatCard({ value, label, icon, color }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const end = parseFloat(value) || 0;
    if (!end) return setV(0);
    const dur = 900, step = (end / dur) * 16;
    let cur = 0;
    const t = setInterval(() => { cur = Math.min(cur + step, end); setV(cur); if (cur >= end) clearInterval(t); }, 16);
    return () => clearInterval(t);
  }, [value]);
  const isInt = Number.isInteger(Number(value));
  return (
    <div className="stat-card" style={{ "--sc": color||"var(--accent)" }}>
      <div className="sc-icon">{icon}</div>
      <div className="sc-value">{isInt ? Math.round(v) : v.toFixed(2)}</div>
      <div className="sc-label">{label}</div>
    </div>
  );
}

/* ── Drop zone ────────────────────────────────────────────────── */
function DropZone({ label, accept, multiple, icon, files, onChange, error }) {
  const ref = useRef();
  const [over, setOver] = useState(false);
  const onDrop = (e) => {
    e.preventDefault(); setOver(false);
    onChange(multiple ? Array.from(e.dataTransfer.files) : [e.dataTransfer.files[0]]);
  };
  return (
    <div className={`dropzone${over?" over":""}${files.length?" has-files":""}${error?" dz-error":""}`}
      onDragOver={(e)=>{e.preventDefault();setOver(true);}} onDragLeave={()=>setOver(false)}
      onDrop={onDrop} onClick={()=>ref.current.click()}>
      <input ref={ref} type="file" accept={accept} multiple={multiple} style={{display:"none"}}
        onChange={(e)=>onChange(Array.from(e.target.files||[]))}/>
      <span className="dz-icon">{icon}</span>
      <span className="dz-label">{files.length ? `${files.length} file${files.length>1?"s":""} selected` : label}</span>
      {files.length > 0 && (
        <ul className="dz-files">
          {files.map((f,i) => <li key={i}>{f.name}</li>)}
        </ul>
      )}
      {error && <span className="dz-err-msg">{error}</span>}
    </div>
  );
}

/* ── Pipeline stepper ─────────────────────────────────────────── */
function PipelineProgress({ step }) {
  return (
    <div className="pipeline">
      {PIPE_STEPS.map((label, i) => (
        <div key={i} className={`pipe-step${i<step?" done":""}${i===step?" active":""}`}>
          <div className="pipe-dot">{i < step ? "✓" : i+1}</div>
          <div className="pipe-label">{label}</div>
          {i < PIPE_STEPS.length-1 && <div className="pipe-line"/>}
        </div>
      ))}
    </div>
  );
}

/* ── Error banner ─────────────────────────────────────────────── */
function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  const code    = error.code || "PIPELINE_ERROR";
  const human   = ERROR_MESSAGES[code] || error.message;
  const isQuota = code === "QUOTA_EXCEEDED";
  return (
    <div className={`error-banner${isQuota?" warn-banner":""}`}>
      <div className="eb-header">
        <span className="eb-icon">{isQuota ? "⚠️" : "❌"}</span>
        <span className="eb-code">{code}</span>
        {onRetry && <button className="eb-retry" onClick={onRetry}>↺ Retry</button>}
      </div>
      <p className="eb-msg">{human}</p>
      {error.details && !isQuota && (
        <details className="eb-details">
          <summary>Technical details</summary>
          <pre>{error.details}</pre>
        </details>
      )}
    </div>
  );
}

/* ── Candidate card ───────────────────────────────────────────── */
function CandidateCard({ s, rank, expanded, onToggle, onOverride }) {
  const rec  = s.recommendation || "MAYBE";
  const meta = REC_META[rec] || REC_META["MAYBE"];
  const dims = [
    { key:"skills_match",           label:"Skills Match" },
    { key:"experience_relevance",   label:"Experience Relevance" },
    { key:"education_certs",        label:"Education & Certifications" },
    { key:"project_portfolio",      label:"Project / Portfolio" },
    { key:"communication_quality",  label:"Communication Quality" },
  ];
  return (
    <div className={`ccard${expanded?" open":""}`} style={{"--rec-color": meta.color}}>
      <div className="ccard-top" onClick={onToggle}>
        <div className="ccard-rank">#{rank}</div>
        <div className="ccard-ring"><ScoreRing score={s.total_weighted_score||0}/></div>
        <div className="ccard-info">
          <div className="ccard-name">
            {s.candidate_name}
            {s.is_overridden && <span className="override-tag">✏ Overridden</span>}
          </div>
          <div className="ccard-source">{s.candidate_source} · {s.source_file}</div>
          <div className="ccard-preview">{(s.overall_summary||"").slice(0,90)}…</div>
        </div>
        <span className="badge" style={{ background:meta.bg, color:meta.color }}>
          {meta.icon} {rec}
        </span>
        <span className="chevron">{expanded?"▲":"▼"}</span>
      </div>

      {expanded && (
        <div className="ccard-body">
          {s.is_overridden && (
            <div className="override-notice">
              ✏ Score overridden from <b>{s.original_score?.toFixed(2)}</b> → <b>{s.total_weighted_score.toFixed(2)}</b>
              {s.override_reason && <> · Reason: <i>{s.override_reason}</i></>}
            </div>
          )}
          <p className="ccard-summary">{s.overall_summary}</p>

          <div className="dim-grid">
            {dims.map(({ key, label }) => {
              const d   = s[key] || {};
              const raw = d.raw_score ?? 0;
              const col = raw >= 7 ? "#00e5b0" : raw >= 5 ? "#60c4ff" : "#ff6b7c";
              return (
                <div key={key} className="dim-row">
                  <div className="dim-header">
                    <span>{DIM_ICONS[label]||"•"} {label} <span className="dim-weight">({(d.weight||0)*100|0}%)</span></span>
                    <span className="dim-score">{raw.toFixed(1)}/10 · weighted {(d.weighted_score||0).toFixed(2)}</span>
                  </div>
                  <ScoreBar value={raw} color={col}/>
                  <div className="dim-just">{d.justification||"—"}</div>
                  {(d.evidence||[]).length > 0 && (
                    <div className="dim-evidence">
                      {d.evidence.slice(0,5).map((ev,i) => (
                        <span key={i} className="ev-tag">{ev}</span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {s.embedding_similarity != null && (
            <div className="embed-sim">
              🔗 Semantic similarity: <b>{(s.embedding_similarity*100).toFixed(1)}%</b>
            </div>
          )}

          <button className="override-btn" onClick={(e)=>{e.stopPropagation();onOverride(s);}}>
            ✏ Override Score
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Score Override Modal ─────────────────────────────────────── */
function OverrideModal({ candidate, scores, onClose, onApplied }) {
  const [newScore, setNewScore]  = useState(candidate.total_weighted_score.toFixed(1));
  const [reason, setReason]      = useState("");
  const [loading, setLoading]    = useState(false);
  const [err, setErr]            = useState("");

  const projected = parseFloat(newScore) || 0;
  const projRec   = projected >= 8 ? "STRONG HIRE" : projected >= 6.5 ? "HIRE" : projected >= 4.5 ? "MAYBE" : "NO HIRE";
  const recMeta   = REC_META[projRec] || REC_META["MAYBE"];

  const validate = () => {
    if (!reason.trim()) return "Please provide a reason for the override.";
    if (isNaN(projected) || projected < 0 || projected > 10) return "Score must be between 0.0 and 10.0.";
    return null;
  };

  const apply = async () => {
    const e = validate(); if (e) { setErr(e); return; }
    setLoading(true); setErr("");
    try {
      const res  = await fetch(`${API_BASE}/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_name: candidate.candidate_name, new_score: projected, reason, scores }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error?.message || "Override failed");
      _addToast(`Score override applied for ${candidate.candidate_name}`, "success");
      onApplied(data.scores);
    } catch (e) {
      setErr(String(e.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e)=>e.stopPropagation()}>
        <div className="modal-header">
          <h3>✏ Override Score</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="modal-candidate">
            <b>{candidate.candidate_name}</b>
            <span className="badge" style={{ background:REC_META[candidate.recommendation]?.bg, color:REC_META[candidate.recommendation]?.color, marginLeft:10 }}>
              {candidate.recommendation}
            </span>
          </div>

          <label className="field-label">
            Current Score
            <div className="current-score">{candidate.total_weighted_score.toFixed(2)} / 10</div>
          </label>

          <label className="field-label">
            New Score (0.0 – 10.0)
            <input type="range" min="0" max="10" step="0.5" value={newScore}
              onChange={(e)=>setNewScore(e.target.value)} className="score-slider"/>
            <div className="slider-display">
              <span style={{ color: recMeta.color, fontWeight:700, fontSize:28 }}>{parseFloat(newScore).toFixed(1)}</span>
              <span className="badge" style={{ background:recMeta.bg, color:recMeta.color, marginLeft:12 }}>{projRec}</span>
            </div>
          </label>

          <label className="field-label">
            Reason for Override <span className="required">*</span>
            <textarea className="jd-textarea" rows={4} placeholder="e.g. Strong cultural fit demonstrated during phone screen; impressive portfolio not captured in resume..."
              value={reason} onChange={(e)=>setReason(e.target.value)}/>
          </label>

          {err && <div className="field-error">⚠ {err}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="run-btn" style={{width:"auto",padding:"10px 28px"}} disabled={loading} onClick={apply}>
            {loading ? <><span className="spinner"/> Applying…</> : "Apply Override"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Animated particles ───────────────────────────────────────── */
function Particles() {
  const canvasRef = useRef();
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    let W = (canvas.width = window.innerWidth);
    let H = (canvas.height = window.innerHeight);
    const pts = Array.from({length:65}, () => ({
      x:Math.random()*W, y:Math.random()*H,
      vx:(Math.random()-.5)*.4, vy:(Math.random()-.5)*.4,
      r:Math.random()*1.8+.5,
    }));
    let raf;
    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      for (const p of pts) {
        p.x+=p.vx; p.y+=p.vy;
        if(p.x<0)p.x=W; if(p.x>W)p.x=0; if(p.y<0)p.y=H; if(p.y>H)p.y=0;
        ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
        ctx.fillStyle="rgba(130,150,255,0.45)"; ctx.fill();
      }
      for(let i=0;i<pts.length;i++) for(let j=i+1;j<pts.length;j++){
        const dx=pts[i].x-pts[j].x, dy=pts[i].y-pts[j].y, d=Math.hypot(dx,dy);
        if(d<110){ ctx.beginPath(); ctx.moveTo(pts[i].x,pts[i].y); ctx.lineTo(pts[j].x,pts[j].y);
          ctx.strokeStyle=`rgba(130,150,255,${.18*(1-d/110)})`; ctx.lineWidth=.7; ctx.stroke(); }
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    const onResize=()=>{W=canvas.width=window.innerWidth; H=canvas.height=window.innerHeight;};
    window.addEventListener("resize", onResize);
    return ()=>{cancelAnimationFrame(raf); window.removeEventListener("resize",onResize);};
  }, []);
  return <canvas ref={canvasRef} className="particles"/>;
}

/* ── Audit Panel ──────────────────────────────────────────────── */
function AuditPanel() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter,  setFilter]  = useState("ALL");

  useEffect(() => {
    fetch(`${API_BASE}/audit`).then(r=>r.json())
      .then(d=>setEntries(d.entries||[]))
      .catch(()=>_addToast("Could not load audit log — is the API server running?","error"))
      .finally(()=>setLoading(false));
  }, []);

  const actionTypes = ["ALL", ...new Set(entries.map(e=>e.action))];
  const shown = filter==="ALL" ? entries : entries.filter(e=>e.action===filter);
  const icons  = {INFO:"ℹ️",WARNING:"⚠️",ERROR:"❌"};

  if (loading) return <div className="empty-state"><span className="spinner large"/></div>;
  if (!entries.length) return (
    <div className="empty-state">
      <div className="empty-icon">📜</div>
      <h3>No audit entries yet</h3>
      <p>Run the shortlisting agent to generate an audit trail.</p>
    </div>
  );

  return (
    <div>
      <div className="section-title">
        Audit Trail
        <span className="pill pill-blue">{entries.length} entries</span>
        <select className="filter-select" value={filter} onChange={e=>setFilter(e.target.value)}>
          {actionTypes.map(a=><option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      <div className="audit-list">
        {shown.map((e,i)=>(
          <div key={i} className="audit-row">
            <span className="audit-icon">{icons[e.severity]||"📝"}</span>
            <div>
              <div className="audit-action">{e.action}</div>
              <div className="audit-ts">{e.timestamp}</div>
            </div>
            <pre className="audit-detail">{JSON.stringify(e.details,null,2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Main App
══════════════════════════════════════════════════════════ */
export default function App() {
  const [tab,          setTab]          = useState("input");
  const [jdText,       setJdText]       = useState("");
  const [jdFile,       setJdFile]       = useState(null);
  const [resumeFiles,  setResumeFiles]  = useState([]);
  const [linkedinFiles,setLinkedinFiles]= useState([]);
  const [loading,      setLoading]      = useState(false);
  const [pipeStep,     setPipeStep]     = useState(-1);
  const [apiError,     setApiError]     = useState(null);   // structured { code, message, details }
  const [warnings,     setWarnings]     = useState([]);
  const [fallback,     setFallback]     = useState(false);
  const [result,       setResult]       = useState(null);
  const [expanded,     setExpanded]     = useState(null);
  const [overrideTarget, setOverrideTarget] = useState(null);
  const [health,       setHealth]       = useState(null);

  // Form validation state
  const [fieldErrors, setFieldErrors]   = useState({});

  const scores      = result?.candidate_scores || [];
  const shortlisted = useMemo(() => scores.filter(s=>["STRONG HIRE","HIRE"].includes(s.recommendation)), [scores]);
  const avgScore    = scores.length ? scores.reduce((a,s)=>a+(s.total_weighted_score||0),0)/scores.length : 0;

  // ── Health check on mount ──────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r=>r.json()).then(setHealth)
      .catch(()=>setHealth({ok:false, error:"API server not reachable — start api_server.py"}));
  }, []);

  // ── Client-side form validation ────────────────────────────
  const validate = useCallback(() => {
    const errs = {};
    if (!jdText.trim() && !jdFile) errs.jd = "Provide a Job Description — paste text or upload a file.";
    if (!resumeFiles.length && !linkedinFiles.length) errs.candidates = "Upload at least one resume (PDF/DOCX) or LinkedIn JSON.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }, [jdText, jdFile, resumeFiles, linkedinFiles]);

  // ── Run pipeline ───────────────────────────────────────────
  const runPipeline = useCallback(async (useSamples = false) => {
    if (!useSamples && !validate()) return;
    setLoading(true); setApiError(null); setWarnings([]); setFallback(false);
    setResult(null); setPipeStep(0);

    const stepTimer = setInterval(() => setPipeStep(p => Math.min(p+1, 3)), 3500);
    try {
      let url, body;
      if (useSamples) {
        url = `${API_BASE}/samples/run`;
        body = new FormData();
        if (jdText.trim()) body.append("jd_text", jdText);
      } else {
        url = `${API_BASE}/run`;
        body = new FormData();
        if (jdText.trim()) body.append("jd_text", jdText);
        if (jdFile) body.append("jd_file", jdFile);
        resumeFiles.forEach(f => body.append("resume_files", f));
        linkedinFiles.forEach(f => body.append("linkedin_files", f));
      }

      const res  = await fetch(url, { method:"POST", body });
      const data = await res.json();

      clearInterval(stepTimer);

      if (!data.ok) {
        setApiError(data.error);
        setPipeStep(-1);
        if (data.error?.code === "QUOTA_EXCEEDED") {
          _addToast("API quota exhausted — pipeline ran in fallback mode", "warning", 8000);
        } else {
          _addToast(data.error?.message || "Pipeline failed", "error");
        }
        return;
      }

      setPipeStep(4);
      setResult(data.result);
      setWarnings(data.warnings || []);
      setFallback(data.fallback_mode || false);

      if (data.fallback_mode) {
        _addToast("Heuristic fallback mode — AI quota exhausted, scores are estimated", "warning", 7000);
      } else {
        _addToast(`Pipeline complete — ${data.candidates_scored} candidates scored`, "success");
      }
      setTab("results");
    } catch (e) {
      clearInterval(stepTimer);
      setApiError({ code:"PIPELINE_ERROR", message: "Could not reach the API server.", details: String(e) });
      _addToast("Cannot connect to the API server — make sure it is running on port 8000", "error", 8000);
      setPipeStep(-1);
    } finally {
      setLoading(false);
    }
  }, [jdText, jdFile, resumeFiles, linkedinFiles, validate]);

  // ── Load sample JD ─────────────────────────────────────────
  const loadSampleJD = async () => {
    try {
      const data = await fetch(`${API_BASE}/samples/jd`).then(r=>r.json());
      if (data.ok) { setJdText(data.jd_text); _addToast("Sample JD loaded", "success"); }
      else _addToast(data.error?.message || "Could not load sample JD", "error");
    } catch { _addToast("Could not reach API to load sample JD", "error"); }
  };

  // ── Override applied ────────────────────────────────────────
  const handleOverrideApplied = (newScores) => {
    setResult(prev => ({ ...prev, candidate_scores: newScores }));
    setOverrideTarget(null);
    setExpanded(null);
  };

  const canRun = (jdText.trim() || jdFile) && (resumeFiles.length || linkedinFiles.length);

  return (
    <div className="root">
      <Particles/>
      <ToastContainer/>
      {overrideTarget && (
        <OverrideModal
          candidate={overrideTarget}
          scores={scores}
          onClose={() => setOverrideTarget(null)}
          onApplied={handleOverrideApplied}
        />
      )}

      {/* ── NAVBAR ── */}
      <nav className="navbar">
        <div className="nav-brand">
          <span className="nav-logo">🎯</span>
          <span>HR<b>Agent</b></span>
        </div>
        <div className="nav-tabs">
          {["input","results","audit"].map(t=>(
            <button key={t} className={`nav-tab${tab===t?" active":""}`} onClick={()=>setTab(t)}>
              {{input:"📋 Configure", results:"📊 Results", audit:"📜 Audit"}[t]}
              {t==="results" && scores.length>0 && <span className="tab-badge">{scores.length}</span>}
            </button>
          ))}
        </div>
        <div className="nav-right">
          {health && (
            <div className={`nav-status${health.ok?"":" nav-status-err"}`}>
              <span className={`status-dot${health.ok?"":" dot-err"}`}/>
              <span>{health.ok ? `API Live · ${health.model}` : "API Offline"}</span>
            </div>
          )}
        </div>
      </nav>

      <main className="main">

        {/* ── HERO ── */}
        <header className="hero">
          <div className="hero-glow hero-glow-1"/>
          <div className="hero-glow hero-glow-2"/>
          <div className="hero-content">
            <div className="hero-tag">Powered by LangGraph · Gemini · Sentence Transformers</div>
            <h1 className="hero-title">
              AI-Powered <span className="grad-text">Candidate Shortlisting</span> Agent
            </h1>
            <p className="hero-sub">
              5-dimension scoring rubric · Semantic resume matching · Human-in-the-loop override · Full audit trail
            </p>
            {result && (
              <div className="hero-pills">
                <span className="pill pill-green">{scores.length} Evaluated</span>
                <span className="pill pill-blue">{shortlisted.length} Shortlisted</span>
                <span className="pill pill-purple">Top: {scores[0]?.total_weighted_score?.toFixed(2)}</span>
                {fallback && <span className="pill pill-warn">⚠ Fallback Mode</span>}
              </div>
            )}
          </div>
        </header>

        {/* ── API offline banner ── */}
        {health && !health.ok && (
          <div className="error-banner">
            <div className="eb-header"><span className="eb-icon">🔴</span><span className="eb-code">API_OFFLINE</span></div>
            <p className="eb-msg">The API server is not running. Start it with: <code>python -m uvicorn api_server:app --reload --port 8000</code></p>
          </div>
        )}

        {/* ═══════ INPUT TAB ═══════ */}
        {tab==="input" && (
          <div className="fade-in">
            <div className="section-title">Configure Pipeline</div>

            <div className="input-grid">
              {/* JD Panel */}
              <div className="glass-card">
                <div className="panel-head">
                  <span className="panel-icon">📄</span>
                  <h2>Job Description</h2>
                  <button className="btn-ghost sm" onClick={loadSampleJD}>Load Sample JD</button>
                </div>
                {fieldErrors.jd && <div className="field-error">⚠ {fieldErrors.jd}</div>}
                <textarea className={`jd-textarea${fieldErrors.jd?" input-err":""}`}
                  placeholder="Paste the complete job description — role, required skills, experience, responsibilities..."
                  rows={12} value={jdText} onChange={(e)=>{setJdText(e.target.value);setFieldErrors(p=>({...p,jd:""}));}}/>
                <div className="or-row"><span>or upload file</span></div>
                <DropZone label="Drop or click · TXT / PDF / DOCX" accept=".txt,.pdf,.docx"
                  icon="📁" files={jdFile?[jdFile]:[]}
                  onChange={f=>{setJdFile(f[0]||null);setFieldErrors(p=>({...p,jd:""}));}}
                  error={null}/>
                {jdText.length > 0 && (
                  <div className="char-count">{jdText.length.toLocaleString()} characters</div>
                )}
              </div>

              {/* Candidates Panel */}
              <div className="glass-card">
                <div className="panel-head">
                  <span className="panel-icon">👥</span>
                  <h2>Candidate Profiles</h2>
                </div>
                {fieldErrors.candidates && <div className="field-error">⚠ {fieldErrors.candidates}</div>}

                <DropZone label="Drop or click · Resumes — PDF / DOCX" accept=".pdf,.docx"
                  multiple icon="📑" files={resumeFiles}
                  onChange={f=>{setResumeFiles(f);setFieldErrors(p=>({...p,candidates:""}));}}
                  error={null}/>
                <DropZone label="Drop or click · LinkedIn JSON exports" accept=".json"
                  multiple icon="🔗" files={linkedinFiles}
                  onChange={f=>{setLinkedinFiles(f);setFieldErrors(p=>({...p,candidates:""}));}}
                  error={null}/>

                <div className="action-row">
                  <button className="run-btn" disabled={!canRun||loading} onClick={()=>runPipeline(false)}>
                    {loading
                      ? <><span className="spinner"/> Running pipeline…</>
                      : <><span>🚀</span> Run Shortlisting Agent</>}
                  </button>
                  <button className="btn-sample" disabled={loading} onClick={()=>runPipeline(true)}
                    title="Run the pipeline on 5 built-in sample LinkedIn profiles">
                    ⚡ Run with Sample Data
                  </button>
                </div>

                <ErrorBanner error={apiError} onRetry={canRun?()=>runPipeline(false):null}/>
              </div>
            </div>

            {/* Pipeline progress */}
            {pipeStep >= 0 && (
              <div className="glass-card" style={{marginTop:18}}>
                <div className="panel-head"><span className="panel-icon">⚙️</span><h2>Pipeline Progress</h2></div>
                <PipelineProgress step={pipeStep}/>
              </div>
            )}
          </div>
        )}

        {/* ═══════ RESULTS TAB ═══════ */}
        {tab==="results" && (
          <div className="fade-in">
            {!result ? (
              <div className="empty-state">
                <div className="empty-icon">🔍</div>
                <h3>No results yet</h3>
                <p>Run the pipeline from the Configure tab to see ranked candidates here.</p>
                <button onClick={()=>setTab("input")}>Go to Configure →</button>
              </div>
            ) : (
              <>
                {/* Stats */}
                <div className="stats-row">
                  <StatCard value={scores.length}  label="Total Evaluated" icon="👤" color="#60c4ff"/>
                  <StatCard value={shortlisted.length} label="Shortlisted"  icon="✅" color="#00e5b0"/>
                  <StatCard value={scores[0]?.total_weighted_score??0} label="Top Score" icon="🏆" color="#ffcc55"/>
                  <StatCard value={avgScore}        label="Avg Score"       icon="📊" color="#b47cff"/>
                </div>

                {/* Fallback / quota warning */}
                {fallback && (
                  <div className="warn-box">
                    <b>⚠ Heuristic Fallback Mode Active</b>
                    <p style={{marginTop:6,marginBottom:0}}>
                      Your Gemini API quota was exhausted during this run. Scores were computed using
                      a deterministic rule-based fallback (skill-overlap, experience years, education keywords).
                      Results are useful for ranking but less precise than AI scoring.
                      To restore full AI scoring, add billing at{" "}
                      <a href="https://aistudio.google.com" target="_blank" rel="noreferrer">aistudio.google.com</a>.
                    </p>
                  </div>
                )}

                {/* Non-quota warnings */}
                {warnings.filter(w=>!w.includes("RESOURCE_EXHAUSTED")&&!w.includes("heuristic")).length > 0 && (
                  <div className="warn-box" style={{marginBottom:14}}>
                    <b>ℹ Pipeline Notes</b>
                    <ul>
                      {warnings.filter(w=>!w.includes("RESOURCE_EXHAUSTED")&&!w.includes("heuristic"))
                        .map((w,i)=><li key={i}>{w.slice(0,160)}</li>)}
                    </ul>
                  </div>
                )}

                {/* Rankings header */}
                <div className="section-title" style={{marginTop:22}}>
                  Ranked Candidates
                  {result.report_html && (
                    <button className="dl-btn" onClick={()=>{
                      const b=new Blob([result.report_html],{type:"text/html"});
                      const u=URL.createObjectURL(b);
                      const a=document.createElement("a");
                      a.href=u; a.download="shortlist_report.html"; a.click();
                      URL.revokeObjectURL(u);
                      _addToast("Report downloaded", "success");
                    }}>⬇ Download Report</button>
                  )}
                </div>

                {/* Score legend */}
                <div className="score-legend">
                  {Object.entries(REC_META).map(([k,m])=>(
                    <span key={k} className="legend-item" style={{color:m.color}}>
                      {m.icon} <span>{k}</span>
                    </span>
                  ))}
                  <span className="legend-item" style={{color:"var(--muted)"}}>
                    Score: ≥8.0 STRONG HIRE · ≥6.5 HIRE · ≥4.5 MAYBE · &lt;4.5 NO HIRE
                  </span>
                </div>

                {/* Candidate cards */}
                <div className="candidates-list">
                  {scores.map((s,i)=>(
                    <CandidateCard key={`${s.candidate_name}-${i}`}
                      s={s} rank={i+1}
                      expanded={expanded===i}
                      onToggle={()=>setExpanded(expanded===i?null:i)}
                      onOverride={setOverrideTarget}/>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* ═══════ AUDIT TAB ═══════ */}
        {tab==="audit" && (
          <div className="fade-in"><AuditPanel/></div>
        )}

      </main>
    </div>
  );
}
