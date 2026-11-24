import './lib/base';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './global.css';
import App from './components/App';
import { clock } from './lib/clock';
import { useStore } from './lib/store';

// 调试/测试钩子 (Playwright 用来读状态, 不用来驱动操作: 操作一律走真实鼠标键盘)
/*
 * Agent Notes: studio 入口; __hx 只给 Playwright 读状态
 * .agents/notes/implemented/feature/2026-11-09-karaoke-studio.md
 */
const hook = { store: useStore, clock };
(window as unknown as { __hx: unknown }).__hx = hook;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
