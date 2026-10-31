import { useEffect, useState } from 'react';
import { X, Loader2, CheckCircle2, AlertCircle, Plus } from 'lucide-react';
import { submitResource } from '../utils/api';
import type { ResourceSubmission } from '../types';

interface ResourceSubmitModalProps {
  open: boolean;
  onClose: () => void;
}

// 与后端 ALLOWED_* 白名单保持一致：知识库只识别这三类领域、四种资源类型
const TYPE_OPTIONS = ['视频教程', '文字教程', '实战项目', '文档资料'] as const;
const FIELD_OPTIONS = ['AI', '编程', '数学'] as const;
const LEVEL_OPTIONS = [
  { value: 'beginner', label: '零基础' },
  { value: 'intermediate', label: '进阶' },
  { value: 'advanced', label: '高阶' },
] as const;

interface FormState {
  title: string;
  url: string;
  description: string;
  resourceType: string;
  field: string;
  level: string;
  tags: string;
}

const EMPTY_FORM: FormState = {
  title: '',
  url: '',
  description: '',
  resourceType: TYPE_OPTIONS[0],
  field: FIELD_OPTIONS[0],
  level: 'intermediate',
  tags: '',
};

/** 解析逗号/顿号/空格分隔的标签，去重并丢弃空值 */
function parseTags(raw: string): string[] {
  const parts = raw.split(/[,，、\s]+/).map((t) => t.trim()).filter(Boolean);
  return Array.from(new Set(parts));
}

/** 校验表单，返回错误信息；通过则返回 null */
function validate(form: FormState): string | null {
  if (!form.title.trim()) {
    return '请填写资源标题';
  }
  if (!form.url.trim()) {
    return '请填写资源链接';
  }
  if (!/^https?:\/\//i.test(form.url.trim())) {
    return '资源链接必须以 http:// 或 https:// 开头';
  }
  try {
    new URL(form.url.trim());
  } catch {
    return '资源链接格式不合法';
  }
  if (!TYPE_OPTIONS.includes(form.resourceType as (typeof TYPE_OPTIONS)[number])) {
    return '资源类型不在允许范围内';
  }
  if (!FIELD_OPTIONS.includes(form.field as (typeof FIELD_OPTIONS)[number])) {
    return '领域不在允许范围内';
  }
  if (!LEVEL_OPTIONS.some((option) => option.value === form.level)) {
    return '难度不在允许范围内';
  }
  return null;
}

export function ResourceSubmitModal({ open, onClose }: ResourceSubmitModalProps) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);

  // 打开时重置上一次的提示，但不清空用户已经填的内容
  useEffect(() => {
    if (open) {
      setErrorMessage(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, submitting, onClose]);

  if (!open) {
    return null;
  }

  const update = (patch: Partial<FormState>) => {
    setForm((prev) => ({ ...prev, ...patch }));
    setErrorMessage(null);
  };

  const handleSubmit = async () => {
    const invalid = validate(form);
    if (invalid) {
      setErrorMessage(invalid);
      return;
    }

    const payload: ResourceSubmission = {
      title: form.title.trim(),
      description: form.description.trim(),
      url: form.url.trim(),
      resource_type: form.resourceType,
      field: form.field,
      level: form.level as ResourceSubmission['level'],
      tags: parseTags(form.tags),
    };

    setSubmitting(true);
    setErrorMessage(null);
    try {
      const result = await submitResource(payload);
      setSubmissionId(result.submission_id);
      // 成功后保留已填内容，避免用户想再提交一条相似资源时重填
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmitting(false);
    }
  };

  const fieldClass =
    'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:bg-gray-100';

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 py-8 overflow-y-auto"
      onClick={() => {
        if (!submitting) {
          onClose();
        }
      }}
    >
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-2xl p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-800">贡献新资源</h3>
            <p className="text-xs text-gray-500 mt-1">
              提交后进入待审核队列，审核通过才会加入知识库参与检索
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-40"
            aria-label="关闭"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {submissionId && (
          <div className="mb-4 flex items-start gap-2 rounded-lg bg-green-50 border border-green-200 px-3 py-2">
            <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
            <div className="text-xs text-green-700">
              <p className="font-medium">已提交，待审核</p>
              <p className="mt-0.5 text-green-600/80 break-all">提交编号：{submissionId}</p>
              <p className="mt-1 text-green-600/80">可以继续修改下表内容并再次提交。</p>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              资源标题 <span className="text-red-500">*</span>
            </label>
            <input
              value={form.title}
              onChange={(event) => update({ title: event.target.value })}
              disabled={submitting}
              placeholder="例如：Python 官方教程"
              className={fieldClass}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              资源链接 <span className="text-red-500">*</span>
            </label>
            <input
              value={form.url}
              onChange={(event) => update({ url: event.target.value })}
              disabled={submitting}
              placeholder="https://example.com/course"
              className={fieldClass}
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">资源类型</label>
              <select
                value={form.resourceType}
                onChange={(event) => update({ resourceType: event.target.value })}
                disabled={submitting}
                className={fieldClass}
              >
                {TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">领域</label>
              <select
                value={form.field}
                onChange={(event) => update({ field: event.target.value })}
                disabled={submitting}
                className={fieldClass}
              >
                {FIELD_OPTIONS.map((field) => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">难度</label>
              <select
                value={form.level}
                onChange={(event) => update({ level: event.target.value })}
                disabled={submitting}
                className={fieldClass}
              >
                {LEVEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">描述</label>
            <textarea
              value={form.description}
              onChange={(event) => update({ description: event.target.value })}
              disabled={submitting}
              placeholder="这个资源讲什么、适合谁…"
              className={`${fieldClass} resize-none h-20`}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              标签 <span className="text-gray-400 font-normal">（用逗号分隔，可留空）</span>
            </label>
            <input
              value={form.tags}
              onChange={(event) => update({ tags: event.target.value })}
              disabled={submitting}
              placeholder="Python, 零基础, 视频"
              className={fieldClass}
            />
          </div>

          {errorMessage && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
              <p className="text-xs text-red-600">提交失败：{errorMessage}</p>
            </div>
          )}
        </div>

        <div className="flex gap-2 mt-5">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg transition-colors disabled:opacity-50"
          >
            关闭
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm bg-gradient-primary text-white font-semibold rounded-lg hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            {submitting ? '提交中…' : '提交待审核'}
          </button>
        </div>
      </div>
    </div>
  );
}
