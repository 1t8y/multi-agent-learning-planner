// 前端入口：把根组件挂载到 index.html 里的 #root 节点。
// StrictMode 只在开发环境做额外的渲染检查（例如故意调用两次副作用函数），不影响生产行为。
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
