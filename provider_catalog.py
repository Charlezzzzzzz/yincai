"""Public model IDs checked against the linked first-party API documentation on 2026-11-18."""

def profile(identifier, label, base, models, docs, note=""):
    return dict(id=identifier, label=label, base_url=base, models=models, docs_url=docs, note=note)


PROVIDERS = [
    profile("ollama", "本机 Ollama", "http://127.0.0.1:11434", ["qwen3.5:9b", "qwen3.6:35b"], "https://docs.ollama.com/api/tags", "请填写本机已安装的模型标签。"),
    profile("deepseek", "DeepSeek", "https://api.deepseek.com", ["deepseek-flash", "deepseek-v4-pro"], "https://api-docs.deepseek.com/api/create-chat-completion/"),
    profile("qwen", "阿里云百炼 · 千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", ["qwen3.8-flash", "qwen4-max", "qwen3.7-plus"], "https://help.aliyun.com/zh/model-studio/text-generation-model", "预设使用北京地域。使用其他地域或业务空间专属域名时，请选自定义并填写对应地址。"),
    profile("moonshot", "月之暗面 · Kimi", "https://api.moonshot.cn/v1", ["kimi-k3.1-pro", "kimi-k3"], "https://platform.kimi.com/docs/models"),
    profile("zhipu", "智谱 · GLM", "https://open.bigmodel.cn/api/paas/v4", ["glm-5.3"], "https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3"),
    profile("volcengine", "火山方舟 · 豆包", "https://ark.cn-beijing.volces.com/api/v3", ["doubao-seed-2-1-lite-260915", "doubao-seed-2-1-pro-260915"], "https://docs.volcengine.com/docs/ark/model-list?lang=zh", "也可填写账号已开通的推理接入点 ID。"),
    profile("minimax", "MiniMax · 国际站", "https://api.minimax.io/v1", ["MiniMax-M3.1-Flash", "MiniMax-M3"], "https://platform.minimax.io/docs/api-reference/text-openai-api", "使用国际站密钥；国内站请选择自定义并填写国内站接口。"),
    profile("openai", "OpenAI", "https://api.openai.com/v1", ["gpt-6.2-sol", "gpt-6.2-astra"], "https://developers.openai.com/api/docs/models/gpt-6.2-sol"),
    profile("google", "Google · Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", ["gemini-4-hydrogen", "gemini-4-argon"], "https://ai.google.dev/gemini-api/docs/openai"),
    profile("anthropic", "Anthropic · Claude", "https://api.anthropic.com/v1", ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"], "https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk", "请使用已绑定工作空间的 Claude API 密钥。"),
    profile("custom", "自定义兼容接口", "", [], "", "填写服务根地址和对方提供的模型 ID。接口须支持 Chat Completions 与文本消息。"),
]
