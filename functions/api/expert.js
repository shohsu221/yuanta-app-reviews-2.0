const EXPERT_HTML = "<!-- 🎯 Strategic Opportunity Card -->\n        <div class=\"glass-card rounded-2xl p-6 relative overflow-hidden border-l-4 border-amber-500\">\n            <div class=\"absolute -right-8 -top-8 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl\"></div>\n            <div class=\"flex items-center gap-3 mb-3\">\n                <span class=\"text-2xl\">🎯</span>\n                <h3 class=\"font-extrabold text-lg text-amber-300\">元大證券「投資先生」核心戰略與競爭機會</h3>\n            </div>\n            <p class=\"text-sm text-gray-300 leading-relaxed\">\n                基於 1240 則真實用戶評論分析，當前台灣證券 App 市場正處於<strong>「體驗退化與效能硬傷」</strong>的焦土戰。\n                在競品<strong>「國泰開盤常態性當機（大樹守衛）」</strong>與<strong>「永豐嚴重過熱耗電（練鐵砂掌）」</strong>的背景下，元大若能迅速還原 UI 細節、優化開戶本地快取防呆、並強力主打高階交易者渴求的獨家「指定沖銷庫存」功能，將可強力收割對競品極度失望的中高頻交易者。\n            </p>\n        </div>\n\n        <!-- 👥 Three Experts Section -->\n        <div class=\"grid grid-cols-1 md:grid-cols-3 gap-5\">\n            <!-- UX Researcher -->\n            <div class=\"glass-card rounded-2xl p-5 border-t-4 border-blue-500 relative\">\n                <div class=\"flex items-center gap-3 mb-3\">\n                    <div class=\"w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center font-bold text-blue-400\">UX</div>\n                    <div>\n                        <h4 class=\"font-bold text-sm text-gray-200\">UX Researcher</h4>\n                        <span class=\"text-[10px] tag-blue px-2 py-0.5 rounded-full font-semibold\">質性體驗專家</span>\n                    </div>\n                </div>\n                <p class=\"text-xs text-gray-400 leading-relaxed\">\n                    專注於用戶體驗摩擦力。指出元大 K 線手勢衝突修復後，4.17.0 的字體與動線問題延續到 4.18.x 的登入、持有成本、閃電下單鎖定與開戶補件摩擦；國泰當機與下單延遲引發用戶焦慮；永豐則在介面細節、耗電與開盤穩定度間拉扯。\n                </p>\n            </div>\n            <!-- Applied Scientist -->\n            <div class=\"glass-card rounded-2xl p-5 border-t-4 border-emerald-500 relative\">\n                <div class=\"flex items-center gap-3 mb-3\">\n                    <div class=\"w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center font-bold text-emerald-400\">AS</div>\n                    <div>\n                        <h4 class=\"font-bold text-sm text-gray-200\">Applied Scientist</h4>\n                        <span class=\"text-[10px] tag-green px-2 py-0.5 rounded-full font-semibold\">定量與數據科學家</span>\n                    </div>\n                </div>\n                <p class=\"text-xs text-gray-400 leading-relaxed\">\n                    專注於系統穩定度與數據架構。分析國泰與永豐開盤 API 卡頓；元大 4.18.x 新增登入、開戶自拍補件、持有成本顯示與閃電下單鎖定問題，顯示交易狀態、Session 與帳務資料同步仍需治理；建議開戶增加暫存防呆，並優化前端渲染與交易狀態回復。\n                </p>\n            </div>\n            <!-- Marketing Strategist -->\n            <div class=\"glass-card rounded-2xl p-5 border-t-4 border-amber-500 relative\">\n                <div class=\"flex items-center gap-3 mb-3\">\n                    <div class=\"w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center font-bold text-amber-400\">MS</div>\n                    <div>\n                        <h4 class=\"font-bold text-sm text-gray-200\">Marketing Strategist</h4>\n                        <span class=\"text-[10px] tag-amber px-2 py-0.5 rounded-full font-semibold\">行銷策略專家</span>\n                    </div>\n                </div>\n                <p class=\"text-xs text-gray-400 leading-relaxed\">\n                    專注市場定位與增長策略。主張元大應避開手續費價格戰，強打「穩定第一」定位；建議強打既有的「指定庫存沖銷」優勢與推出「美股 DRIP」以差異化精準收割競品流失的高階、高頻交易客戶。\n                </p>\n            </div>\n        </div>\n\n        <!-- 💬 Collaborative Debate Board -->\n        <div class=\"glass-card rounded-2xl p-6\">\n            <h3 class=\"font-bold text-base text-gray-100 mb-4 flex items-center gap-2\">\n                <span>💬</span> 三專家聯席討論與決策紀要 (Expert Collaborative Debate)\n            </h3>\n            \n            <div class=\"space-y-4 max-h-[500px] overflow-y-auto pr-2\">\n                <!-- Dialogue 1: UXR -->\n                <div class=\"flex items-start gap-3 interactive-card p-2 -ml-2 rounded-xl\" onclick=\"showReviewSource('expert-uxr')\" title=\"點擊查看專業術語解釋\">\n                    <div class=\"w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold text-xs text-white shrink-0\">UX</div>\n                    <div class=\"bg-blue-950/20 border border-blue-500/10 rounded-xl p-3.5 max-w-3xl\">\n                        <div class=\"flex items-center gap-2 mb-1.5\">\n                            <span class=\"text-xs font-bold text-blue-300\">UX Researcher</span>\n                            <span class=\"text-[10px] text-gray-500\">11:05</span>\n                        </div>\n                        <p class=\"text-xs text-gray-300 leading-relaxed\">\n                            「元大 Q1 手勢衝突 Bug 修復後，Q2 沒有真正形成口碑反彈；4.17.0 的庫存圓餅圖字體與動線異動，加上 4.18.x 的登入、持有成本、閃電下單鎖定與開戶自拍補件問題，讓使用者感覺核心任務仍被打斷。\n                            再看競品國泰證券，大跌時伺服器必當機，被股民嘲諷為『大樹守衛守護你的資產』（想賣卻賣不掉）。這種在用戶面臨現金流失時的極度焦慮，會徹底摧毀品牌信任。我們絕不能重蹈覆轍。」\n                        </p>\n                    </div>\n                </div>\n\n                <!-- Dialogue 2: AS -->\n                <div class=\"flex items-start gap-3 interactive-card p-2 -ml-2 rounded-xl\" onclick=\"showReviewSource('expert-as')\" title=\"點擊查看專業術語解釋\">\n                    <div class=\"w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center font-bold text-xs text-white shrink-0\">AS</div>\n                    <div class=\"bg-emerald-950/20 border border-emerald-500/10 rounded-xl p-3.5 max-w-3xl\">\n                        <div class=\"flex items-center gap-2 mb-1.5\">\n                            <span class=\"text-xs font-bold text-emerald-300\">Applied Scientist</span>\n                            <span class=\"text-[10px] text-gray-500\">11:07</span>\n                        </div>\n                        <p class=\"text-xs text-gray-300 leading-relaxed\">\n                            「從數據來看，國泰與永豐都在 9:00 開盤高峰期卡死，元大 4.18.x 則出現登入、身分驗證補件、持有成本顯示與閃電下單鎖定狀態無法保持等相容性與狀態同步異常。這通常是負載平衡與 Heartbeat 心跳設置異常。我們必須擴容伺服器並放寬 Session 自動登出時限。\n                            另外，永豐大戶投的『發燙練鐵砂掌』在 iOS 設備上非常嚴重，這通常是因為前端數據監聽未做 Throttling，導致 CPU 高負載。我們投資先生必須優化前端 WebGL 渲染以防燙手。最後，針對 Android 開戶切換 App 就遺失表單的 Bug，我建議引進本地 `Local Storage` 快取草稿機制，防止開戶漏斗轉化率的嚴重 Drop-off。」\n                        </p>\n                    </div>\n                </div>\n\n                <!-- Dialogue 3: MS -->\n                <div class=\"flex items-start gap-3 interactive-card p-2 -ml-2 rounded-xl\" onclick=\"showReviewSource('expert-ms')\" title=\"點擊查看專業術語解釋\">\n                    <div class=\"w-8 h-8 rounded-full bg-amber-500 flex items-center justify-center font-bold text-xs text-white shrink-0\">MS</div>\n                    <div class=\"bg-amber-950/20 border border-amber-500/10 rounded-xl p-3.5 max-w-3xl\">\n                        <div class=\"flex items-center gap-2 mb-1.5\">\n                            <span class=\"text-xs font-bold text-amber-300\">Marketing Strategist</span>\n                            <span class=\"text-[10px] text-gray-500\">11:10</span>\n                        </div>\n                        <p class=\"text-xs text-gray-300 leading-relaxed\">\n                            「國泰用戶說得好：『手續費再便宜，當機賣不掉有屁用！』這給了元大極佳的定位切入點！我們不需要跟國泰打價格血戰，我們要把投資先生包裝為『穩定安全、關鍵時刻絕不掉鏈』的首選工具。\n                            但支撐這個定位的前提是修復 4.18.x 版的登入、持有成本、閃電下單與開戶補件路徑。同時，針對國泰與永豐用戶都在強烈許願的『庫存指定沖銷功能』（即擁有多張股票時指定賣出高成本者以利節稅），元大投資先生早已具備此功能，若能將此既有優勢包裝強打，將會成為吸引中高頻投資人的行銷王牌！」\n                        </p>\n                    </div>\n                </div>\n            </div>\n        </div>\n\n        <!-- 📊 Deep-Dive Comparison Matrix -->\n        <div class=\"glass-card rounded-2xl p-6 overflow-hidden\">\n            <h3 class=\"font-bold text-base text-gray-100 mb-4 flex items-center gap-2\">\n                <span>📊</span> 三大平台深度對比矩陣 (Competitive Matrix)\n            </h3>\n            <div class=\"overflow-x-auto\">\n                <table class=\"w-full text-left border-collapse\">\n                    <thead>\n                        <tr class=\"border-b border-gray-800 text-gray-400 text-xs\">\n                            <th class=\"py-3 px-4\">對比維度</th>\n                            <th class=\"py-3 px-4 text-blue-400\">元大證券「投資先生」</th>\n                            <th class=\"py-3 px-4 text-rose-400\">國泰證券 App</th>\n                            <th class=\"py-3 px-4 text-amber-400\">永豐大戶投 App</th>\n                        </tr>\n                    </thead>\n                    <tbody class=\"text-xs divide-y divide-gray-800/50\">\n                        <tr>\n                            <td class=\"py-3 px-4 font-bold text-gray-300\">開戶引導 (Onboarding)</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🔴 Android 切換 App 查資料時進度易遭系統清理，無資料暫存防呆，且不支援 PDF 上傳。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🔴 複委託加開上傳介面極度難用，開戶審查速度慢。但新股申購流程順暢。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🔴 線上開戶審查超慢（有用戶投訴 17 天還在審查中），偶爾卡在自動跳轉。</td>\n                        </tr>\n                        <tr>\n                            <td class=\"py-3 px-4 font-bold text-gray-300\">核心交易 (Core UI/UX)</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟡 技術指標豐富。<br>🔴 4.17.0 圓餅圖字體與動線異動；4.18.x 登入、持有成本、開戶補件與閃電下單鎖定狀態引發新負評。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟡 介面乾淨清晰。<br>🔴 K線跨度不好調整，沒有個股筆記，且無智慧下單改價功能（需刪單重下）。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟢 <strong>大優勢</strong>：介面美觀現代，新手友好。<br>🔴 <strong>交易 Bug</strong>：切換整股/零股時自動重設已調好的價格。</td>\n                        </tr>\n                        <tr>\n                            <td class=\"py-3 px-4 font-bold text-gray-300\">系統效能 (Performance)</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟡 Q1 有 K線手勢 Bug（已修）。<br>🔴 4.18.x 登入/身分驗證、交易狀態保持與帳務資料同步仍有穩定性風險。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🔴 <strong>致命傷 (大樹守衛)</strong>：開盤與波動大時極易癱瘓，海外用戶頻繁報價連線失敗。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🔴 <strong>致命傷 (練鐵砂掌)</strong>：能耗極高，手機異常發熱（一小時耗電 30% 以上）。</td>\n                        </tr>\n                        <tr>\n                            <td class=\"py-3 px-4 font-bold text-gray-300\">特色加值 (Value-adds)</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟢 提供庫存總損益平衡價（買入價+手續費+稅），方便用戶平損益。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟢 複委託手續費便宜。<br>🔴 缺點：無到價提醒（需去樹精靈），無個股含息成本，無英股。</td>\n                            <td class=\"py-3 px-4 text-gray-400\">🟢 <strong>大優勢</strong>：獨家提供「即時大戶散戶資金流向圖」。<br>🔴 缺點：豐存股需轉網頁，大戶豐拆分。</td>\n                        </tr>\n                    </tbody>\n                </table>\n            </div>\n        </div>\n\n        <!-- 🚀 Action Plan Timeline -->\n        <div class=\"glass-card rounded-2xl p-6\">\n            <h3 class=\"font-bold text-base text-gray-100 mb-6 flex items-center gap-2\">\n                <span>🚀</span> 元大證券「投資先生」戰略行動方案 (Action Plan)\n            </h3>\n            \n            <div class=\"relative border-l border-gray-800 pl-6 space-y-6\">\n                <!-- Stage 1 -->\n                <div class=\"relative\">\n                    <span class=\"absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-blue-500 border border-gray-900 flex items-center justify-center text-[10px] text-white font-bold\">1</span>\n                    <div class=\"flex items-center gap-2 mb-1.5\">\n                        <span class=\"text-xs tag-blue px-2.5 py-0.5 rounded-full font-bold\">階段一</span>\n                        <h4 class=\"font-bold text-sm text-gray-200\">體驗還原與流程防呆（1個月內）</h4>\n                    </div>\n                    <ul class=\"text-xs text-gray-400 list-disc list-inside space-y-1 pl-1\">\n                        <li><strong>還原無障礙 UI</strong>：將庫存圓餅圖報酬率字體還原，把投資夥伴與客服懸浮標誌改為可折疊，消除誤觸。</li>\n                        <li><strong>恢復快捷路徑</strong>：重新上架「點擊庫存總報酬，直接跳轉當沖交易畫面」的快捷路徑。</li>\n                        <li><strong>開戶漏斗防呆</strong>：加入 LocalStorage 暫存草稿機制，放開限制支援 PDF 格式財力證明。</li>\n                    </ul>\n                </div>\n                \n                <!-- Stage 2 -->\n                <div class=\"relative\">\n                    <span class=\"absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-emerald-500 border border-gray-900 flex items-center justify-center text-[10px] text-white font-bold\">2</span>\n                    <div class=\"flex items-center gap-2 mb-1.5\">\n                        <span class=\"text-xs tag-green px-2.5 py-0.5 rounded-full font-bold\">階段二</span>\n                        <h4 class=\"font-bold text-sm text-gray-200\">系統效能與數據穩定（3個月內）</h4>\n                    </div>\n                    <ul class=\"text-xs text-gray-400 list-disc list-inside space-y-1 pl-1\">\n                        <li><strong>優化 Session 機制</strong>：修復開盤強制登出 Bug，將自動登出時限由 30秒 放寬至國際 15-30分鐘 標準。</li>\n                        <li><strong>開盤頻寬備援擴容</strong>：擴容每日 9:00 - 9:15 伺服器頻寬，保證 API 響應小於 1.5 秒，徹底與競品癱瘓劃清界線。</li>\n                        <li><strong>大數據輕量化推送</strong>：借鑑永豐發燙教訓，優化看盤 WebGL 渲染與滾動防抖更新，降低 CPU 消耗。</li>\n                    </ul>\n                </div>\n                \n                <!-- Stage 3 -->\n                <div class=\"relative\">\n                    <span class=\"absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-amber-500 border border-gray-900 flex items-center justify-center text-[10px] text-white font-bold\">3</span>\n                    <div class=\"flex items-center gap-2 mb-1.5\">\n                        <span class=\"text-xs tag-amber px-2.5 py-0.5 rounded-full font-bold\">階段三</span>\n                        <h4 class=\"font-bold text-sm text-gray-200\">功能超車與定位收割（6個月內）</h4>\n                    </div>\n                    <ul class=\"text-xs text-gray-400 list-disc list-inside space-y-1 pl-1\">\n                        <li><strong>擴大宣傳「精緻庫存指定沖銷」</strong>：強力推廣既有之指定庫存賣出功能，教育用戶手動優先賣出「高/低成本庫存」以利節稅。</li>\n                        <li><strong>推出「美股還原K線」與「美股 DRIP」</strong>：解決永豐分割錯亂痛點，提供複委託股息除息次日自動再投入。</li>\n                        <li><strong>行銷定位大戰</strong>：強打<strong>「關鍵時刻，絕不掉鏈！元大投資先生——您的資金，值得更穩定的守護。」</strong></li>\n                    </ul>\n                </div>\n            </div>\n        </div>";

function json(data, init = {}) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...(init.headers || {}),
    },
  });
}

const enc = new TextEncoder();

// HMAC-SHA256 a value with the server secret, return base64url signature.
async function sign(value, secret) {
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(value));
  return btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// Length-checked constant-time string compare.
function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Mint a signed "<expiry>.<hmac>" token so the unlock cookie can't be forged.
async function makeToken(secret, ttl = 86400) {
  const exp = String(Date.now() + ttl * 1000);
  return `${exp}.${await sign(exp, secret)}`;
}

async function verifyToken(token, secret) {
  if (!token || !token.includes('.')) return false;
  const [exp, sig] = token.split('.');
  if (!timingSafeEqual(sig, await sign(exp, secret))) return false;
  return Number.isFinite(+exp) && Date.now() < +exp;
}

function getCookie(request, name) {
  const m = (request.headers.get('cookie') || '')
    .match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
  return m ? m[1] : null;
}

async function unlockedResponse(env) {
  const token = await makeToken(env.EXPERT_TAB_SECRET);
  return json(
    { html: EXPERT_HTML },
    {
      headers: {
        'cache-control': 'no-store',
        'set-cookie': `yuanta_expert_unlocked=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400`,
      },
    },
  );
}

export async function onRequestGet({ request, env }) {
  if (!env.EXPERT_TAB_SECRET) {
    return json({ error: 'not_configured' }, { status: 500, headers: { 'cache-control': 'no-store' } });
  }
  const ok = await verifyToken(getCookie(request, 'yuanta_expert_unlocked'), env.EXPERT_TAB_SECRET);
  if (!ok) {
    return json({ error: 'locked' }, { status: 401, headers: { 'cache-control': 'no-store' } });
  }
  return unlockedResponse(env);
}

export async function onRequestPost({ request, env }) {
  let body = {};
  try {
    body = await request.json();
  } catch (_) {
    return json({ error: 'invalid_json' }, { status: 400, headers: { 'cache-control': 'no-store' } });
  }

  if (!env.EXPERT_TAB_PASSWORD || !env.EXPERT_TAB_SECRET) {
    return json({ error: 'password_not_configured' }, { status: 500, headers: { 'cache-control': 'no-store' } });
  }

  if (!timingSafeEqual(String(body.password || ''), env.EXPERT_TAB_PASSWORD)) {
    return json({ error: 'unauthorized' }, { status: 401, headers: { 'cache-control': 'no-store' } });
  }

  return unlockedResponse(env);
}
