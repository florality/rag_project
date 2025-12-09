# Vercel 部署说明

## 轻量级部署版本
此版本移除了大型AI依赖包，以符合Vercel的Lambda函数大小限制。

### 部署步骤：
1. 使用 `requirements-vercel.txt` 作为依赖文件
2. 确保 `api/index.py` 使用轻量级版本
3. 在Vercel中设置环境变量（如果需要）

### 功能限制：
- 移除了完整的AI模型依赖
- 保留了基本的Web框架功能
- 完整功能需要在本地环境运行

### 本地完整版本：
如需完整功能，请在本地运行：
```bash
pip install -r requirements.txt
python main.py
```

## 📋 立即操作建议

1. **立即部署轻量级版本**：使用上面的配置，可以立即部署到Vercel
2. **保留完整功能**：在本地环境中运行完整版本
3. **考虑替代方案**：如果需要在云端运行完整功能，可以考虑：
   - AWS Lambda + EFS（支持大文件）
   - Google Cloud Run（无大小限制）
   - 自建服务器

您希望我帮您实施这些修改吗？还是您有其他偏好方案？