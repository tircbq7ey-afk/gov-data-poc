// =========================
// VisaNavi: script.js 完全版
//  - 既存の会員確認/Stripe導線を維持
//  - 127.0.0.1/localhost では会員確認を自動スキップ
//  - ローカル: Flask(8000)の /ping /ask を使用（GET）
//  - 本番: Netlify Functions の /.netlify/functions/ask 等を使用（POST）
// =========================

// ←←← 本番の Payment Link に差し替えてください（既存値を踏襲）
const PAYMENT_LINK = "https://buy.stripe.com/bJe7sM4GO1HWgic4CS3VC02";

// 会員判定キャッシュ（ミリ秒）
const MEMBER_CACHE_TTL = 1000 * 60 * 60 * 6;

// DOM util
const $ = (id) => document.getElementById(id);
const answerBox = $("answer");
const langSelect = $("lang-select");
function setAnswer(html){ if (answerBox) answerBox.innerHTML = html; }
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

// ======== 環境自動判定（ローカル開発 or 本番） ========
const DEV = ["127.0.0.1","localhost"].includes(location.hostname);
const API_BASE = DEV ? "http://127.0.0.1:8000" : "/.netlify/functions";

// ローカル: GET /ask?q=...&k=...&lang=..
// 本番   : POST /.netlify/functions/ask {question, lang, email}
async function callAskAPI(question, lang, email){
  if (DEV){
    const k = 3; // 上位3件（必要なら調整）
    const url = `${API_BASE}/ask?q=${encodeURIComponent(question)}&k=${k}&lang=${encodeURIComponent(lang)}`;
    const res = await fetch(url);
    const text = await res.text();
    let json = {};
    try{ json = JSON.parse(text); }catch{ throw new Error(text || "invalid json"); }
    // Flask 版の戻り: { ok, count, results:[{rank, score, source_path, source_url, text, title}] }
    return renderFromResults(json);
  }else{
    const res = await fetch(`${API_BASE}/ask`,{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      credentials:"include",
      body: JSON.stringify({ question, lang, email })
    });
    const text = await res.text();
    let json = {};
    try{ json = JSON.parse(text); }catch{ throw new Error(text || "invalid json"); }
    // Netlify 版の戻り: { answer, sources:[{title,url}] } を想定
    return renderFromAnswer(json);
  }
}

function renderFromResults(data){
  if (!data || !Array.isArray(data.results) || !data.results.length){
    return "該当が見つかりませんでした。";
  }
  const rows = data.results
    .sort((a,b) => (a.rank||0)-(b.rank||0))
    .map(r=>{
      const title = r.title || (r.source_path ? r.source_path.split(/[\\/]/).pop() : "出典");
      // source_url があれば優先
      const link = r.source_url || r.source_path || "";
      const a = link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(title)}</a>` : esc(title);
      const score = (typeof r.score === "number") ? ` (score: ${r.score.toFixed(3)})` : "";
      const text = r.text ? `<div style="margin-top:4px">${esc(r.text)}</div>` : "";
      return `<li><strong>#${r.rank||"-"}</strong> ${a}${score}${text}</li>`;
    })
    .join("");
  return `<ol>${rows}</ol>`;
}

function renderFromAnswer(data){
  const ans = (data && data.answer || "").trim();
  const html = ans ? esc(ans).replace(/\n/g,"<br>") : "回答が取得できませんでした。";
  let refs = "";
  if (data && Array.isArray(data.sources) && data.sources.length){
    refs = `<div style="margin-top:.75rem;font-size:.9em;color:#555">
              参考: ${data.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title||"出典")}</a>`).join(" / ")}
            </div>`;
  }
  return html + refs;
}

// ======== Cookie / LocalStorage util（既存の方針を踏襲） ========
function getCookie(name){
  const m = (document.cookie || "").split("; ").find(v=>v.startsWith(name+"="));
  if (!m) return "";
  try { return decodeURIComponent(m.split("=")[1]); } catch { return ""; }
}
function setCookie(name, value, maxAgeSec){
  const parts = [`${name}=${encodeURIComponent(value)}`, "Path=/", "SameSite=Lax"];
  if (maxAgeSec) parts.push(`Max-Age=${maxAgeSec}`);
  document.cookie = parts.join("; ");
}
function dropParams(keys){
  const u = new URL(location.href);
  let changed = false;
  keys.forEach(k => { if (u.searchParams.has(k)){ u.searchParams.delete(k); changed = true; } });
  if (changed){
    const clean = u.pathname + (u.search ? "?"+u.searchParams.toString() : "");
    history.replaceState({}, "", clean);
  }
}
function getSavedEmail(){
  const cookieMail = getCookie("user_email");
  if (cookieMail) return cookieMail;
  const p = new URLSearchParams(location.search);
  return localStorage.getItem("user_email") || p.get("email") || "";
}
function saveEmail(e){ if(e) localStorage.setItem("user_email", e); }

// ======== 会員キャッシュ（既存踏襲） ========
function readMemberCache(){
  try{ return JSON.parse(localStorage.getItem("member_cache")||"null"); }
  catch{ return null; }
}
function writeMemberCache(email, ok, reason){
  localStorage.setItem("member_cache", JSON.stringify({
    email, ok, reason: reason||"", exp: Date.now() + MEMBER_CACHE_TTL
  }));
}

// ======== Stripe戻り検証（本番のみ使われる想定） ========
async function verifyStripeOnReturn(){
  if (DEV) return; // ローカルはスキップ
  const p = new URLSearchParams(location.search);
  const sid   = p.get("session_id");
  const mailP = p.get("email") || "";
  if (!sid) return;

  try{
    setAnswer("決済を確認中です…");
    const url = "/.netlify/functions/stripe-verify?session_id=" + encodeURIComponent(sid)
              + (mailP ? "&email=" + encodeURIComponent(mailP) : "");
    const r = await fetch(url, { credentials: "include" });
    const text = await r.text();
    let j = {}; try{ j = JSON.parse(text); }catch(_){}
    if (r.ok && j.ok){
      const email = j.email || j.customer_email || mailP || getSavedEmail() || "";
      if (email){
        saveEmail(email);
        writeMemberCache(email, true, "paid");
      }
      dropParams(["session_id","email"]);
      setAnswer('お支払いありがとうございます。会員状態を更新しました。<br>フォームからご質問ください。');
    } else {
      setAnswer("決済の確認に失敗しました。ページを更新して再試行してください。");
    }
  }catch{
    setAnswer("決済確認でエラーが発生しました。しばらくしてから再試しください。");
  }
}

// ======== 会員チェック（本番のみ） ========
async function checkMember(email){
  if (DEV) return { ok:true, reason:"dev" }; // ローカルは常にOK
  const r = await fetch("/.netlify/functions/check-member?email="+encodeURIComponent(email), { credentials: "include" });
  const j = await r.json().catch(()=>({ok:false,reason:"error"}));
  writeMemberCache(email, !!j.ok, j.reason||"");
  return { ok: !!j.ok, reason: j.reason||"" };
}

async function ensureActive(){
  if (DEV) return { ok:true, email:"dev@example.com" }; // ローカルはスキップ

  const cookieMail = getCookie("user_email");
  if (cookieMail) saveEmail(cookieMail);

  let email = getSavedEmail();
  if (!email) email = prompt("ご登録のメールアドレスを入力してください（有料会員確認）");
  if (!email){
    setAnswer(`メールの入力が必要です。<a href="${PAYMENT_LINK}" target="_blank" rel="noopener">こちら</a>からご登録ください。`);
    return { ok:false };
  }
  saveEmail(email);

  try{
    const { ok, reason } = await checkMember(email);
    if (ok) return { ok:true, email };
    if (reason === "inactive"){
      setAnswer('ご契約の状態がアクティブではありません。<br>' +
                `再登録は <a href="${PAYMENT_LINK}" target="_blank" rel="noopener">こちら</a> からお願いします。`);
    } else {
      setAnswer('この機能は有料会員向けです。<br>' +
                `ご登録は <a href="${PAYMENT_LINK}" target="_blank" rel="noopener">こちら</a> からお願いします。`);
    }
    return { ok:false };
  } catch{
    setAnswer("会員確認でエラーが発生しました。時間をおいて再試しください。");
    return { ok:false };
  }
}

// ======== 送信ハンドラ ========
let sending = false;
async function handleSubmit(e){
  if (e){ e.preventDefault(); e.stopPropagation(); }
  if (sending) return;
  sending = true;

  const inputQuestion = $("question");
  const { ok, email } = await ensureActive();
  if (!ok){ sending = false; return; }

  const question = (inputQuestion?.value || "").trim();
  const lang = (langSelect && langSelect.value) ? langSelect.value : "JP";
  if (!question){
    setAnswer("質問を入力してください。");
    sending = false; return;
  }

  try{
    setAnswer("送信中…");
    const html = await callAskAPI(question, lang, email);
    setAnswer(html);
  }catch(err){
    console.error(err);
    setAnswer("通信に失敗しました。回線状況と API の起動状態をご確認ください。");
  }finally{
    sending = false;
  }
}

// ======== API 接続テスト（任意） ========
async function pingTest(){
  try{
    const url = DEV ? `${API_BASE}/ping` : "/.netlify/functions/ping";
    const r = await fetch(url);
    const j = await r.json();
    setAnswer(`API 接続: ${j && j.ok ? "OK" : "NG"}`);
  }catch{
    setAnswer("API 接続に失敗しました。");
  }
}
const testBtn = document.getElementById("api-test");
if (testBtn) testBtn.addEventListener("click", pingTest);

// ======== 初期化 ========
function attachSubmitHandler(){
  const form = $("faq-form");
  if (!form) return false;
  try { form.setAttribute("action",""); } catch {}
  form.removeEventListener("submit", handleSubmit);
  form.addEventListener("submit", handleSubmit);
  return true;
}
function initWhenReady(){
  verifyStripeOnReturn(); // 本番時のみ有効
  if (attachSubmitHandler()) return;
  const timer = setInterval(() => { if (attachSubmitHandler()) clearInterval(timer); }, 200);
  setTimeout(()=>clearInterval(timer), 10000);
}
if (document.readyState === "loading"){
  document.addEventListener("DOMContentLoaded", initWhenReady);
}else{
  initWhenReady();
}

// デバッグ/補助（既存の補助も維持）
window.clearSavedEmail = function(){
  localStorage.removeItem("user_email");
  localStorage.removeItem("member_cache");
  setCookie("user_email", "", 1);
  setCookie("paid", "", 1);
  alert("保存されたメール/Cookie情報を削除しました。再読み込みしてください。");
};
