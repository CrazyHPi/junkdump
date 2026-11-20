// 零依赖静态服务器：用来预览已构建的站点（不需要 esbuild，因而在受限沙箱里也能跑）
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { join, extname, resolve } from 'node:path'

const root = resolve(process.argv[2] ?? 'docs/.vitepress/dist')
const port = Number(process.argv[3] ?? 4173)

const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2'
}

async function find(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0])
  const candidates = clean.endsWith('/')
    ? [join(root, clean, 'index.html')]
    : [join(root, clean), join(root, clean + '.html'), join(root, clean, 'index.html')]
  for (const c of candidates) {
    if (!c.startsWith(root)) continue
    try {
      const st = await stat(c)
      if (st.isFile()) return c
    } catch {}
  }
  return null
}

createServer(async (req, res) => {
  const file = (await find(req.url ?? '/')) ?? join(root, '404.html')
  try {
    const body = await readFile(file)
    res.writeHead(file.endsWith('404.html') ? 404 : 200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' })
    res.end(body)
  } catch {
    res.writeHead(404).end('not found')
  }
}).listen(port, '127.0.0.1', () => {
  console.log('OSL docs preview: http://127.0.0.1:' + port + '/')
})
