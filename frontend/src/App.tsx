// 根组件：只负责页面骨架与错误条展示，业务状态全部走 planStore。
// 页面自上而下是：标题 → 输入区 → 错误提示（有才显示）→ 结果区 → 页脚。
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
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <Header />
        
        <InputSection />

        {error && (
          <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded-lg mb-8">
            {error}
          </div>
        )}

        <ResultSection />

        <footer className="text-center mt-12 text-white/60 text-sm">
          <p>基于多智能体协作技术 · 为您提供个性化学习规划</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
