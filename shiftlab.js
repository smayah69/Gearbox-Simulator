
(() => {
"use strict";
// ================= car configuration (see cars.js) =================
const CAR = window.SHIFTLAB_CARS[window.SHIFTLAB_CAR || "saxo"];
const Z = CAR.Z;
const RATIO = CAR.ratio;
const FD = CAR.fd, RW = CAR.tyre/(2*Math.PI), MASS = CAR.mass, G = 9.81;
const JE = 0.13, JI = 0.012, CDA = CAR.cda, RHO = 1.2, CRR = 0.012, BMAX = 7500;
const CLUTCH_CAP = CAR.clutchCap, SYNC_CAP = 14, LIMIT = CAR.limit, OVERREV = CAR.limit + 600;
const RPM = w => w*60/(2*Math.PI), RAD = r => r*2*Math.PI/60;
const clamp = (x,a,b) => Math.max(a, Math.min(b, x));
const ss = x => { x = clamp(x,0,1); return x*x*(3-2*x); };
const TQ = CAR.tq;
const NOS = CAR.nos || {tq:60, time:7, refill:20};   // nitrous: extra N·m, seconds per bottle, seconds to refill
function tmax(r){ if (r<=0) return 0; for (let i=1;i<TQ.length;i++){ if (r<=TQ[i][0]){ const [a,ta]=TQ[i-1],[b,tb]=TQ[i]; return ta+(tb-ta)*(r-a)/(b-a);} } return TQ[TQ.length-1][1]; }
// synchro units: A = 1/2, B = 3/4, C = 5th; each sits on the input or output shaft (CAR.units[k].shaft)
const UNITS = CAR.units;
const PLANES = CAR.planes;          // lever planes: {unit, up, down}
const REV = CAR.rev;                // {plane, dir}: dir +1 = reverse is "back", -1 = "forward"
const PKEYS = Object.keys(PLANES).map(Number).sort((a,b)=>a-b);
const PMIN = PKEYS[0], PMAX = PKEYS[PKEYS.length-1];
const fmt = n => Math.round(n).toLocaleString("en");
const wear = () => 1-S.health/100;   // 0 = new gearbox, 1 = wrecked: the car gets sillier as it wears

// ================= state =================
let S;
function fresh(){
  return {
    we:0, wi:0, v:0, engineOn:false, cranking:0, dist:0,
    clutch:{v:0,key:false,manual:false}, thr:{v:0,key:false,manual:false}, brk:{v:0,key:false,manual:false},
    units:{A:{s:0,st:"free",bt:0},B:{s:0,st:"free",bt:0},C:{s:0,st:"free",bt:0}},
    ri:0, riSt:"free", riBt:0,
    lever:{x:0, y:0, drag:false, kb:null, kbT:0, lockR:false},
    Tc:0, temp:40, health:100, grinding:0, grindWhy:"", syncing:null, syncT:0, overrevT:-9, limT:0, lugT:0,
    nos:{key:false, ptr:false, lvl:1, on:false},
    wearStage:0, popT:0,
    engagedSince:0, lastGear:"N", time:0, shake:0, puffs:[], sparks:[], stallT:-9,
  };
}
S = fresh();

function gearOf(unitKey, side){ return UNITS[unitKey].gears[String(side)]; }
function engaged(){
  for (const k of Object.keys(UNITS)){ const u=S.units[k]; if (u.st==="engaged") return {gear:gearOf(k,Math.sign(u.s)), unit:k}; }
  if (S.riSt==="engaged") return {gear:"R", unit:"R"};
  return null;
}
function clutchCap(){ return CLUTCH_CAP*(1-ss((S.clutch.v-0.2)/0.55)); }

// ================= coach / messages =================
const msgTitle=document.getElementById("msgTitle"), msgText=document.getElementById("msgText"), logEl=document.getElementById("log");
const lastMsg={};
function say(key, title, text, mood="info", cool=3){
  const now=S.time;
  if (lastMsg[key]!==undefined && now-lastMsg[key]<cool) return;
  lastMsg[key]=now;
  msgTitle.textContent=title; msgText.innerHTML=text;
  msgTitle.className = mood==="bad"?"bad":mood==="good"?"good":"";
  const li=document.createElement("li");
  const m=Math.floor(now/60), s=Math.floor(now%60);
  li.innerHTML=`<time>${m}:${String(s).padStart(2,"0")}</time><span></span>`;
  li.querySelector("span").textContent=title;
  logEl.prepend(li); while(logEl.children.length>4) logEl.lastChild.remove();
  faceMoodHold = {bad:"ouch",good:"happy",info:null}[mood]; faceHoldT = 2.2;
}

// ================= controls =================
// every pedal can appear twice (full size at the bottom, mini in the top strip); both drive the same S[k]
function pedalSetup(el, k){
  const track=el.querySelector(".track"), pad=el.querySelector(".pad");
  let dragging=false;
  const set=(e)=>{ const r=track.getBoundingClientRect(), ph=pad.offsetHeight, o=S[k];
    o.v=clamp((e.clientY-r.top-4-ph/2)/(r.height-ph-12),0,1); o.manual=true; o.key=false; };
  el.addEventListener("pointerdown",e=>{dragging=true;el.setPointerCapture(e.pointerId);set(e);e.preventDefault();});
  el.addEventListener("pointermove",e=>{ if(dragging) set(e); });
  el.addEventListener("pointerup",()=>dragging=false);
  el.addEventListener("pointercancel",()=>dragging=false);
  return el;
}
const pedalEls=[];
for (const [k,ids] of [["clutch",["clutchPedal","clutchMini"]],["brk",["brakePedal","brakeMini"]],["thr",["throttlePedal","throttleMini"]]])
  for (const id of ids){ const el=document.getElementById(id); if (el) pedalEls.push([k,pedalSetup(el,k)]); }
function pedalUI(){
  for (const [k,el] of pedalEls){
    const v=S[k].v, h=el.querySelector(".track").clientHeight, pad=el.querySelector(".pad"), val=el.querySelector(".val");
    pad.style.top=(4+v*(h-pad.offsetHeight-12))+"px";
    el.querySelector(".fill").style.height=(v*100)+"%";
    if (val) val.textContent=Math.round(v*100)+" %";
    el.setAttribute("aria-valuenow",Math.round(v*100));
  }
}
function pedalKeys(dt){
  const c=S.clutch;
  if (c.key) c.v=Math.min(1,c.v+6*dt); else if(!c.manual) c.v=Math.max(0,c.v-0.8*dt);
  for (const p of [S.thr,S.brk]){ if(p.key) p.v=Math.min(1,p.v+2.4*dt); else if(!p.manual) p.v=Math.max(0,p.v-4*dt); }
}

// ---- lever / H-gate (main one at the bottom, mini copy in the top strip) ----
const GW = (PMAX-PMIN)>=3 ? 42 : 50, GC = 100-(PMIN+PMAX)/2*GW;
const GX=x=>GC+x*GW, GY=y=>120+y*78;
function buildGate(svg, font, kr){
  const xs=PKEYS.map(GX), paths=[`M${xs[0]} 120 H${xs[xs.length-1]}`];
  let labels="";
  for (const p of PKEYS){
    const P=PLANES[p], x=GX(p);
    paths.push(`M${x} ${P.up!=null?42:120} V${P.down!=null?198:120}`);
    if (P.up!=null) labels+=`<text x="${x}" y="27">${P.up}</text>`;
    if (P.down!=null) labels+=`<text x="${x}" y="226">${P.down}</text>`;
  }
  const d=paths.join(" ");
  svg.innerHTML=`
  <rect x="4" y="4" width="192" height="232" rx="22" fill="var(--surface-2)" stroke="var(--line)" stroke-width="2"/>
  <g stroke="var(--line)" stroke-width="16" stroke-linecap="round" fill="none"><path d="${d}"/></g>
  <g stroke="var(--surface)" stroke-width="8" stroke-linecap="round" fill="none" opacity=".9"><path d="${d}"/></g>
  <g font-family="Fredoka, Nunito, sans-serif" font-weight="700" font-size="${font}" fill="var(--muted)" text-anchor="middle">${labels}</g>
  <line class="stick" x1="${GX(0)}" y1="120" x2="${GX(0)}" y2="120" stroke="var(--muted)" stroke-width="5" stroke-linecap="round" opacity=".5"/>
  <circle class="knob" cx="${GX(0)}" cy="120" r="${kr}" fill="var(--accent)" stroke="var(--surface)" stroke-width="3"/>
  <circle class="knobHi" cx="${GX(0)-6}" cy="114" r="${kr*0.3}" fill="#fff" opacity=".55"/>`;
  const gatePoint=e=>{ const r=svg.getBoundingClientRect(); return {x:((e.clientX-r.left)/r.width*200-GC)/GW, y:((e.clientY-r.top)/r.height*240-120)/78}; };
  svg.addEventListener("pointerdown",e=>{ svg.setPointerCapture(e.pointerId); S.lever.drag=true; S.lever.kb=null; leverPtr=gatePoint(e); e.preventDefault(); });
  svg.addEventListener("pointermove",e=>{ if(S.lever.drag) leverPtr=gatePoint(e); });
  svg.addEventListener("pointerup",leverUp); svg.addEventListener("pointercancel",leverUp);
  return {knob:svg.querySelector(".knob"), knobHi:svg.querySelector(".knobHi"), stick:svg.querySelector(".stick")};
}
let leverPtr=null;
const leverUp=()=>{ if(!S.lever.drag) return; S.lever.drag=false; leverPtr=null;
  const eg=engaged(); if (eg){ S.lever.y = Math.sign(actualY()); } else { S.lever.y=0; S.lever.kb={x:0,y:0,rest:true}; } };
const gates=[[ "gate",17,17],["gateMini",30,24]].map(([id,f,kr])=>document.getElementById(id)&&buildGate(document.getElementById(id),f,kr)).filter(Boolean);

function actualY(){ // the lever's real position follows the sleeve / idler of the plane it sits in
  const pl=Math.round(S.lever.x);
  if (Math.abs(S.lever.x-pl)>0.15 || !PLANES[pl]) return 0;
  const P=PLANES[pl];
  if (pl===REV.plane && (S.ri>0.001 || S.lever.y*REV.dir>0.02) && (!P.unit || S.units[P.unit].s*REV.dir>=-0.001)) return S.ri*REV.dir;
  return P.unit ? S.units[P.unit].s : 0;
}
function inRail(){ return Math.abs(actualY())<0.12; }
function leverStep(dt){
  const L=S.lever;
  if (L.drag && leverPtr){
    if (inRail()) { const nx=clamp(leverPtr.x,PMIN,PMAX); L.x += clamp(nx-L.x,-8*dt,8*dt); }
    const pl=Math.round(L.x);
    let ty = (Math.abs(L.x-pl)<0.15 && PLANES[pl]) ? clamp(leverPtr.y,-1,1) : 0;
    if (PLANES[pl] && ((ty<0 && PLANES[pl].up==null) || (ty>0 && PLANES[pl].down==null))) ty=0;
    L.y = ty;
  } else if (L.kb){
    const t=L.kb; L.kbT+=dt;
    const pl=Math.round(L.x);
    if (Math.abs(L.x-t.x)>0.02){
      if (Math.abs(actualY())>0.12){ L.y=0; }
      else { L.y=0; L.x += clamp(t.x-L.x,-6*dt,6*dt); if (Math.abs(L.x-t.x)<0.02) L.x=t.x; }
    } else {
      if (t.y!==0 && Math.sign(actualY())!==0 && Math.sign(actualY())!==Math.sign(t.y)) L.y=0;
      else L.y += clamp(t.y-L.y,-7*dt,7*dt);
      if (t.rest && Math.abs(L.y)<0.01 && Math.abs(L.x)<0.01) L.kb=null;
    }
    if ((S.grinding>0.9) && t.y!==0){ // give up after a second of grinding
      say("abort","Lever popped back to neutral","You kept pushing while it ground. Press the clutch fully and try again.","bad",2);
      L.kb={x:0,y:0,rest:true}; L.y=0;
    }
  } else if (!engaged() && Math.abs(L.y)<0.02 && Math.abs(L.x)>0.001 && inRail()){
    L.x += clamp(-L.x,-4*dt,4*dt); // spring back to the 3/4 plane
  }
  // 5th → reverse lockout (only where 5th and reverse share a plane, like the MA)
  if (CAR.lockout5R){
    if (S.units.C.st==="engaged") L.lockR=true;
    if (Math.round(L.x)!==REV.plane) L.lockR=false;
    if (L.lockR && Math.round(L.x)===REV.plane && L.y*REV.dir>0.1 && S.units.C.s*REV.dir>=-0.05){
      L.y=0.08*REV.dir; say("lockR","5th → reverse lockout",CAR.lockoutText,"info",3);
    }
  }
}
function selectGear(g){
  let x=0, y=0;
  if (g!=="N") for (const p of PKEYS){ if (PLANES[p].up==g){x=p;y=-1;} if (PLANES[p].down==g){x=p;y=1;} }
  S.lever.kb={x,y,rest:g==="N"}; S.lever.kbT=0; S.lever.drag=false;
}
function leverUI(){
  const ay=actualY(); let jx=0,jy=0;
  if (S.grinding>0.05 && !reduceMotion){ jx=(Math.random()-0.5)*4; jy=(Math.random()-0.5)*4; }
  else if (wear()>0.3 && !reduceMotion){ jx=Math.sin(S.time*9)*wear()*2.5; } // sloppy linkage
  const cx=GX(S.lever.x)+jx, cy=GY(ay)+jy;
  for (const g of gates){ g.knob.setAttribute("cx",cx); g.knob.setAttribute("cy",cy); g.knobHi.setAttribute("cx",cx-6); g.knobHi.setAttribute("cy",cy-6);
    g.stick.setAttribute("x2",cx); g.stick.setAttribute("y2",cy); }
}

// ---- keyboard ----
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
addEventListener("keydown",e=>{
  if (e.target && (e.target.tagName==="INPUT"||e.target.tagName==="TEXTAREA")) return;
  const k=e.key.toLowerCase(), dig=/^Digit\d$/.test(e.code) ? e.code.slice(5) : k; // Shift+1 still means 1st
  if (k==="shift"){ S.nos.key=true; }
  else if (k===" "||k==="c"){ S.clutch.key=true; S.clutch.manual=false; e.preventDefault(); }
  else if (k==="w"||k==="arrowup"){ S.thr.key=true; S.thr.manual=false; e.preventDefault(); }
  else if (k==="s"||k==="arrowdown"){ S.brk.key=true; S.brk.manual=false; e.preventDefault(); }
  else if ("12345".includes(dig) && dig.length===1){ selectGear(+dig); }
  else if (k==="r"){ selectGear("R"); }
  else if (k==="n"||dig==="0"){ selectGear("N"); }
  else if (k==="e" && !e.repeat){ toggleEngine(); }
  else if (k==="m" && !e.repeat){ toggleSound(); }
});
addEventListener("keyup",e=>{
  const k=e.key.toLowerCase();
  if (k==="shift") S.nos.key=false;
  else if (k===" "||k==="c") S.clutch.key=false;
  else if (k==="w"||k==="arrowup") S.thr.key=false;
  else if (k==="s"||k==="arrowdown") S.brk.key=false;
});
addEventListener("blur",()=>{ S.clutch.key=S.thr.key=S.brk.key=S.nos.key=S.nos.ptr=false; });

// ---- nitrous button (hold) ----
const nosBtn=document.getElementById("nosBtn"), nosFill=document.getElementById("nosFill");
if (nosBtn){
  nosBtn.addEventListener("pointerdown",e=>{ nosBtn.setPointerCapture(e.pointerId); S.nos.ptr=true; e.preventDefault(); });
  for (const ev of ["pointerup","pointercancel","lostpointercapture"]) nosBtn.addEventListener(ev,()=>{ S.nos.ptr=false; });
}

// ---- engine start ----
const startBtn=document.getElementById("startBtn"), startTxt=document.getElementById("startTxt"), engDot=document.getElementById("engDot");
function toggleEngine(){
  if (S.engineOn || S.cranking>0){ S.engineOn=false; S.cranking=0; say("off","Engine off","Turn it back on with Start or E.","info",0.5); return; }
  const eg=engaged();
  if (eg && clutchCap()>20){ say("startgear","Clutch first!","You're in gear. Starting now would jerk the car forward on the starter. Press the clutch (or pick neutral), then start.","bad",1); return; }
  S.cranking=0.75; say("crank","Cranking…","Starter motor spinning the engine up.","info",0.5);
}
startBtn.addEventListener("click",toggleEngine);
document.getElementById("resetBtn").addEventListener("click",()=>{ const snd=S.sound; S=fresh(); S.sound=snd; logEl.innerHTML=""; say("reset","Fresh gearbox","Everything reset. Start the engine to drive again.","good",0); });

// ================= physics =================
function fres(v){ return CRR*MASS*G*clamp(v/0.3,-1,1) + 0.5*RHO*CDA*v*Math.abs(v); }
function fbrake(v){ return S.brk.v*BMAX*clamp(v/0.3,-1,1); }
function dragI(w){ return 0.6*clamp(w/2,-1,1)+0.004*w; }

function stepUnits(dt){
  const L=S.lever, pl=Math.round(L.x), onPlane=Math.abs(L.x-pl)<0.15;
  const wo = S.v/RW*FD;
  S.syncing=null;
  for (const k of Object.keys(UNITS)){
    const u=S.units[k];
    const P = onPlane ? PLANES[pl] : null;
    let tgt = (P && P.unit===k) ? L.y : 0;
    if (tgt && !gearOf(k,Math.sign(tgt))) tgt=0;   // that side of the plane is reverse, not this sleeve
    if (P && P.unit===k && pl===REV.plane && S.ri>0.01) tgt=0;
    if (u.st==="engaged"){
      if (tgt*Math.sign(u.s)<0.5){
        if (Math.abs(S.Tc)<30 || clutchCap()<5){ u.st="free"; u.s-=Math.sign(u.s)*0.12; }
        else say("loaded","Stuck in gear","The dog teeth are carrying engine torque, so the sleeve won't slide out. Press the clutch or lift off the throttle.","bad",3);
      }
      continue;
    }
    const d = Math.sign(tgt)||Math.sign(u.s);
    if (Math.abs(tgt)>Math.abs(u.s)+1e-3 && d!==0 && (Math.sign(u.s)===d||u.s===0)){
      let next=u.s+d*6*dt;
      const g=gearOf(k,d); if (!g){ u.s=0; continue; }
      const diff=S.wi-wo*RATIO[g];
      if (Math.abs(next)>=0.35){
        S.syncing={unit:k,gear:g,diff,side:d}; // cone friction acts from ring contact until the dogs mesh
        if (Math.abs(u.s)<0.36 && Math.abs(diff)>2.5){
          u.s=d*0.35; if(u.st!=="blocked"){u.st="blocked"; u.bt=0; S.syncT=0;}
          u.bt+=dt;
          continue;
        }
      }
      if (u.st==="blocked") u.st="free"; // ring unblocked: speeds match
      u.s=clamp(next,-1,1);
      if (Math.abs(u.s)>=0.9){
        if (Math.abs(diff)<4){
          u.s=d; u.st="engaged";
          if (clutchCap()>12) say("clutchless","Clean clutchless shift into "+g+ordS(g)+"!","Engine speed already matched the gear, so the synchro had nothing to do. Nice rev-matching.","good",4);
          else if (u.bt>0) say("synced",g+ordS(g)+" engaged",`The synchro matched speeds in ${Math.max(10,Math.round(u.bt*1000))} ms, then the sleeve slid onto the dog teeth.`,"good",1.5);
          else say("synced",g+ordS(g)+" engaged","Nothing was turning, so the sleeve slid straight onto the dog teeth.","good",1.5);
          S.wi = wo*RATIO[g]; u.bt=0;
        } else { u.s=d*0.35; u.st="blocked"; }
      }
    } else {
      // moving back toward neutral or toward the target inside the free zone
      u.st = "free";
      u.s += clamp(tgt-u.s,-6*dt,6*dt);
      if (Math.abs(u.s)<0.35) u.bt=0;
    }
  }
  // reverse idler (no synchroniser)
  const RP = PLANES[REV.plane];
  let tR = (onPlane && pl===REV.plane && L.y*REV.dir>0 && (!RP.unit || S.units[RP.unit].s*REV.dir>=-0.001)) ? L.y*REV.dir : 0;
  if (S.riSt==="engaged"){
    if (tR<0.5){ if (Math.abs(S.Tc)<30 || clutchCap()<5){ S.riSt="free"; S.ri=0.85; } else say("loadedR","Stuck in reverse","The idler is carrying torque. Press the clutch or lift off the throttle.","bad",3); }
  } else if (tR>S.ri+1e-3){
    let next=S.ri+4*dt;
    const inputSpin=Math.abs(RPM(S.wi)), rolling=Math.abs(S.v);
    if (next>=0.4 && S.ri<0.41 && (inputSpin>60 || rolling>0.25)){
      S.ri=0.4; S.riSt="blocked"; S.riBt+=dt;
      if (rolling>0.25) S.grindWhy="rolling"; else S.grindWhy= clutchCap()>12 ? "revclutch":"revspin";
    } else {
      S.riSt="free"; S.ri=Math.min(1,next);
      if (S.ri>=0.95){ S.ri=1; S.riSt="engaged"; S.wi=0; say("rev","Reverse engaged","The idler slid into mesh with the input reverse gear and the teeth on the 1/2 sleeve. Three gears in a row: the car will go backwards.","good",2); }
    }
  } else { S.riSt="free"; S.riBt=0; S.ri += clamp(tR-S.ri,-4*dt,4*dt); }
}
function ordS(g){ return g===1?"st":g===2?"nd":g===3?"rd":"th"; }

function physics(dt){
  S.time+=dt;
  stepUnits(dt);
  const eg=engaged();
  const cap=clutchCap();
  // engine torque
  const rpm=RPM(S.we);
  let thr=S.thr.v;
  if (S.engineOn){
    const idle = clamp(0.16+(850-rpm)*0.0016,0,0.6);
    thr=Math.max(thr,idle);
    if (rpm>LIMIT) thr=0;
  }
  let Te=0;
  const fric = 5+0.0028*rpm+(1-S.thr.v)*0.0025*rpm;
  if (S.engineOn) Te = thr*tmax(rpm) - fric;
  else Te = -fric*clamp(S.we/3,0,1);
  if (S.cranking>0){ Te += 45; }
  // nitrous: only fires with the engine running, real throttle, above 1,200 rpm and below the limiter
  const nosWant = S.nos.key||S.nos.ptr;
  S.nos.on = nosWant && S.engineOn && S.nos.lvl>0 && S.thr.v>0.2 && rpm>1200 && rpm<LIMIT;
  if (S.nos.on){ Te += NOS.tq*S.thr.v; S.nos.lvl=Math.max(0,S.nos.lvl-dt/NOS.time); }
  else if (!nosWant) S.nos.lvl=Math.min(1,S.nos.lvl+dt/NOS.refill);
  // downstream
  let Jd, Tload, Tsync=0, rg=null;
  if (eg){
    rg=RATIO[eg.gear];
    const k=FD*rg;
    Jd = JI + MASS*RW*RW/(k*k);
    Tload = -(fres(S.v)+fbrake(S.v))*RW/k;
  } else {
    Jd=JI; Tload=-dragI(S.wi);
    if (S.syncing){
      const wo=S.v/RW*FD, tgt=wo*RATIO[S.syncing.gear];
      const locked = cap>1 && Math.abs(S.we-S.wi)<1;
      const Jeff = JI + (locked?JE:0);
      const cap2=SYNC_CAP*(1-0.6*wear()); Tsync = clamp(Jeff*(tgt-S.wi)/dt, -cap2, cap2);   // worn cones grip less
      Tload += Tsync;
    }
  }
  // implicit clutch torque
  let Tc = (S.we - S.wi + dt*(Te/JE - Tload/Jd)) / (dt*(1/JE+1/Jd));
  Tc = clamp(Tc,-cap,cap);
  S.Tc=Tc;
  S.we += dt*(Te-Tc)/JE;
  S.wi += dt*(Tc+Tload)/Jd;
  if (S.we<0) S.we=0;
  // car
  if (eg){ S.v = S.wi*RW/(FD*rg); }
  else {
    let F = -fres(S.v) - fbrake(S.v);
    if (S.syncing) F += -Tsync*RATIO[S.syncing.gear]*FD/RW;
    S.v += dt*F/MASS;
  }
  S.dist += S.v*dt;
  // clutch heat
  const slipP = Math.abs(Tc*(S.we-S.wi));
  S.temp += dt*(slipP/900 - (S.temp-40)*0.035);
  // cranking
  if (S.cranking>0){ S.cranking-=dt; if (RPM(S.we)>420){ S.engineOn=true; S.cranking=0; say("started","Engine running","Idling at about 850 rpm. Hold the clutch and pick 1st.","good",1); } else if (S.cranking<=0){ say("nocrank","Won't turn over","The starter couldn't spin the engine: something is holding it (in gear with the clutch up?). Press the clutch and try again.","bad",1); } }
  // stall
  const r2=RPM(S.we);
  if (S.engineOn && r2<360){
    S.engineOn=false; S.stallT=S.time; S.shake=0.6;
    const g=eg?eg.gear:null;
    if (g && Math.abs(S.v)<1.0 && (g===3||g===4||g===5)) say("stall","Stalled in "+g+ordS(g)+"!","Pulling away in "+g+ordS(g)+" asks the engine to move the car with very little gear reduction. Use 1st: it multiplies torque "+RATIO[1].toFixed(1)+" times.","bad",1);
    else if (g && S.brk.v>0.3) say("stall","Stalled!","You braked to a stop still in gear with the clutch up, so the wheels dragged the engine to a halt. Press the clutch before you stop.","bad",1);
    else if (g) say("stall","Stalled!","The clutch bit too quickly for the engine speed, so the car's load stopped the engine. Release the clutch more slowly through the bite point and add a little throttle.","bad",1);
    else say("stall","Engine stopped","Engine speed fell too low. Press Start to restart.","bad",1);
    S.health=Math.max(0,S.health-1);
  }
  // grinding
  let grind=false;
  if (S.syncing && !eg){
    S.syncT+=dt;
    const u=S.units[S.syncing.unit];
    if (u.st==="blocked" && u.bt>0.15 && cap>12){ grind=true; S.grindWhy="noclutch"; }
  }
  if (S.riSt==="blocked") grind=true;
  if (grind){ S.grinding=Math.min(2,S.grinding+dt); S.health=Math.max(0,S.health-dt*(S.riSt==="blocked"?5:3.5)); }
  else S.grinding=Math.max(0,S.grinding-dt*3);
}

// ================= monitors (messages that need context) =================
let lastGrindMsg=-9;
function monitors(dt){
  const eg=engaged(), rpm=RPM(S.we), kmh=S.v*3.6;
  if (S.grinding>0.05){
    if (S.grindWhy==="noclutch" && S.syncing){
      const g=S.syncing?S.syncing.gear:"";
      say("grind","KRRRRK! Grinding into "+g+ordS(g),"The clutch isn't pressed, so the synchro would have to slow down the whole engine and flywheel too. It can't, the blocker ring stays in the way and the sleeve chamfers grind on it. Press the clutch fully, then shift.","bad",2.5);
    } else if (S.grindWhy==="rolling") say("grindR","CRUNCH! Reverse while rolling","Reverse has no synchroniser. With the car still moving, the idler's straight teeth smash against the spinning teeth on the 1/2 sleeve. Stop completely first.","bad",2.5);
    else if (S.grindWhy==="revclutch") say("grindR2","CRUNCH! Reverse with the clutch up","The input shaft is spinning with the engine, and reverse has no synchro to stop it. Press the clutch, wait a second, then select R.","bad",2.5);
    else if (S.grindWhy==="revspin") say("grindR3","Crunch… wait a moment","The clutch is pressed, but the input shaft is still spinning down. Give it a second, or briefly touch a forward gear to stop it, then select R.","bad",2.5);
  }
  const forced = eg && clutchCap()>60 && RPM(Math.abs(S.wi))>OVERREV && Math.abs(S.we-S.wi)>RAD(300);
  if ((rpm>OVERREV || forced) && S.overrevT<S.time-3){ S.overrevT=S.time; S.health=Math.max(0,S.health-8);
    say("overrev","Over-rev! "+(eg?(eg.gear==="R"?"Reverse":eg.gear+ordS(eg.gear)):"")+" at "+Math.round(Math.abs(kmh))+" km/h","In this gear the wheels turn the input shaft at "+Math.round(RPM(Math.abs(S.wi))).toLocaleString("en")+" rpm, far past the "+fmt(LIMIT)+" rpm red line. Letting the clutch up drags the engine toward that speed and the car lurches. The synchro happily matched the input shaft; the engine is what can't take it. Pick a gear that suits your speed.","bad",3); S.shake=0.4; }
  if (S.engineOn && rpm>LIMIT-50 && S.thr.v>0.5){ S.limT+=dt; if (S.limT>0.6) say("limiter","Bouncing off the limiter",fmt(LIMIT)+" rpm is the fuel cut-off. Press the clutch and shift up.","info",5); } else S.limT=0;
  if (eg && eg.gear!=="R" && S.engineOn && clutchCap()>150 && rpm<1100 && S.thr.v>0.6 && Math.abs(S.we-S.wi)<2){ S.lugT+=dt; if(S.lugT>1.2) say("lug","Lugging the engine","Full throttle below 1,100 rpm strains the engine and gearbox. Change down a gear.","info",6); } else S.lugT=0;
  if (S.temp>230) say("hot","Clutch is smoking","You've been slipping the clutch for a long time. Let it fully up or fully down; the friction plate is near "+Math.round(S.temp)+" °C.","bad",6);
  if (S.nos.key||S.nos.ptr){
    if (!S.engineOn) say("nosOff","Nitrous needs a running engine","Start the engine (E), pick a gear, then hold Shift with the throttle down.","info",5);
    else if (S.nos.lvl<=0) say("nosEmpty","Nitrous bottle empty","Let go of Shift and the bottle refills in about "+NOS.refill+" s.","info",5);
    else if (S.thr.v<=0.2) say("nosThr","Add throttle for nitrous","Nitrous only fires with the throttle pressed. Hold W as well as Shift.","info",5);
    else if (S.nos.on && (!eg || clutchCap()<20)) say("nosN","Nitrous with nothing to push","No gear is driving the wheels, so the extra torque only spins the engine up to the limiter.","info",5);
    else if (S.nos.on) say("nos","Nitrous!","Nitrous oxide brings extra oxygen so the engine burns more fuel: about +"+NOS.tq+" N·m at full throttle. The bottle lasts "+NOS.time+" s.","good",8);
  }
  if (!S.engineOn && S.cranking<=0 && S.thr.v>0.5 && S.time-S.stallT>1.5) say("thrOff","Engine is off","Throttle does nothing without the engine running. Press Start (E).","info",6);
  if (eg && eg.gear===1 && kmh>3 && S.lastGear!=="1") {}
  // worn gearbox: the car gets dumber in stages, and worn dog teeth let a gear jump out off the throttle
  const stage = S.health<15?3 : S.health<40?2 : S.health<70?1 : 0;
  if (stage>S.wearStage){
    S.wearStage=stage;
    if (stage===1) say("wear1","The car looks a bit dopey…","Gearbox health is under 70 %. The synchro cones are glazing, so shifts take longer and grind more easily. Be gentle!","bad",0);
    else if (stage===2) say("wear2","Uh-oh, the car's gone silly","Under 40 %: the dog teeth are rounded off, so gears can jump out when you lift off the throttle. Listen for the whine.","bad",0);
    else say("wear3","Duuuh… the car has lost it","Under 15 %: this gearbox is scrap. Press Reset for a fresh one.","bad",0);
  }
  S.popT+=dt;
  if (eg && eg.gear!=="R" && S.health<40 && S.engineOn && S.thr.v<0.15 && Math.abs(S.v)>3 && S.popT>2 && Math.random()<dt*(0.4-S.health/100)*1.5){
    const u=S.units[eg.unit]; u.st="free"; u.s=Math.sign(u.s)*0.3; selectGear("N"); S.popT=0; S.shake=0.3; clunk();
    say("popout","Popped out of "+eg.gear+ordS(eg.gear)+"!","The worn dog teeth are rounded, so when you lifted off the throttle the sleeve walked back out to neutral. Healthy gearboxes have back-cut teeth that hold it in.","bad",3);
  }
  const gname = eg ? String(eg.gear) : "N";
  if (gname!==S.lastGear){ S.lastGear=gname; }
  if (eg && eg.gear==="R" && S.v>0.5){}
}

// ================= audio =================
let AC=null, au={};
const soundBtn=document.getElementById("soundBtn");
const SND = Object.assign({wave:"sawtooth", sub:0.5, harm:[2,0,"square"], cutoff:300, open:1600, q:4, drive:0, rasp:0, raspHz:1200,
  burble:0, whine:0, whineMul:6, pops:0, starter:33, vol:1}, CAR.sound||{});   // per-car engine voice (cars.js)
function driveCurve(k){ // soft clip; k = 0 leaves the wave untouched
  const n=1024, c=new Float32Array(n), a=k*40;
  for (let i=0;i<n;i++){ const x=i/(n-1)*2-1; c[i]=(1+a)*x/(1+a*Math.abs(x)); }
  return c;
}
function initAudio(){
  try{
    AC=new (window.AudioContext||window.webkitAudioContext)();
    const osc=type=>{ const o=AC.createOscillator(); o.type=type; o.start(); return o; };
    const gain=v=>{ const g=AC.createGain(); g.gain.value=v; return g; };
    const filt=(type,f,q)=>{ const b=AC.createBiquadFilter(); b.type=type; b.frequency.value=f; b.Q.value=q; return b; };
    const master=gain(0.6); master.connect(AC.destination);
    // engine: firing order + half order + one harmonic → grit → lowpass → burble (uneven firing) → level
    const [hm,hg,ht]=SND.harm;
    const mix=gain(SND.vol*1.5/(1+SND.sub+hg)), sh=AC.createWaveShaper(); sh.curve=driveCurve(SND.drive); sh.oversample="2x";
    const lp=filt("lowpass",600,SND.q), amp=gain(1-SND.burble/2), eg=gain(0);
    mix.connect(sh); sh.connect(lp); lp.connect(amp); amp.connect(eg); eg.connect(master);
    const o1=osc(SND.wave), o2=osc("square"), o3=osc(ht), g2=gain(SND.sub), g3=gain(hg);
    o1.connect(mix); o2.connect(g2); g2.connect(mix); o3.connect(g3); g3.connect(mix);
    const lfo=osc("sine"), lg=gain(SND.burble/2); lfo.connect(lg); lg.connect(amp.gain);
    const ow=osc("sine"), wg=gain(0); ow.connect(wg); wg.connect(master);          // intake / chain whine
    const len=AC.sampleRate*1, buf=AC.createBuffer(1,len,AC.sampleRate), d=buf.getChannelData(0);
    for(let i=0;i<len;i++) d[i]=Math.random()*2-1;
    const nz=AC.createBufferSource(); nz.buffer=buf; nz.loop=true; nz.start();
    const noise=(f,g)=>{ f.connect(g); g.connect(master); nz.connect(f); return g; };
    const rbp=filt("bandpass",SND.raspHz,1.2), rg=noise(rbp,gain(0));                // exhaust rasp
    const bp=filt("bandpass",2600,2.5), gg=noise(bp,gain(0));                         // grinding
    const hp=filt("highpass",3800,0.7), ng=noise(hp,gain(0));                         // nitrous hiss
    const pbp=filt("bandpass",800,0.9), pg=noise(pbp,gain(0));                        // overrun pops
    const st=osc("square"); st.frequency.value=SND.starter; const sg=gain(0); st.connect(sg); sg.connect(mix);
    const gw=osc("triangle"), gwg=gain(0); gw.connect(gwg); gwg.connect(master);        // worn-gear whine
    au={master,lp,eg,o1,o2,o3,lfo,ow,wg,rbp,rg,gg,bp,ng,pbp,pg,sg,st,gw,gwg};
  }catch(e){ AC=null; }
}
function clunk(){ // a short knock when a gear jumps out
  if (!AC || !S.sound) return;
  const t=AC.currentTime; au.pbp.frequency.setValueAtTime(260,t);
  au.pg.gain.cancelScheduledValues(t); au.pg.gain.setValueAtTime(0.5,t); au.pg.gain.exponentialRampToValueAtTime(0.0005,t+0.12);
}
function toggleSound(){
  if (!AC) initAudio();
  if (!AC) { soundBtn.textContent="🔇 No audio"; return; }
  S.sound=!S.sound;
  if (S.sound) AC.resume();
  au.master.gain.setTargetAtTime(S.sound?0.6:0, AC.currentTime, 0.05);
  soundBtn.textContent = S.sound ? "🔊 Sound on" : "🔈 Sound off";
  soundBtn.setAttribute("aria-pressed", String(!!S.sound));
}
soundBtn.addEventListener("click",toggleSound);
let popT=9, prevThr=0, lastAT=0;
function audioTick(){
  if (!AC || !S.sound) return;
  const t=AC.currentTime, dt=clamp(t-lastAT,0,0.1), rpm=RPM(S.we), f=Math.max(8,rpm/30), nos=S.nos.on; lastAT=t;
  const run = S.engineOn||rpm>100;
  au.o1.frequency.setTargetAtTime(f,t,0.02); au.o2.frequency.setTargetAtTime(f/2,t,0.02); au.o3.frequency.setTargetAtTime(f*SND.harm[0],t,0.02);
  au.lfo.frequency.setTargetAtTime(f/2,t,0.02); au.ow.frequency.setTargetAtTime(f*SND.whineMul,t,0.02);
  au.lp.frequency.setTargetAtTime(SND.cutoff+S.thr.v*SND.open+rpm*0.12+(nos?700:0),t,0.05);
  const on = run ? (0.06+0.14*S.thr.v)*clamp(rpm/600,0,1)*(nos?1.25:1) : 0;
  au.eg.gain.setTargetAtTime(on,t,0.05);
  au.rg.gain.setTargetAtTime(S.engineOn ? SND.rasp*S.thr.v*clamp(rpm/1500,0,1) : 0,t,0.05); au.rbp.frequency.setTargetAtTime(SND.raspHz+rpm*0.15,t,0.05);
  au.wg.gain.setTargetAtTime(run ? SND.whine*clamp(rpm/LIMIT,0,1) : 0,t,0.05);
  au.sg.gain.setTargetAtTime(S.cranking>0?0.12:0,t,0.03); au.st.frequency.setTargetAtTime(SND.starter*(0.85+Math.random()*0.3),t,0.02);
  const gr = S.grinding>0.05 ? 0.18+0.14*Math.random() : 0;
  au.gg.gain.setTargetAtTime(gr,t,0.015); au.bp.frequency.setTargetAtTime(1800+Math.random()*1800,t,0.01);
  au.ng.gain.setTargetAtTime(nos?0.11:0,t,0.04);
  const ws=RPM(Math.abs(S.wi)), wr=wear();   // worn gears whine at tooth-mesh frequency
  au.gw.frequency.setTargetAtTime(80+ws/60*12,t,0.03); au.gwg.gain.setTargetAtTime(wr>0.3 ? (wr-0.3)*0.12*clamp(ws/1500,0,1) : 0,t,0.08);
  // overrun pops: a short window after lifting off the throttle at high revs
  if (prevThr>0.3 && S.thr.v<0.1 && rpm>2800) popT=0;
  prevThr=S.thr.v; popT+=dt;
  if (SND.pops && S.engineOn && popT<1.5 && rpm>2000 && S.thr.v<0.1 && Math.random()<SND.pops*0.25){
    au.pbp.frequency.setValueAtTime(500+Math.random()*600,t);
    au.pg.gain.cancelScheduledValues(t); au.pg.gain.setValueAtTime(0.25+0.2*Math.random(),t);
    au.pg.gain.exponentialRampToValueAtTime(0.0005,t+0.05+0.04*Math.random());
  }
}

// ================= drawing =================
let T={};
function readTokens(){
  const cs=getComputedStyle(document.documentElement);
  for (const k of ["bg","surface","surface-2","ink","muted","line","input","output","free","brass","accent","reverse","danger","ok","sky","hill","road","casing","steel","nitrous"]) T[k]=cs.getPropertyValue("--"+k).trim();
}
readTokens();
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",readTokens);
new MutationObserver(readTokens).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
function hex2rgb(h){ h=h.replace("#",""); if(h.length===3) h=h.split("").map(c=>c+c).join(""); const n=parseInt(h,16); return [n>>16&255,n>>8&255,n&255]; }
function mixc(a,b,u){ const A=hex2rgb(a),B=hex2rgb(b); return `rgb(${A.map((x,i)=>Math.round(x+(B[i]-x)*u)).join(",")})`; }
function shade(c,k){ const A=hex2rgb(c.startsWith("#")?c:"#888"); return `rgb(${A.map(x=>Math.round(clamp(x*k,0,255))).join(",")})`; }

function fitCanvas(cv){
  const dpr=Math.min(2,devicePixelRatio||1), r=cv.getBoundingClientRect();
  const w=Math.max(10,Math.round(r.width*dpr)), h=Math.max(10,Math.round(r.height*dpr));
  if (cv.width!==w||cv.height!==h){ cv.width=w; cv.height=h; }
  return {w,h,dpr};
}
function rr(c,x,y,w,h,r){ c.beginPath(); c.roundRect ? c.roundRect(x,y,w,h,r) : c.rect(x,y,w,h); }

// visual rotation angles (scaled so teeth never strobe)
const VK=0.25/3000;
let A={e:0,i:0,o:0,id:0};
function angles(dt){
  A.e += RPM(S.we)*VK*dt; A.i += RPM(S.wi)*VK*dt; A.o += RPM(S.v/RW*FD)*VK*dt;
  if (S.riSt==="engaged") A.id += -RPM(S.wi)*12/17*VK*dt;
}

function gearCyl(c,x0,w,yc,R,col,ang,N,hel,alpha=1){
  const g=c.createLinearGradient(0,yc-R,0,yc+R);
  g.addColorStop(0,shade(col,0.62)); g.addColorStop(0.3,shade(col,1.08)); g.addColorStop(0.55,col); g.addColorStop(1,shade(col,0.55));
  c.globalAlpha=alpha; c.fillStyle=g; rr(c,x0,yc-R,w,2*R,Math.min(7,w/3)); c.fill();
  if (N){
    c.save(); rr(c,x0,yc-R,w,2*R,Math.min(7,w/3)); c.clip();
    c.lineWidth=1.6;
    for (let i=0;i<N;i++){
      const th=2*Math.PI*(i/N+ang), z=Math.cos(th); if (z<=0.05) continue;
      const y=yc+R*Math.sin(th), dy=hel*z;
      c.strokeStyle=`rgba(20,25,40,${(0.12+0.38*z)*alpha})`;
      c.beginPath(); c.moveTo(x0,y-dy); c.lineTo(x0+w,y+dy); c.stroke();
    }
    c.restore();
  }
  c.lineWidth=2; c.strokeStyle=`rgba(20,25,40,${0.45*alpha})`; rr(c,x0,yc-R,w,2*R,Math.min(7,w/3)); c.stroke();
  c.globalAlpha=1;
}

// cutaway geometry (logical 1000 x 500)
const YI=165, YO=345, D=YO-YI;
const PX={1:[214,40],2:[362,40],3:[432,40],4:[574,40],5:[716,40]};
const UX={A:298,B:503,C:800};
function radii(g){ const [a,b]=Z[g]; return [D*a/(a+b), D*b/(a+b)]; }
const UNIT_OF={}; for (const [k,u] of Object.entries(UNITS)) for (const [sd,g] of Object.entries(u.gears)) UNIT_OF[g]={unit:k, side:+sd};
const onInput = k => UNITS[k].shaft==="in";

function drawBox(){
  const cv=document.getElementById("box"), {w,h}=fitCanvas(cv), c=cv.getContext("2d");
  const sc=w/1040; c.setTransform(sc,0,0,sc,0,0); c.clearRect(0,0,1040,520);
  const eg=engaged(), cl=S.clutch.v, cap=clutchCap();
  // casing
  c.fillStyle=T.casing; rr(c,112,40,800,450,30); c.fill();
  c.strokeStyle=T.line; c.lineWidth=3; rr(c,112,40,800,450,30); c.stroke();
  c.setLineDash([6,6]); c.beginPath(); c.moveTo(690,48); c.lineTo(690,482); c.stroke(); c.setLineDash([]);
  c.font="600 13px Fredoka, Nunito, sans-serif"; c.fillStyle=T.muted; c.textAlign="left";
  if (onInput("C")) c.fillText(CAR.endHousing,700,474); else c.fillText(CAR.endHousing,772,62);
  // engine + clutch
  gearCyl(c,8,30,YI,16,T.steel,-A.e,6,0);
  gearCyl(c,36,24,YI,110,T.steel,-A.e,36,0);
  const dsh=5*cl, psh=10*cl;
  gearCyl(c,62+dsh,9,YI,96,T.input,-A.i,26,0);
  gearCyl(c,74+psh,16,YI,102,T.steel,-A.e,30,0);
  c.fillStyle=T.muted; c.font="600 12px Nunito, sans-serif"; c.textAlign="center";
  c.fillText("engine",48,46); c.fillText("clutch",80,YI+128);
  // slip glow at clutch
  const slip=Math.abs(S.Tc*(S.we-S.wi));
  if (slip>200){ c.fillStyle=`rgba(255,110,60,${clamp(slip/9000,0.1,0.65)})`; rr(c,58+dsh,YI-100,8,200,4); c.fill(); }
  // shafts
  gearCyl(c,64,850,YI,13,T.input,-A.i,8,0);
  gearCyl(c,135,780,YO,14,T.output,A.o,8,0);
  // final drive
  gearCyl(c,150,34,YO,30,T.output,A.o,CAR.fdTeeth[0],3);
  c.save(); rr(c,112,40,800,450,30); c.clip(); gearCyl(c,146,42,YO+30+120,120,T.output,-A.o*CAR.fdTeeth[0]/CAR.fdTeeth[1],CAR.fdTeeth[1],-3); c.restore();
  c.fillStyle=T.muted; c.fillText("to wheels ↓",167,510);
  // reverse train (idler behind)
  const rio=S.ri; const ID_R=(D-13-40-88)/2+6, ID_Y=YI+34+ID_R;
  c.fillStyle=T.steel; rr(c,226,ID_Y-5,130,10,5); c.fill();
  const ix=UX.A-17-42*(1-rio);
  gearCyl(c,ix,32,ID_Y,ID_R,T.reverse,A.id,17,0,0.95);
  if (S.riSt==="blocked") sparks(c,UX.A-6,ID_Y+ID_R);
  // gear pairs
  for (let g=1; g<=5; g++){
    const [x,wd]=PX[g], [rd,rn]=radii(g);
    const e = eg && eg.gear===g ? 1 : 0, looseIn = onInput(UNIT_OF[g].unit);
    if (looseIn){ // loose gear on the input shaft, fixed partner on the output shaft
      gearCyl(c,x,wd,YI,rd,e?T.input:T.free,-A.o*Z[g][1]/Z[g][0],Z[g][0],5);
      gearCyl(c,x,wd,YO,rn,T.output,A.o,Z[g][1],-5);
    } else {
      gearCyl(c,x,wd,YI,rd,T.input,-A.i,Z[g][0],5);
      gearCyl(c,x,wd,YO,rn,e?T.output:T.free,A.i*Z[g][0]/Z[g][1],Z[g][1],-5);
    }
    c.fillStyle=T.input; c.font="700 15px Fredoka, Nunito, sans-serif"; c.textAlign="center";
    c.fillText(g+ordS(g),x+wd/2,YI-rd-8);
  }
  // reverse gear on input
  gearCyl(c,UX.A-16,30,YI,36,T.reverse,-A.i,12,0);
  c.fillStyle=T.reverse; c.font="700 14px Fredoka, Nunito, sans-serif"; c.fillText("R",UX.A-1,YI-44);
  // synchro units
  for (const k of Object.keys(UNITS)){
    const u=S.units[k], cx=UX[k], off=u.s*22, inS=onInput(k);
    const Y = inS ? YI : YO, sc = inS ? 0.74 : 1;            // input-shaft synchros are drawn smaller
    const shaftAng = inS ? -A.i : A.o, shaftCol = inS ? T.input : T.output;
    for (const s of Object.keys(UNITS[k].gears).map(Number)){
      const g=gearOf(k,s), e = eg && eg.gear===g;
      const col=e?shaftCol:T.free;
      const gearAng = inS ? -A.o*Z[g][1]/Z[g][0] : A.i*Z[g][0]/Z[g][1];
      const dx = cx + s*37; gearCyl(c, s<0?dx-13:dx, 13, Y, 74*sc, col, gearAng, 26, 0);
      const pushed = (Math.sign(u.s)===s && Math.abs(u.s)>=0.3) ? 4 : 0;
      const rx = cx + s*(26+pushed); gearCyl(c, s<0?rx-10:rx, 10, Y, 70*sc, T.brass, shaftAng, 22, 0);
      if (S.syncing && S.syncing.unit===k && S.syncing.side===s){
        const gx=cx+s*(37+pushed*0.2);
        const grad=c.createLinearGradient(gx-10,0,gx+10,0);
        grad.addColorStop(0,"rgba(255,90,40,0)"); grad.addColorStop(0.5,`rgba(255,110,50,${0.55+0.3*Math.random()})`); grad.addColorStop(1,"rgba(255,90,40,0)");
        c.fillStyle=grad; c.fillRect(gx-10,Y-80*sc,20,160*sc);
        if (S.grinding>0.05) sparks(c,cx+s*30+off*0.2,Y-84*sc);
      }
    }
    gearCyl(c,cx-17,34,Y,62*sc,shaftCol,shaftAng,20,0);
    const sx=cx-26+off, nT = k==="A"?43:22;
    gearCyl(c,sx,20,Y,82*sc,shaftCol,shaftAng,nT,0);
    gearCyl(c,sx+20,12,Y,70*sc,shade(shaftCol,0.7),shaftAng,18,0);
    gearCyl(c,sx+32,20,Y,82*sc,shaftCol,shaftAng,nT,0);
    // fork (from below for output-shaft sleeves, from above for input-shaft sleeves)
    c.fillStyle=T.steel;
    if (inS){
      rr(c,cx+off-6,0,12,Y-82*sc+6,4); c.fill();
      c.globalAlpha=0.5; rr(c,cx+off-5,Y-82*sc,10,82*sc+6,4); c.fill(); c.globalAlpha=1;
      c.fillStyle=T.ink; c.font="700 12px Nunito, sans-serif"; c.textAlign="center";
      c.fillText(k==="A"?"1/2":k==="B"?"3/4":"5th", cx+off+(k==="C"?0:0), Y+82*sc+16);
    } else {
      rr(c,cx+off-6,Y+76,12,520-(Y+76),4); c.fill();
      c.globalAlpha=0.5; rr(c,cx+off-5,Y-6,10,84,4); c.fill(); c.globalAlpha=1;
      c.fillStyle=T.steel; rr(c,cx+off-34,476,68,10,5); c.fill();
      c.fillStyle=T.ink; c.font="700 12px Nunito, sans-serif"; c.textAlign="center";
      c.fillText(k==="A"?"1/2":k==="B"?"3/4":"5th", cx+off, Y+110);
    }
  }
  // power flow
  const pa=clamp(Math.abs(S.Tc)/25,0,1);
  if (eg && pa>0.05){
    let pts;
    if (eg.gear==="R") pts=[[20,YI],[UX.A,YI],[UX.A,YO],[167,YO],[167,YO+70]];
    else { const [x,wd]=PX[eg.gear], gx=x+wd/2, ux=UX[eg.unit];
      pts = onInput(eg.unit) ? [[20,YI],[ux,YI],[ux,YI+40],[gx,YI+40],[gx,YO],[167,YO],[167,YO+70]]
                             : [[20,YI],[gx,YI],[gx,YO-46],[ux,YO-46],[ux,YO],[167,YO],[167,YO+70]]; }
    flow(c,pts,T.accent,pa);
  } else if (!eg && S.we>5 && cap>20 && Math.abs(S.we-S.wi)<5){
    flow(c,[[20,YI],[700,YI]],T.input,0.6,5);
  }
  // labels
  c.textAlign="left"; c.font="700 13px Fredoka, Nunito, sans-serif";
  c.fillStyle=T.input; c.fillText("INPUT shaft",925,YI+5);
  c.fillStyle=T.output; c.fillText("OUTPUT shaft",925,YO+5);
  c.font="600 11px Nunito, sans-serif"; c.fillStyle=T.muted;
  c.fillText(CAR.inNote,925,YI+21); c.fillText(CAR.outNote,925,YO+21);
  c.fillStyle=T.reverse; c.textAlign="left"; c.fillText("idler",UX.A+18,ID_Y+ID_R+4);
  // status bubble
  let tag=null;
  if (S.grinding>0.05) tag=["GRINDING!",T.danger];
  else if (S.syncing) tag=["synchronising "+S.syncing.gear+ordS(S.syncing.gear)+"…",T.brass];
  else if (eg) tag=[(eg.gear==="R"?"reverse":eg.gear+ordS(eg.gear)+" gear")+" locked", T.output];
  if (tag){ c.font="700 15px Fredoka, Nunito, sans-serif"; const tw=c.measureText(tag[0]).width+22; c.fillStyle=tag[1]; rr(c,520-tw/2,8,tw,26,13); c.fill(); c.fillStyle="#fff"; c.textAlign="center"; c.fillText(tag[0],520,26); }
  if (S.shake>0) S.shake-=1/60;
}
function flow(c,pts,col,a,wd=9){
  c.save(); c.lineJoin="round"; c.lineCap="round";
  c.globalAlpha=0.22*a; c.strokeStyle=col; c.lineWidth=wd+10; c.beginPath(); pts.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p)); c.stroke();
  c.globalAlpha=0.95*a; c.lineWidth=wd; c.setLineDash([16,12]); c.lineDashOffset=-S.time*70; c.beginPath(); pts.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p)); c.stroke();
  c.restore();
}
function sparks(c,x,y){
  if (reduceMotion) { c.fillStyle=T.danger; c.beginPath(); c.arc(x,y,6,0,7); c.fill(); return; }
  for (let i=0;i<10;i++){
    const a=Math.random()*Math.PI*2, r=6+Math.random()*26;
    c.strokeStyle=Math.random()<0.5?"#ffd23f":"#ff6a3d"; c.lineWidth=2;
    c.beginPath(); c.moveTo(x,y); c.lineTo(x+Math.cos(a)*r,y+Math.sin(a)*r); c.stroke();
  }
}

// ---- gauges ----
function gauge(id,val,max,red,label,unit,major,fmt){
  const cv=document.getElementById(id), {w}=fitCanvas(cv), c=cv.getContext("2d");
  const sc=w/200; c.setTransform(sc,0,0,sc,0,0); c.clearRect(0,0,200,200);
  const a0=Math.PI*0.75, a1=Math.PI*2.25, cx=100, cy=104, R=78;
  c.lineCap="round"; c.lineWidth=14; c.strokeStyle=T.line; c.beginPath(); c.arc(cx,cy,R,a0,a1); c.stroke();
  if (red!=null){ c.strokeStyle=T.danger; c.globalAlpha=0.35; c.beginPath(); c.arc(cx,cy,R,a0+(a1-a0)*red/max,a1); c.stroke(); c.globalAlpha=1; }
  const f=clamp(val/max,0,1); const col = red!=null && val>red ? T.danger : T.accent;
  c.strokeStyle=col; c.beginPath(); c.arc(cx,cy,R,a0,a0+(a1-a0)*Math.max(0.0001,f)); c.stroke();
  c.fillStyle=T.muted; c.font="700 11px JetBrains Mono, monospace"; c.textAlign="center"; c.textBaseline="middle";
  for (let m=0;m<=max;m+=major){ const a=a0+(a1-a0)*m/max; c.fillText(fmt(m),cx+Math.cos(a)*(R-24),cy+Math.sin(a)*(R-24)); }
  const a=a0+(a1-a0)*f; c.strokeStyle=T.ink; c.lineWidth=4; c.beginPath(); c.moveTo(cx,cy); c.lineTo(cx+Math.cos(a)*(R-10),cy+Math.sin(a)*(R-10)); c.stroke();
  c.fillStyle=T.ink; c.beginPath(); c.arc(cx,cy,7,0,7); c.fill();
  c.font="700 26px Fredoka, Nunito, sans-serif"; c.fillText(Math.round(val).toLocaleString("en"),cx,cy+44);
  c.font="700 11px Nunito, sans-serif"; c.fillStyle=T.muted; c.fillText(label+" · "+unit,cx,cy+66); c.textBaseline="alphabetic";
}

// ---- car bodies (side view, nose to the right) ----
function drawCarBody(c){
  const col=CAR.colour, edge=CAR.edge, glass=T.sky, B=CAR.shape;
  const P = d => new Path2D(d);
  // wheel arches behind the body
  c.fillStyle="#22262e";
  for (const wx of [-34,34]){ c.beginPath(); c.arc(wx,12,14.5,Math.PI,0); c.fill(); }
  c.lineWidth=1.6; c.strokeStyle=edge; c.fillStyle=col;
  const shell=P(B.shell); c.fill(shell); c.stroke(shell);
  c.fillStyle="#22262e"; for (const wx of [-34,34]){ c.beginPath(); c.arc(wx,12,14.5,Math.PI,0); c.fill(); }
  c.fillStyle=glass; for (const g of B.glass) c.fill(P(g));
  c.strokeStyle=edge; c.lineWidth=1.4; c.stroke(P(B.lines));
  if (B.strip){ c.lineWidth=2.4; c.strokeStyle="rgba(30,34,44,.75)"; c.stroke(P(B.strip)); }
  if (B.tail){ c.fillStyle="#c0392b"; c.fill(P(B.tail)); }
  c.lineWidth=1.4; c.fillStyle="#fff7c2"; c.strokeStyle=edge; const lp=P(B.lamp); c.fill(lp); c.stroke(lp);
  const rev = S.riSt==="engaged"; c.fillStyle = S.brk.v>0.05 ? "#ff3b3b" : rev ? "#ffffff" : "#c0392b";
  rr(c,-60,-9,6,8,2); c.fill();
  // little face on the bonnet: it gets dumber as the gearbox wears
  if (S.health<70) return;   // derpFace() is drawn after the wheels instead
  c.fillStyle=CAR.faceInk; c.beginPath(); c.arc(36,-2,2.2,0,7); c.arc(46,-2,2.2,0,7); c.fill();
  c.strokeStyle=CAR.faceInk; c.lineWidth=1.6; c.beginPath();
  if (S.grinding>0.05||S.time-S.stallT<1.5) { c.moveTo(37,6); c.lineTo(45,6); } else c.arc(41,3,4,0.15*Math.PI,0.85*Math.PI);
  c.stroke();
}
function derpFace(c){
  const wr=wear(), t=S.time, ink=CAR.faceInk, pup="#1f2a3c", wob=reduceMotion?0:Math.sin(t*6)*0.8*wr;
  const eyes=[[34,-3,3.4+wr*2.2,1],[47,-5,2.4+wr*0.8,-1]];        // odd-sized googly eyes, pupils crossed
  for (const [x,y,r,dir] of eyes){
    c.fillStyle="#fff"; c.strokeStyle="#1f2a3c"; c.lineWidth=0.9; c.beginPath(); c.arc(x,y,r,0,7); c.fill(); c.stroke();
    c.strokeStyle=pup; c.fillStyle=pup;
    if (S.health<15){ c.lineWidth=1.3; c.beginPath(); c.moveTo(x-r*0.55,y-r*0.55); c.lineTo(x+r*0.55,y+r*0.55); c.moveTo(x+r*0.55,y-r*0.55); c.lineTo(x-r*0.55,y+r*0.55); c.stroke(); }
    else { c.beginPath(); c.arc(x+dir*r*0.4+wob,y+r*0.3-wob*dir,r*0.45,0,7); c.fill(); }
  }
  // goofy open grin, tongue flopping out once it's really worn
  c.strokeStyle=ink; c.lineWidth=1.8; c.beginPath(); c.moveTo(31,4); c.quadraticCurveTo(39,11+wob,49,3); c.stroke();
  if (S.health<40){ c.fillStyle="#ff6f91"; c.strokeStyle="#c2185b"; c.lineWidth=0.7; c.beginPath(); c.ellipse(43+wob*0.5,10+wr*2.5,2.8,2.4+wr*3,0.2,0,7); c.fill(); c.stroke(); }
  if (S.health<15){ // dazed: stars circling the roof
    c.fillStyle="#ffd23f"; c.strokeStyle="#c98a00"; c.lineWidth=0.6;
    for (let i=0;i<3;i++){ const a=(reduceMotion?0:t*3)+i*2.1, x=Math.cos(a)*16-6, y=-44+Math.sin(a)*4;
      c.beginPath(); for (let k=0;k<10;k++){ const rr2=k%2?1.6:3.8, b=k*Math.PI/5-Math.PI/2; c.lineTo(x+Math.cos(b)*rr2,y+Math.sin(b)*rr2); } c.closePath(); c.fill(); c.stroke(); }
  }
}

// ---- road ----
function drawRoad(){
  const cv=document.getElementById("road"), {w,h,dpr}=fitCanvas(cv), c=cv.getContext("2d");
  const H=132, sc=h/H, W=w/sc; c.setTransform(sc,0,0,sc,0,0);
  c.fillStyle=T.sky; c.fillRect(0,0,W,H);
  const px=S.dist*12; // px per metre
  // hills
  c.fillStyle=T.hill;
  c.beginPath(); c.moveTo(0,H);
  for (let x=0;x<=W+20;x+=20){ const X=x+px*0.15; c.lineTo(x,74-18*Math.sin(X/130)-10*Math.sin(X/47)); }
  c.lineTo(W,H); c.fill();
  // trees
  for (let i=-1;i<W/90+2;i++){
    const base=Math.floor(px*0.55/90)+i, x=base*90-px*0.55;
    const seed=Math.sin(base*12.9898)*43758.5453, rnd=seed-Math.floor(seed);
    if (rnd<0.35) continue;
    c.fillStyle=T.steel; c.fillRect(x+8,70,4,18);
    c.fillStyle=mixc(T.hill.startsWith("#")?T.hill:"#bfe3cf",T.output.startsWith("#")?T.output:"#2fb894",0.45); c.beginPath(); c.arc(x+10,64,10+rnd*6,0,7); c.fill();
  }
  // road
  c.fillStyle=T.road; c.fillRect(0,88,W,44);
  c.fillStyle="rgba(255,255,255,.75)";
  for (let x=-((px)%60); x<W; x+=60) c.fillRect(x,108,30,4);
  // car
  const carX=Math.min(W*0.32,260), carY=96;
  let bob = S.engineOn ? Math.sin(S.time*RPM(S.we)/60*0.5)*0.6 : 0;
  let jx=0, jy=0;
  if (!reduceMotion && (S.grinding>0.05 || S.shake>0)){ jx=(Math.random()-0.5)*3; jy=(Math.random()-0.5)*3; }
  const wr=wear(), silly = (wr>0.3 && !reduceMotion) ? Math.sin(S.time*(3+wr*5))*0.06*wr : 0;   // worn = wobbly
  const pitch = clamp(-(S.lastAcc||0)*0.012,-0.06,0.06) + silly;
  c.save(); c.translate(carX+jx,carY+bob+jy+wr*1.5); c.rotate(pitch);
  // exhaust puffs
  if (S.engineOn && Math.random()<0.15+S.thr.v*0.6) S.puffs.push({x:-58,y:6,r:3,a:0.5});
  if (S.health<40 && (S.engineOn||Math.abs(S.v)>1) && Math.random()<wr*0.5) S.puffs.push({x:6+Math.random()*10,y:8,r:2.5,a:0.45,dark:true}); // smoke from the gearbox
  for (const p of S.puffs){ p.x-=0.6+S.v*0.3; p.y-=0.25; p.r+=0.25; p.a-=0.012; }
  S.puffs=S.puffs.filter(p=>p.a>0).slice(-60);
  for (const p of S.puffs){ c.fillStyle=p.dark?`rgba(70,74,84,${p.a})`:`rgba(160,170,190,${p.a})`; c.beginPath(); c.arc(p.x,p.y,p.r,0,7); c.fill(); }
  if (S.nos.on) nosFlame(c);
  drawCarBody(c);
  // wheels
  const wa=S.dist/RW;
  for (const wx of [-34,34]){ c.fillStyle="#2a2f3a"; c.beginPath(); c.arc(wx,12,12,0,7); c.fill(); c.fillStyle=T.steel; c.beginPath(); c.arc(wx,12,6,0,7); c.fill();
    c.strokeStyle="#2a2f3a"; c.lineWidth=2; c.beginPath(); c.moveTo(wx,12); c.lineTo(wx+Math.cos(wa)*6,12+Math.sin(wa)*6); c.stroke(); }
  if (S.health<70) derpFace(c);   // on top of the front wheel so the tongue can flop over it
  c.restore();
  if (S.nos.on && !reduceMotion){ // speed streaks behind the car
    c.strokeStyle="rgba(255,255,255,.7)"; c.lineWidth=2;
    for (let i=0;i<6;i++){ const y=30+i*11, x=carX-70-((S.time*520+i*97)%(carX+40)); c.beginPath(); c.moveTo(x,y); c.lineTo(x-26-i*3,y); c.stroke(); }
  }
  // overlay text
  const kmh=Math.abs(S.v*3.6), eg=engaged();
  c.fillStyle=T.ink; c.font="700 22px Fredoka, Nunito, sans-serif"; c.textAlign="right";
  c.fillText(kmh.toFixed(0)+" km/h"+(S.v<-0.2?" ◀":""),W-16,30);
  c.font="600 12px Nunito, sans-serif"; c.fillStyle=T.muted;
  c.fillText((S.dist/1000).toFixed(2)+" km driven · "+(eg?(eg.gear==="R"?"reverse":eg.gear+ordS(eg.gear)+" gear"):"neutral"),W-16,48);
}

function nosFlame(c){ // blue-violet nitrous flame from the exhaust (car space, tailpipe at x -58)
  const L = reduceMotion ? 34 : 26+Math.random()*18, w = reduceMotion ? 5 : 4+Math.random()*2.5;
  const g=c.createLinearGradient(-58,0,-58-L,0);
  g.addColorStop(0,"#ffffff"); g.addColorStop(0.25,"#8fdcff"); g.addColorStop(0.65,T.nitrous||"#8a5cff"); g.addColorStop(1,"rgba(138,92,255,0)");
  c.fillStyle=g; c.beginPath(); c.moveTo(-57,6-w); c.quadraticCurveTo(-58-L*0.55,6-w*0.6,-58-L,6); c.quadraticCurveTo(-58-L*0.55,6+w*0.6,-57,6+w); c.closePath(); c.fill();
}

// ---- mascot ----
let faceMoodHold=null, faceHoldT=0;
function drawFace(dt){
  const cv=document.getElementById("face"), c=cv.getContext("2d"); c.setTransform(2,0,0,2,0,0); c.clearRect(0,0,92,92);
  faceHoldT-=dt; if (faceHoldT<0) faceMoodHold=null;
  let mood="smile";
  if (!S.engineOn && S.cranking<=0) mood="sleep";
  if (S.syncing) mood="focus";
  if (S.temp>200) mood="sweat";
  if (Math.abs(S.v*3.6)>90 || S.nos.on) mood="wow";
  if (faceMoodHold) mood=faceMoodHold;
  if (S.time-S.overrevT<2.5) mood="dizzy";
  if (S.grinding>0.05) mood="ouch";
  const cx=46, cy=48, t=S.time;
  // gear body
  c.fillStyle=T.free;
  c.beginPath();
  for (let i=0;i<12;i++){ const a=i/12*Math.PI*2+t*0.15*(S.engineOn?1:0); const a2=a+Math.PI/12;
    c.lineTo(cx+Math.cos(a-0.12)*42,cy+Math.sin(a-0.12)*42); c.lineTo(cx+Math.cos(a+0.12)*42,cy+Math.sin(a+0.12)*42);
    c.lineTo(cx+Math.cos(a2-0.1)*35,cy+Math.sin(a2-0.1)*35); c.lineTo(cx+Math.cos(a2+0.1)*35,cy+Math.sin(a2+0.1)*35); }
  c.closePath(); c.fill();
  c.fillStyle=mixc(T.free.startsWith("#")?T.free:"#f2bf47","#ffffff",0.25); c.beginPath(); c.arc(cx,cy,30,0,7); c.fill();
  c.fillStyle="#ff9aa2"; c.globalAlpha=0.55; c.beginPath(); c.arc(cx-17,cy+8,5,0,7); c.arc(cx+17,cy+8,5,0,7); c.fill(); c.globalAlpha=1;
  c.strokeStyle="#1f2a3c"; c.fillStyle="#1f2a3c"; c.lineWidth=2.6; c.lineCap="round";
  const eye=(x,y)=>{
    if (mood==="sleep"||mood==="happy"){ c.beginPath(); c.arc(x,y+1,4,Math.PI*1.1,Math.PI*1.9,false); c.stroke(); }
    else if (mood==="ouch"){ c.beginPath(); c.moveTo(x-4,y-3); c.lineTo(x+3,y); c.lineTo(x-4,y+3); c.stroke(); }
    else if (mood==="dizzy"){ c.beginPath(); for(let k=0;k<14;k++){ const a=k*0.8+t*8, r=k*0.38; c.lineTo(x+Math.cos(a)*r,y+Math.sin(a)*r);} c.stroke(); }
    else if (mood==="wow"){ c.beginPath(); c.arc(x,y,4.5,0,7); c.fill(); c.fillStyle="#fff"; c.beginPath(); c.arc(x+1.5,y-1.5,1.5,0,7); c.fill(); c.fillStyle="#1f2a3c"; }
    else { const blink = (t%3.2)<0.12; if (blink){ c.beginPath(); c.moveTo(x-3,y); c.lineTo(x+3,y); c.stroke(); } else { c.beginPath(); c.arc(x,y,3.4,0,7); c.fill(); } }
  };
  if (mood==="ouch"){ c.beginPath(); c.moveTo(cx+18-4,cy-6-3); c.lineTo(cx+18-11,cy-6); c.lineTo(cx+18-4,cy-6+3); c.stroke(); eye(cx-11,cy-6); }
  else { eye(cx-11,cy-6); eye(cx+11,cy-6); }
  c.beginPath();
  if (mood==="smile"||mood==="happy") c.arc(cx,cy+5,8,0.15*Math.PI,0.85*Math.PI);
  else if (mood==="focus"){ c.moveTo(cx-5,cy+10); c.lineTo(cx+5,cy+10); }
  else if (mood==="ouch"){ c.moveTo(cx-8,cy+12); for(let k=0;k<5;k++) c.lineTo(cx-8+4*(k+1),cy+(k%2?12:8)); }
  else if (mood==="sleep"){ c.arc(cx,cy+11,3,0,7); }
  else if (mood==="dizzy"){ c.moveTo(cx-7,cy+11); c.quadraticCurveTo(cx,cy+5,cx+7,cy+11); }
  else if (mood==="wow"){ c.arc(cx,cy+11,5,0,7); }
  else if (mood==="sweat"){ c.moveTo(cx-6,cy+11); c.lineTo(cx+6,cy+11); }
  c.stroke();
  if (mood==="sleep"){ c.fillStyle=T.muted; c.font="700 12px Fredoka, sans-serif"; c.fillText("z",cx+28,cy-24+Math.sin(t*2)*2); c.font="700 9px Fredoka, sans-serif"; c.fillText("z",cx+36,cy-34+Math.sin(t*2+1)*2); }
  if (mood==="sweat"||mood==="focus"){ c.fillStyle="#7cc4ff"; c.beginPath(); c.moveTo(cx+26,cy-20); c.quadraticCurveTo(cx+31,cy-11,cx+26,cy-9); c.quadraticCurveTo(cx+21,cy-11,cx+26,cy-20); c.fill(); }
}

// ---- side panel text ----
const el=id=>document.getElementById(id);
function panelUI(){
  const eg=engaged(), cap=clutchCap(), slip=Math.abs(S.we-S.wi);
  el("gearTxt").textContent = eg ? String(eg.gear) : "N";
  if (el("gearMini")) el("gearMini").textContent = eg ? String(eg.gear) : "N";
  let cs = S.clutch.v>0.75 ? "disengaged" : cap>1 && slip>RAD(40) ? "slipping" : "engaged";
  el("vClutch").textContent = cs+" · "+Math.round(cap)+" N·m";
  el("chipClutch").classList.toggle("warn", cs==="slipping" && slip>RAD(800));
  let sy="idle";
  if (S.grinding>0.05) sy="GRINDING";
  else if (S.syncing) sy="syncing "+S.syncing.gear+ordS(S.syncing.gear)+" · Δ"+Math.round(Math.abs(RPM(S.syncing.diff)))+" rpm";
  else if (eg) sy=(eg.gear==="R"?"reverse idler":"locked "+eg.gear+ordS(eg.gear));
  el("vSync").textContent=sy; el("chipSync").classList.toggle("warn",S.grinding>0.05);
  el("vShafts").textContent=Math.round(RPM(S.wi)).toLocaleString("en")+" / "+Math.round(RPM(S.v/RW*FD)).toLocaleString("en")+" rpm";
  el("vTemp").textContent=Math.round(S.temp)+" °C"; el("chipTemp").classList.toggle("warn",S.temp>200);
  el("vHealth").textContent=Math.round(S.health)+" %"; el("healthBar").style.width=S.health+"%";
  el("healthBar").style.background = S.health>60?"var(--ok)":S.health>30?"var(--free)":"var(--danger)";
  if (nosBtn){ nosFill.style.width=(S.nos.lvl*100)+"%"; nosBtn.classList.toggle("on",S.nos.on); nosBtn.setAttribute("aria-pressed",String(S.nos.on)); }
  const on=S.engineOn||S.cranking>0;
  startTxt.textContent = on ? "Stop engine" : "Start engine";
  startBtn.classList.toggle("off", on); engDot.classList.toggle("on", S.engineOn);
}

// ================= main loop =================
let last=performance.now(), prevV=0;
function frame(now){
  let dt=Math.min(0.05,(now-last)/1000); last=now;
  pedalKeys(dt); leverStep(dt);
  const N=10, h=dt/N;
  for (let i=0;i<N;i++) physics(h);
  S.lastAcc = (S.v-prevV)/Math.max(dt,1e-3); prevV=S.v;
  monitors(dt); angles(dt);
  try{ drawRoad(); drawBox(); gauge("tacho",RPM(S.we),7000,LIMIT,"engine","rpm",1000,m=>m/1000); gauge("speedo",Math.abs(S.v*3.6),180,null,"speed","km/h",30,m=>m); drawFace(dt); }catch(e){ console.error(e); }
  pedalUI(); leverUI(); panelUI(); audioTick();
  requestAnimationFrame(frame);
}
{ const h=document.getElementById("revHint"); if (h) h.textContent=CAR.revHint; }
requestAnimationFrame(frame);
})();
