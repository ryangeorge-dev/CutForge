import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
// Node 26 exposes its own optional localStorage. Tests must use the browser
// storage implementation supplied by jsdom, just as the running UI does.
Object.defineProperty(globalThis, 'localStorage', { value: window.localStorage, configurable: true });
afterEach(cleanup);
