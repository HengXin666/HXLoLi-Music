/* 多工程验收台: 页面在 /s/<番>/<歌>/ 下时, 所有 /api /media 请求都要带这个前缀 (服务端按前缀选工程).
 * 单工程 (--project) 时前缀为空, 行为与以前一样. 服务端回的 JSON 里的地址已经带前缀; 这里只补前端写死的地址.
 * Agent Notes: 验收台多工程 (一个服务挂全部歌)
 * .agents/notes/implemented/feature/2026-11-24-karaoke-studio-multi.md
 */
export const BASE = (location.pathname.match(/^\/s\/[^/]+\/[^/]+/) ?? [''])[0];
export const withBase = (u: string) => (BASE && /^\/(api|media|fonts|octopus)\//.test(u) ? BASE + u : u);

const raw = window.fetch.bind(window);
window.fetch = ((i: RequestInfo | URL, init?: RequestInit) => raw(typeof i === 'string' ? withBase(i) : i, init)) as typeof window.fetch;
if (BASE) document.title = `${decodeURIComponent(BASE.split('/')[3] ?? '')} · HX 验收台`;
