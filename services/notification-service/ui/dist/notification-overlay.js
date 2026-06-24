"use strict";(()=>{var f={info:"#2563eb",warning:"#d97706",success:"#16a34a"};function p(i,n){return`${i.replace(/^http/,"ws")}/notifications/ws?access_token=${encodeURIComponent(n)}`}function m(i){let n;try{n=JSON.parse(i)}catch{return null}if(typeof n!="object"||n===null)return null;let{severity:t,title:e,body:o,scope:s}=n;if(t!=="info"&&t!=="warning"&&t!=="success"||typeof e!="string"||typeof o!="string")return null;let r={severity:t,title:e,body:o};if(s!==void 0){if(typeof s!="object"||s===null)return null;let{axis:a,value:c}=s;if(typeof a!="string"||typeof c!="string")return null;r.scope={axis:a,value:c}}return r}function b(i){return S[i]}var S={info:[{freq:784,startMs:0,durationMs:220}],warning:[{freq:600,startMs:0,durationMs:160},{freq:600,startMs:190,durationMs:160}],success:[{freq:523,startMs:0,durationMs:150},{freq:659,startMs:150,durationMs:150},{freq:784,startMs:300,durationMs:150},{freq:1047,startMs:450,durationMs:260}]},x=.34,l=class{constructor(n=document){this.target=n,this.target.addEventListener("click",()=>this.unlock(),{once:!0})}unlock(){try{this.ctx??(this.ctx=new AudioContext),this.ctx.resume()}catch{}}play(n){let t=this.ctx;if(!t||t.state!=="running")return;let e=t.currentTime;for(let o of b(n)){let s=t.createOscillator(),r=t.createGain();s.type="triangle",s.frequency.value=o.freq;let a=e+o.startMs/1e3,c=a+o.durationMs/1e3;r.gain.setValueAtTime(1e-4,a),r.gain.exponentialRampToValueAtTime(x,a+.01),r.gain.exponentialRampToValueAtTime(1e-4,c),s.connect(r).connect(t.destination),s.start(a),s.stop(c+.02)}}};function h(i,n){let t=i.scope;return t?n==null?!1:t.value===n:!0}function g(i,n=window){return n.__praimSelections?.[i]}function T(i,n=window){let t=g(i,n);return t!==void 0?t:i==="workshop"?n.__praimActiveWorkshop:void 0}function v(i,n=window){let t=T(i,n);return t==null?t:typeof t=="object"&&"poiId"in t?String(t.poiId):String(t)}var k=5e3,u=320,d=class extends HTMLElement{constructor(){super();this.audio=new l;this.closing=!1;this.backoffMs=0;this.root=this.attachShadow({mode:"open"})}static get observedAttributes(){return["token","base"]}connectedCallback(){this.root.innerHTML=`
            <style>
                :host { display: contents; }
                .stack {
                    /* Top aligned just below where the dashboard widgets start (the
                       4rem navbar + the page header bar), same right edge as before. */
                    position: fixed; top: 8.25rem; right: 1rem; z-index: 2147483647;
                    display: flex; flex-direction: column; gap: .75rem;
                    pointer-events: none; font-family: system-ui, sans-serif;
                }
                .toast {
                    pointer-events: auto; position: relative;
                    min-width: 22rem; max-width: 30rem;
                    color: #fff; border-radius: .75rem; padding: 1.1rem 1.4rem;
                    box-shadow: 0 6px 18px rgba(0,0,0,.28);
                    /* Fade + slide: starts hidden, .show fades it in, .hide fades it
                       out (TTL or the X). Duration mirrors TOAST_FADE_MS. */
                    opacity: 0; transform: translateX(.75rem);
                    transition: opacity ${u}ms ease, transform ${u}ms ease;
                }
                .toast.show { opacity: 1; transform: translateX(0); }
                .toast.hide { opacity: 0; transform: translateX(.75rem); }
                .toast .close {
                    /* A round badge straddling the top-left corner (half outside the
                       box), like a messaging-app dismiss bubble \u2014 not a button inside. */
                    position: absolute; top: -.7rem; left: -.7rem;
                    width: 1.85rem; height: 1.85rem; padding: 0;
                    display: flex; align-items: center; justify-content: center;
                    background: #fff; color: #334155; border: 0; border-radius: 50%;
                    box-shadow: 0 1px 5px rgba(0,0,0,.35);
                    font-size: 1.3rem; line-height: 1; cursor: pointer;
                    opacity: .95; transition: transform .12s ease;
                }
                .toast .close:hover { opacity: 1; transform: scale(1.12); }
                .toast .title { font-weight: 600; font-size: 1.2rem; }
                .toast .body { font-size: 1.05rem; opacity: .95; margin-top: .3rem; }
            </style>
            <div class="stack" role="status" aria-live="polite"></div>
        `,this.toasts=this.root.querySelector(".stack"),this.connect()}disconnectedCallback(){this.closing=!0,this.reconnectTimer!==void 0&&clearTimeout(this.reconnectTimer),this.socket?.close()}attributeChangedCallback(){this.isConnected&&this.connect()}connect(){let t=this.getAttribute("token")??"",e=this.getAttribute("base")||window.location.origin;this.reconnectTimer!==void 0&&clearTimeout(this.reconnectTimer),this.socket&&(this.closing=!0,this.socket.close()),this.closing=!1,this.socket=new WebSocket(p(e,t)),this.socket.addEventListener("open",()=>{this.backoffMs=0}),this.socket.addEventListener("message",o=>this.onMessage(o)),this.socket.addEventListener("close",()=>this.scheduleReconnect())}scheduleReconnect(){if(this.closing)return;let t=500,e=1e4;this.backoffMs=Math.min(this.backoffMs?this.backoffMs*2:t,e);let o=Math.random()*(this.backoffMs/2);this.reconnectTimer=setTimeout(()=>this.connect(),this.backoffMs+o)}onMessage(t){let e=m(String(t.data));if(!e)return;let o=e.scope?v(e.scope.axis):void 0;h(e,o)&&(this.renderToast(e),this.audio.play(e.severity))}renderToast(t){let e=document.createElement("div");e.className="toast",e.style.background=f[t.severity];let o=document.createElement("button");o.className="close",o.type="button",o.setAttribute("aria-label","Chiudi notifica"),o.textContent="\xD7";let s=document.createElement("div");s.className="title",s.textContent=t.title;let r=document.createElement("div");r.className="body",r.textContent=t.body,e.append(o,s,r),this.toasts.append(e),requestAnimationFrame(()=>e.classList.add("show"));let a=!1,c=()=>{a||(a=!0,clearTimeout(y),e.classList.remove("show"),e.classList.add("hide"),setTimeout(()=>e.remove(),u))};o.addEventListener("click",c);let y=setTimeout(c,k)}};customElements.get("notification-overlay")||customElements.define("notification-overlay",d);})();
