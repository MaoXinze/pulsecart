/**
 * Used to parse the .env.development proxy configuration
 */
import type { ProxyOptions } from 'vite';

type ProxyItem = [string, string];

type ProxyList = ProxyItem[];

type ProxyTargetList = Record<string, ProxyOptions>;

const httpsRE = /^https:\/\//;

/**
 * Generate proxy
 * @param list
 */
export function createProxy(list: ProxyList = []) {
  const ret: ProxyTargetList = {};
  for (const [prefix, target] of list) {
    const isHttps = httpsRE.test(target);

    // https://github.com/http-party/node-http-proxy#options
    ret[prefix] = {
      target: target,
      changeOrigin: true,
      ws: true,
      // 品控 Dify 工作流可能超过 1 分钟，避免开发代理先断开
      timeout: 600000,
      proxyTimeout: 600000,
      rewrite: (path) => path.replace(new RegExp(`^${prefix}`), ''),
      // https is require secure=false
      ...(isHttps ? { secure: false } : {}),
      configure: (proxy) => {
        // 后端 WebSocket 断开或页面刷新时常见，无需刷屏报错
        const ignoreCodes = new Set(['ECONNABORTED', 'ECONNRESET', 'EPIPE']);
        proxy.on('error', (err: NodeJS.ErrnoException) => {
          if (ignoreCodes.has(err.code || '')) return;
          console.error('[vite proxy]', err.message);
        });
        proxy.on('proxyReqWs', (_proxyReq, _req, socket) => {
          socket.on('error', (err: NodeJS.ErrnoException) => {
            if (ignoreCodes.has(err.code || '')) return;
            console.error('[vite proxy ws]', err.message);
          });
        });
      },
    };
  }
  return ret;
}
