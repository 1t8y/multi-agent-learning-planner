import { Brain, Sparkles } from 'lucide-react';

export function Header() {
  return (
    <header className="text-center mb-10">
      <div className="flex items-center justify-center gap-3 mb-4">
        <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
          <Brain className="w-7 h-7 text-white" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-white">
          学习规划助手
        </h1>
        <Sparkles className="w-6 h-6 text-yellow-300" />
      </div>
      <p className="text-white/80 text-lg max-w-2xl mx-auto">
        基于多智能体协作，为您量身定制个性化学习方案
      </p>
    </header>
  );
}
