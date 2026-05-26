# GitHub安全配置指南

## 已配置的安全措施

### ✅ .gitignore 已更新

以下文件和目录会被自动忽略，不会上传到GitHub：

```
# 敏感配置
.env
.env.local
.env.*.local

# Trae配置（包含API密钥）
.trae/config/
.trae/agents/
.trae/documents/

# Python
__pycache__/
*.pyc

# 虚拟环境
venv/
env/
.venv/

# IDE
.vscode/
.idea/
```

### ✅ 配置示例文件已创建

| 示例文件 | 说明 | 真实配置位置 |
|---------|------|------------|
| `.env.example` | Python环境变量示例 | `.env`（已忽略） |
| `hermes_sync.json.example` | Hermes配置示例 | `hermes_sync.json`（已忽略） |

## 安全配置步骤

### 1. 设置环境变量

复制示例文件并填写真实信息：

```bash
# Python后端
cd learning-planning-multi-agent
cp .env.example .env
# 编辑 .env，填入你的API密钥

# Hermes配置
cd ..
cp .trae/config/hermes_sync.json.example .trae/config/hermes_sync.json
# 编辑 hermes_sync.json，填入真实配置
```

### 2. 验证Git状态

```bash
git status
# 确认以下文件不在待提交列表中：
# - .env
# - .trae/config/hermes_sync.json
# - .trae/agents/
# - .trae/documents/
```

### 3. 安全提交

```bash
# 添加安全文件
git add .gitignore
git add .trae/config/hermes_sync.json.example
git add learning-planning-multi-agent/.env.example
git add SECURITY.md

# 提交
git commit -m "Add security configuration and examples"
```

## 安全检查清单

- [x] `.gitignore` 包含敏感文件
- [x] 示例配置文件已创建
- [x] 真实API密钥不在仓库中
- [x] `.env` 被忽略
- [x] `.trae/config/` 被忽略
- [x] `.trae/agents/` 被忽略
- [x] `.trae/documents/` 被忽略

## 其他安全建议

1. **不要提交包含真实密钥的配置文件**
2. **使用环境变量而非硬编码**
3. **定期轮换API密钥**
4. **使用不同的API密钥用于开发和生产**
5. **配置密钥权限最小化**

## 问题排查

如果不小心提交了敏感信息：

```bash
# 从git历史中移除（警告：会重写历史）
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

然后强制推送到远程仓库。
