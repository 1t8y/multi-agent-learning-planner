import { Header } from './components/Header';
import { InputSection } from './components/InputSection';
import { ResultSection } from './components/ResultSection';
import { usePlanStore } from './store/planStore';

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
