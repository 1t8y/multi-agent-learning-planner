import { useState } from 'react';
import { Wand2, Loader2, X } from 'lucide-react';
import { usePlanStore } from '../store/planStore';
import { generateLearningPlan, getMockPlanResponse } from '../utils/api';

export function InputSection() {
  const { userInput, setUserInput, isLoading, setIsLoading, setPlanResult, setError, planResult } = usePlanStore();
  const [inputValue, setInputValue] = useState(userInput);

  const handleSubmit = async () => {
    if (!inputValue.trim()) {
      setError('请输入您的学习需求');
      return;
    }

    setIsLoading(true);
    setError(null);
    setUserInput(inputValue);

    try {
      const result = await generateLearningPlan(inputValue);
      setPlanResult(result);
    } catch (error) {
      console.error('API调用失败，使用模拟数据:', error);
      const mockResult = getMockPlanResponse();
      mockResult.requirement_data.learning_objective = inputValue;
      setPlanResult(mockResult);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setInputValue('');
    setUserInput('');
    setPlanResult(null);
    setError(null);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSubmit();
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-2xl p-6 md:p-8 card-shadow mb-8">
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <label className="block text-gray-700 font-semibold">
            请输入您的学习需求
          </label>
          {(inputValue || planResult) && (
            <button
              onClick={handleClear}
              className="flex items-center gap-1 text-sm text-gray-400 hover:text-red-500 transition-colors"
            >
              <X className="w-4 h-4" />
              清除
            </button>
          )}
        </div>
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="例如：我是零基础，每天可以学习2小时，想学习Python编程，喜欢视频学习方式..."
          className="w-full h-32 p-4 border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent transition-all duration-300 text-gray-700 placeholder-gray-400"
        />
        <p className="text-sm text-gray-400 mt-2">
          按 Ctrl + Enter 快速生成
        </p>
      </div>

      <button
        onClick={handleSubmit}
        disabled={isLoading || !inputValue.trim()}
        className="w-full bg-gradient-primary text-white font-semibold py-4 px-6 rounded-xl flex items-center justify-center gap-3 hover:opacity-90 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>正在生成学习规划...</span>
          </>
        ) : planResult ? (
          <>
            <Wand2 className="w-5 h-5" />
            <span>重新生成学习规划</span>
          </>
        ) : (
          <>
            <Wand2 className="w-5 h-5" />
            <span>生成学习规划</span>
          </>
        )}
      </button>
    </div>
  );
}
