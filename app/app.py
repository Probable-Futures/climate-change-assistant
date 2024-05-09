import os
import json
from typing import Dict

from openai import AsyncOpenAI
from openai.types.beta import Thread
from openai.types.beta.threads import (
    MessageContentImageFile,
    MessageContentText,
    ThreadMessage,
)
import chainlit as cl
from typing import Optional
from chainlit.context import context
from decimal import Decimal

import assistant_tools as at
import prompts as pr
import price_helper
import consts


api_key = os.environ.get("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)
assistant_id = os.environ.get("ASSISTANT_ID")


class DictToObject:
    def __init__(self, dictionary):
        for key, value in dictionary.items():
            setattr(self, key, value)


async def process_thread_message(
    message_references: Dict[str, cl.Message], thread_message: ThreadMessage
):
    for idx, content_message in enumerate(thread_message.content):
        id = thread_message.id + str(idx)
        if isinstance(content_message, MessageContentText):
            if id in message_references:
                msg = message_references[id]
                msg.content = content_message.text.value
                await msg.update()
            else:
                message_references[id] = cl.Message(
                    author=thread_message.role, content=content_message.text.value
                )
                await message_references[id].send()
        elif isinstance(content_message, MessageContentImageFile):
            image_id = content_message.image_file.file_id
            response = await client.files.with_raw_response.retrieve_content(image_id)
            elements = [
                cl.Image(
                    name=image_id,
                    content=response.content,
                    display="inline",
                    size="large",
                ),
            ]
            print("trying to display message line 53")

            if id not in message_references:
                message_references[id] = cl.Message(
                    author=thread_message.role,
                    content="",
                    elements=elements,
                )
                await message_references[id].send()
        else:
            print("unknown message type", type(content_message))


@cl.on_chat_start
async def start_chat():
    thread = await client.beta.threads.create()
    cl.user_session.set("thread", thread)
    cl.user_session.set("generated_image_count", 0)
    await cl.Message(
        author="Climate Change Assistant",
        content="Hi! I'm your climate change assistant to help you prepare. What location are you interested in?",
    ).send()


@cl.on_message
async def run_conversation(message_from_ui: cl.Message):
    count = 0
    thread = cl.user_session.get("thread")  # type: Thread
    # Add the message to the thread
    await client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=message_from_ui.content
    )

    # Send empty message to display the loader
    loader_msg = cl.Message(author="assistant", content="")
    await loader_msg.send()

    # Create the run
    run = await client.beta.threads.runs.create(
        thread_id=thread.id, assistant_id=assistant_id
    )

    message_references = {}  # type: Dict[str, cl.Message]

    # Periodically check for updates
    while True:
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )

        # Fetch the run steps
        run_steps = await client.beta.threads.runs.steps.list(
            thread_id=thread.id, run_id=run.id, order="asc"
        )

        for step in run_steps.data:
            # Fetch step details
            run_step = await client.beta.threads.runs.steps.retrieve(
                thread_id=thread.id, run_id=run.id, step_id=step.id
            )
            step_details = run_step.step_details
            # Update step content in the Chainlit UI
            if step_details.type == "message_creation":
                thread_message = await client.beta.threads.messages.retrieve(
                    message_id=step_details.message_creation.message_id,
                    thread_id=thread.id,
                )
                await process_thread_message(message_references, thread_message)

            print("line 116 about the call the tools call loop")
            count += 1
            print(str(count))

            if step_details.type == "tool_calls":
                loading_message = "Retrieving information, please stand by."
                loading_message_to_assistant = cl.Message(
                    author="assistant", content=loading_message
                )
                await loading_message_to_assistant.send()  # output_message_to_assistant.send()

                for tool_call in step_details.tool_calls:
                    print("top of tool call loop line 119")

                    # IF tool call is a disctionary, convert to object
                    if isinstance(tool_call, dict):
                        print("here is a tool call at line 120")
                        print(tool_call)
                        tool_call = DictToObject(tool_call)
                        if tool_call.type == "function":
                            function = DictToObject(tool_call.function)
                            tool_call.function = function
                        if tool_call.type == "code_interpreter":
                            code_interpretor = DictToObject(tool_call.code_interpretor)
                            tool_call.code_interpretor = code_interpretor

                    print("here are step details at line 130")
                    print(step_details)
                    print("here is tool call at line 132")
                    print(tool_call)
                    if tool_call.type == "code_interpreter":
                        if not tool_call.id in message_references:
                            message_references[tool_call.id] = cl.Message(
                                author=tool_call.type,
                                content=tool_call.code_interpreter.input
                                or "# Generating code...",
                                language="python",
                                parent_id=context.session.root_message.id,
                            )
                            await message_references[tool_call.id].send()
                        else:
                            message_references[tool_call.id].content = (
                                tool_call.code_interpreter.input
                                or "# Generating code..."
                            )
                            await message_references[tool_call.id].update()

                        print("here is tool call id in line 151")
                        tool_output_id = tool_call.id + "output"

                        if not tool_output_id in message_references:
                            message_references[tool_output_id] = cl.Message(
                                author=f"{tool_call.type}_result",
                                content=str(tool_call.code_interpreter.outputs) or "",
                                language="json",
                                parent_id=context.session.root_message.id,
                            )
                            await message_references[tool_output_id].send()
                        else:
                            message_references[tool_output_id].content = (
                                str(tool_call.code_interpreter.outputs) or ""
                            )
                            await message_references[tool_output_id].update()

                    elif tool_call.type == "retrieval":
                        if not tool_call.id in message_references:
                            message_references[tool_call.id] = cl.Message(
                                author=tool_call.type,
                                content="Retrieving information",
                                parent_id=context.session.root_message.id,
                            )
                            await message_references[tool_call.id].send()
                    # Note that this assumes some arguments due to some bug with early assistants and chainlit
                    # so be careful for functions that don't have mandatory parameters
                    elif (
                        tool_call.type == "function"
                        and len(tool_call.function.arguments) > 0
                    ):
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        if not tool_call.id in message_references:
                            message_references[tool_call.id] = cl.Message(
                                author=function_name,
                                content=function_args,
                                language="json",
                                # parent_id=context.session.root_message.id,
                            )
                            # await message_references[tool_call.id].send()

                            function_mappings = {
                                "get_pf_data_new": at.get_pf_data_new,
                                "get_current_datetime": at.get_current_datetime,
                            }

                            # Not sure why, but sometimes this is returned rather than name
                            function_name = function_name.replace("_schema", "")

                            print(f"FUNCTION NAME: {function_name}")
                            print(function_args)

                            summary, parsed_output = function_mappings[function_name](
                                **function_args
                            )  # , output, image

                            # img = cl.Image(url=image, name="image1", display="inline", size="large")  # path=image_path,
                            # img = Image.open(filename)

                            print("line 213 bottom of tool loop")

                            if summary is not None:  # output
                                # tool_output_id = tool_call.id + "output"

                                # Send the summary message to the UI first
                                # message_history = cl.user_session.get("thread")
                                # message_history.append({"role": "user", "content": message_from_ui.content})

                                msg = cl.Message(content="")
                                await msg.send()

                                output = ""

                                for part in summary:
                                    if token := part.choices[0].delta.content or "":
                                        output += token
                                        await msg.stream_token(token)

                                await msg.update()

                                loading_message = "Now, let's take a closer look at what life will look like in the future in that city."
                                loading_message_to_assistant = cl.Message(
                                    author="assistant", content=loading_message
                                )
                                await loading_message_to_assistant.send()

                                # Send the story and image to the UI in chunks
                                temperature_output, water_output, land_output = (
                                    at.story_splitter(parsed_output)
                                )

                                story_chunks = [
                                    temperature_output,
                                    water_output,
                                    land_output,
                                ]
                                print("got story chunks")

                                # iterating through this list
                                # prompts_list = [temperature_prompt, water_prompt, land_prompt]

                                for i in range(len(story_chunks)):
                                    output = ""
                                    story = at.story_completion(
                                        pr.prompts_list[i], story_chunks[i]
                                    )

                                    print(story)

                                    msg = cl.Message(content="")
                                    await msg.send()

                                    for part in story:
                                        if token := part.choices[0].delta.content or "":
                                            output += token
                                            await msg.stream_token(token)

                                    await msg.update()

                                    # loading_message_to_assistant = cl.Message(author="assistant",
                                    #                                          content=output)
                                    # await loading_message_to_assistant.send()

                                    # await cl.sleep(10)

                                    print("\n generating image, begin")

                                    generated_image_count = cl.user_session.get(
                                        "generated_image_count"
                                    )
                                    generated_image_count += 1
                                    cl.user_session.set(
                                        "generated_image_count", generated_image_count
                                    )

                                    # uncomment this line/ switch with 283 to run stable diffusion XL with GPU
                                    # img = cl.Image(
                                    #     content=at.get_image_response_SDXL(
                                    #         at.summarizer(output)
                                    #     ),
                                    #     name="image1",
                                    #     display="inline",
                                    #     size="large",
                                    # )  # _SDXL
                                    img = cl.Image(
                                        url=at.get_image_response(
                                            pr.storyboard_prompt, at.summarizer(output)
                                        ),
                                        name="image1",
                                        display="inline",
                                        size="large",
                                    )
                                    print("\n generating image, complete")
                                    image_message_to_assistant = cl.Message(
                                        author="Climate Change Assistant",
                                        content=" ",
                                        elements=[img],
                                    )
                                    await image_message_to_assistant.send()  # output_message_to_assistant.send()

                            await client.beta.threads.runs.submit_tool_outputs(
                                thread_id=thread.id,
                                run_id=run.id,
                                tool_outputs=[
                                    {
                                        "tool_call_id": tool_call.id,
                                        "output": output,
                                    },
                                ],
                            )

        await cl.sleep(1)  # Refresh every second

        print(f"RUN STATUS: {run.status}")

        if run.status in ["cancelled", "failed", "completed", "expired"]:
            if consts.is_dev:
                image_count = cl.user_session.get("generated_image_count")
                print("Count =", image_count)

                all_messages = await client.beta.threads.messages.list(
                    thread_id=thread.id
                )
                [input_tokens, output_tokens] = price_helper.tokens_per_user(
                    all_messages.data[2:]
                )  # skip last two messages
                [tokens_for_last_input_message, tokens_for_last_output_message] = (
                    price_helper.tokens_per_user(all_messages.data[:2])
                )  # tokens of the last 2 messages (top of the list are the latest messages)
                cost = sum(
                    [
                        Decimal(
                            image_count * 0.04
                        ),  # dalle-3 images: Standard 1024×1024 image cost is 0.04
                        price_helper.cost_of_input_tokens_per_model(input_tokens),
                        price_helper.cost_of_output_tokens_per_model(output_tokens),
                        price_helper.cost_of_input_tokens_per_model(
                            tokens_for_last_input_message
                        ),
                        price_helper.cost_of_output_tokens_per_model(
                            tokens_for_last_output_message
                        ),
                        price_helper.cost_of_input_tokens_per_model(
                            input_tokens + output_tokens
                        ),  # the assistant will read all previous messages as input to generate the response
                    ]
                )
                cost_message = cl.Message(
                    author="system",
                    content=f"The minimum total cost for this conversation so far is: ${round(cost, 6)}\n{consts.note_message}",
                )
                await cost_message.send()

            # Wait until the run is done (cancelled, failed, completed, expired)
            while True:
                runs = await client.beta.threads.runs.list(thread_id=thread.id)
                is_completed = True
                for run in runs.data:
                    print("run: ", run)
                    if run.status == "requires_action":
                        await client.beta.threads.runs.cancel(
                            thread_id=thread.id, run_id=run.id
                        )
                    elif run.status not in [
                        "cancelled",
                        "failed",
                        "completed",
                        "expired",
                    ]:
                        is_completed = False
                        break
                if is_completed is True:
                    break
                await cl.sleep(1)

            break


# @cl.oauth_callback
# def oauth_callback(
#     provider_id: str,
#     token: str,
#     raw_user_data: Dict[str, str],
#     default_app_user: cl.AppUser,
# ) -> Optional[cl.AppUser]:
#     return default_app_user
