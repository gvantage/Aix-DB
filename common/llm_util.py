import json
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from model.db_connection_pool import get_db_pool
from model.db_models import TAiModel

pool = get_db_pool()


def get_llm(temperature=0.75):
    with pool.get_session() as session:
        # Fetch default model
        model = session.query(TAiModel).filter(TAiModel.default_model == True).filter(TAiModel.model_type == 1).first()
        if not model:
            raise ValueError("No default AI model configured in database.")

        # Map supplier to model type string used in map
        # 1:OpenAI, 2:Azure, 3:Ollama, 4:vLLM, 5:DeepSeek, 6:Qwen, 7:Moonshot, 8:ZhipuAI, 9:Other
        supplier = model.supplier

        # Determine internal model_type key for the map
        if supplier == 3:
            model_type = "ollama"
        elif supplier == 6:
            model_type = "qwen"
        else:
            # Default to openai for others (OpenAI, DeepSeek, Moonshot, Zhipu, vLLM, etc.)
            model_type = "openai"

        model_name = model.base_model
        model_api_key = model.api_key
        model_base_url = model.api_domain

        try:
            temperature = float(temperature)
        except ValueError:
            temperature = 0.75

        model_map = {
            "openai": lambda: ChatOpenAI(
                model=model_name,
                temperature=temperature,
                base_url=model_base_url,
                api_key=model_api_key or "empty",  # Ensure not None
            ),
            "qwen": lambda: ChatTongyi(
                model=model_name,
                api_key=model_api_key,
                streaming=True,
                model_kwargs={"temperature": temperature},
            ),
            "ollama": lambda: ChatOllama(model=model_name, temperature=temperature, base_url=model_base_url),
        }

        if model_type in model_map:
            return model_map[model_type]()
        else:
            # Should not happen given logic above, but fallback to openai
            return model_map["openai"]()
