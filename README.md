# 简历筛选 Agent

基于 LangChain 和 OpenAI 的简历初筛示例，所有可调参数集中在 `config.get_config()` 中。

## 环境准备
```bash
cd /Users/fangfang/test
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # 已安装可跳过
```

在 `.env` 或环境变量中提供 `OPENAI_API_KEY`，可按需覆盖 `config.py` 中的关键词与模型。

## 运行演示
```bash
source .venv/bin/activate
python main.py
```

输出示例：
```
筛选结果:
{'decision': 'accept', 'score': 0.76, 'missing': ['...'], 'reasoning': '...'}
```

## 快速调整
- 所有参数（模型、温度、关键词、阈值等）在 `config.py` 的 `get_config()` 中集中管理。
- 如需改为英文输出，调整 `language` 为 `"en"`。

