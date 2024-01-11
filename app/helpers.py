from tiktoken import (
    encoding_for_model,
    get_encoding,
)


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        num_tokens += len(encoding.encode(message))
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def cost_of_input_tokens_per_model(user_tokens, model="gpt-3.5-turbo-0613"):
    user_tokens_cost = 0.0
    if model == "gpt-4-1106-preview" or model == "gpt-4-1106-vision-preview":
        user_tokens_cost = (user_tokens * 0.01) / 1000
    elif model == "gpt-4":
        user_tokens_cost = (user_tokens * 0.03) / 1000
    elif model == "gpt-4-32k":
        user_tokens_cost = (user_tokens * 0.06) / 1000
    elif model == "gpt-3.5-turbo-1106":
        user_tokens_cost = (user_tokens * 0.001) / 1000
    elif "gpt-3.5-turbo" in model:
        return cost_of_input_tokens_per_model(user_tokens, model="gpt-3.5-turbo-1106")
    else:
        raise NotImplementedError(
            f"""cost_of_input_tokens_per_model() is not implemented for model {model}."""
        )
    return user_tokens_cost


def cost_of_output_tokens_per_model(assistant_tokens, model="gpt-3.5-turbo-0613"):
    assistant_tokens_cost = 0.0
    if model == "gpt-4-1106-preview" or model == "gpt-4-1106-vision-preview":
        assistant_tokens_cost = (assistant_tokens * 0.03) / 1000
    elif model == "gpt-4":
        assistant_tokens_cost = (assistant_tokens * 0.06) / 1000
    elif model == "gpt-4-32k":
        assistant_tokens_cost = (assistant_tokens * 0.12) / 1000
    elif model == "gpt-3.5-turbo-1106":
        assistant_tokens_cost = (assistant_tokens * 0.002) / 1000
    elif "gpt-3.5-turbo" in model:
        return cost_of_output_tokens_per_model(assistant_tokens, model="gpt-3.5-turbo-1106")
    else:
        raise NotImplementedError(
            f"""cost_of_output_tokens_per_model() is not implemented for model {model}."""
        )
    return assistant_tokens_cost