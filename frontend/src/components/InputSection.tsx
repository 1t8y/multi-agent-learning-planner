// 输入区：文本框 + 提交按钮 + 清除按钮。
// 这里是 /api/plan 的唯一触发点，负责管理加载态与错误提示。
import { useState } from 'react';
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
    <div className="request">
      <div className="request__head">
        <label className="field__label" htmlFor="learning-request">
          你的学习需求
        </label>

        {(inputValue || planResult) && (
          <button type="button" className="btn btn--quiet btn--sm" onClick={handleClear}>
            清除
          </button>
        )}
      </div>

      <div className="field">
        <textarea
          id="learning-request"
          name="learning-request"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading}
          placeholder="例如：我是零基础，每天可以学习 2 小时，想学 Python 编程，喜欢视频学习"
          className="field__input"
          aria-describedby="learning-request-help"
        />
      </div>

      <div className="request__foot">
        <p className="request__help" id="learning-request-help">
          按 Ctrl + Enter 也可以提交
        </p>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !inputValue.trim()}
          className="btn btn--primary"
        >
          {isLoading ? (
            <>
              <span className="btn__spin" aria-hidden="true" />
              <span>正在生成…</span>
            </>
          ) : planResult ? (
            <span>重新生成学习规划</span>
          ) : (
            <span>生成学习规划</span>
          )}
        </button>
      </div>
    </div>
  );
}
