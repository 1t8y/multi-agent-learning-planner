// 输入区：文本框 + 提交按钮 + 清除按钮。
// 这里是 /api/plan 的唯一触发点，负责管理加载态与错误提示。
import { useState } from 'react';
import { Wand2, Loader2, X } from 'lucide-react';
import { usePlanStore } from '../store/planStore';
import { generateLearningPlan } from '../utils/api';

/**
 * 学习需求输入与提交。
 *
 * 输入框内容同时存在两处：组件内 inputValue（受控输入，逐字更新）
 * 和 store.userInput（提交后才同步）。这样做是为了避免每次击键都触发全局重渲染。
 */
export function InputSection() {
  const { userInput, setUserInput, isLoading, setIsLoading, setPlanResult, setError, planResult } = usePlanStore();
  const [inputValue, setInputValue] = useState(userInput);

  /**
   * 提交学习需求。
   *
   * 顺序很重要：先清空上一轮结果再发请求。
   * 这样请求失败时页面是「空的 + 错误提示」，不会残留上一轮的计划让人误以为是新结果。
   */
  const handleSubmit = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed) {
      setError('请输入您的学习需求');
      return;
    }

    setIsLoading(true);
    setError(null);
    // 清空上一轮结果：请求失败时页面不能残留旧数据，更不能展示 mock 数据
    setPlanResult(null);
    setUserInput(trimmed);

    try {
      const result = await generateLearningPlan(trimmed);
      setPlanResult(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('生成学习规划失败:', error);
      setError(`生成失败：${message}`);
    } finally {
      setIsLoading(false);
    }
  };

  /** 清空输入、结果与错误，回到初始状态。 */
  const handleClear = () => {
    setInputValue('');
    setUserInput('');
    setPlanResult(null);
    setError(null);
  };

  /** 快捷键：Ctrl + Enter 提交（Enter 单独按下用于换行）。 */
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
