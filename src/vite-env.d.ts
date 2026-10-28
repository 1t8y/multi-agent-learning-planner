/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 可选：覆盖前端请求的后端地址；开发环境默认 http://localhost:8001 */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
