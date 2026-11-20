// 「贡献新资源」弹窗：前端先做一遍白名单校验，再提交到 /api/resources/submit。
// 提交成功后不会立刻出现在推荐里——要先进待审核队列，审核通过才入库。
import { useEffect, useState } from 'react';
import { submitResource } from '../utils/api';
import type { ResourceSubmission } from '../types';

interface ResourceSubmitModalProps {
  /** 是否显示弹窗；false 时组件直接返回 null，不渲染 DOM */
  open: boolean;
  /** 关闭回调；提交中会被忽略，防止请求还没回来就关窗 */
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

/** 表单内部状态；tags 用原始字符串保存，提交时才拆分去重 */
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

/**
 * 资源贡献弹窗。
 *
 * 两个 useEffect 分别负责：打开时清掉上次的错误提示、监听 Esc 关闭。
 * 关闭按钮在提交中会被忽略，避免用户在请求途中关窗造成「已提交但没看到结果」。
 */
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

  /** 改任意一个字段：顺带清掉上一次的错误提示，避免旧错误一直挂着。 */
  const update = (patch: Partial<FormState>) => {
    setForm((prev) => ({ ...prev, ...patch }));
    setErrorMessage(null);
  };

  /**
   * 校验并提交。
   *
   * 校验分两层：这里先做即时反馈（不浪费一次网络请求），
   * 后端仍会再校验一次白名单——前端校验只是体验优化，不是安全边界。
   */
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

  return (
    <div
      className="dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="resource-dialog-title"
      onClick={() => { if (!submitting) { onClose(); } }}
    >
      <div className="dialog__sheet" onClick={(event) => event.stopPropagation()}>
        <div className="dialog__head">
          <div>
            <h2 className="dialog__title" id="resource-dialog-title">
              贡献新资源
            </h2>
            <p className="dialog__note">先进入待审核队列，审核通过后才加入知识库参与检索。</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="dialog__close"
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        {submissionId && (
          <div className="dialog__ok">
            <div>
              <p className="dialog__ok-title">已提交，待审核</p>
              <p className="dialog__ok-id">提交编号 {submissionId}</p>
              <p>可以继续修改下表内容并再次提交。</p>
            </div>
          </div>
        )}

        <div className="dialog__fields">
          <div>
            <label className="dialog__label" htmlFor="res-title">
              资源标题 <span className="dialog__req">*</span>
            </label>
            <input
              id="res-title"
              name="title"
              value={form.title}
              onChange={(event) => update({ title: event.target.value })}
              disabled={submitting}
              placeholder="例如：Python 官方教程"
              className="dialog__input"
            />
          </div>

          <div>
            <label className="dialog__label" htmlFor="res-url">
              资源链接 <span className="dialog__req">*</span>
            </label>
            <input
              id="res-url"
              name="url"
              type="url"
              inputMode="url"
              value={form.url}
              onChange={(event) => update({ url: event.target.value })}
              disabled={submitting}
              placeholder="https://example.com/course"
              className="dialog__input"
            />
          </div>

          <div className="dialog__row">
            <div>
              <label className="dialog__label" htmlFor="res-type">
                资源类型
              </label>
              <select
                id="res-type"
                name="resource_type"
                value={form.resourceType}
                onChange={(event) => update({ resourceType: event.target.value })}
                disabled={submitting}
                className="dialog__select"
              >
                {TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="dialog__label" htmlFor="res-field">
                领域
              </label>
              <select
                id="res-field"
                name="field"
                value={form.field}
                onChange={(event) => update({ field: event.target.value })}
                disabled={submitting}
                className="dialog__select"
              >
                {FIELD_OPTIONS.map((field) => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="dialog__label" htmlFor="res-level">
                难度
              </label>
              <select
                id="res-level"
                name="level"
                value={form.level}
                onChange={(event) => update({ level: event.target.value })}
                disabled={submitting}
                className="dialog__select"
              >
                {LEVEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="dialog__label" htmlFor="res-description">
              描述
            </label>
            <textarea
              id="res-description"
              name="description"
              value={form.description}
              onChange={(event) => update({ description: event.target.value })}
              disabled={submitting}
              placeholder="这个资源讲什么、适合谁"
              className="dialog__area"
            />
          </div>

          <div>
            <label className="dialog__label" htmlFor="res-tags">
              标签 <span className="dialog__hint">用逗号分隔，可留空</span>
            </label>
            <input
              id="res-tags"
              name="tags"
              value={form.tags}
              onChange={(event) => update({ tags: event.target.value })}
              disabled={submitting}
              placeholder="Python, 零基础, 视频"
              className="dialog__input"
            />
          </div>

          {errorMessage && (
            <div className="notice" role="alert">
              提交失败：{errorMessage}
            </div>
          )}
        </div>

        <div className="dialog__foot">
          <button type="button" onClick={onClose} disabled={submitting} className="btn btn--quiet">
            关闭
          </button>
          <button type="button" onClick={handleSubmit} disabled={submitting} className="btn btn--primary">
            {submitting ? '提交中…' : '提交待审核'}
          </button>
        </div>
      </div>
    </div>
  );
}
