// 根组件：只负责页面骨架与错误条展示，业务状态全部走 planStore。
// 页面自上而下是：顶栏 → 输入区 → 错误提示（有才显示）→ 结果区 → 页脚。
import { Header } from './components/Header';
import { InputSection } from './components/InputSection';
import { ResultSection } from './components/ResultSection';
import { usePlanStore } from './store/planStore';

/**
 * 应用根组件。
 *
 * 这里只订阅 error 一个字段：请求失败时必须把后端返回的真实原因显示出来，
 * 不允许静默回退成假数据，所以错误条放在输入区与结果区之间。
 */
function App() {
  const { error } = usePlanStore();

  return (
    <div className="app">
      <Header />

      <main className="main" id="main">
        <div className="shell">
          <InputSection />

          {error && (
            <div className="notice" role="alert">
              {error}
            </div>
          )}

          <ResultSection />
        </div>
      </main>

      <footer className="colophon">
        <div className="shell">
          <p>评估均分低于 6 分时自动重新规划，最多 3 轮。</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
