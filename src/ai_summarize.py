'''
Name: ai_summarize.py
Author: HuangFuSL
Date: 2025-06-07
Description: This script reads a PDF document, summarizes its content using OpenAI's language model, and merges the sections into a coherent summary.

Configuration:
- BASE_URL: The API endpoint
- API_KEY: API key
- MODEL_NAME: The model to use for summarization
'''
from __future__ import annotations

import asyncio
import json
import sys
from typing import Dict, List

import openai
import pymupdf

PDF_FILE = sys.argv[1]
BASE_URL = 'https://api.openai.com/v1'
API_KEY = ''
MODEL_NAME = 'gpt-4.1-mini'
SUMMARIZE_PROMPT = '''
## Role

你是一位经验丰富的学术助手，精通论文阅读与信息提取，尤其擅长在复杂技术论文中梳理关键观点和贡献。

## Instruction

请你阅读接下来给出的论文文本，识别并总结其主要内容。你的总结应重点关注以下内容（当且仅当文本中存在对应内容时）

* 研究问题（作者试图解决什么问题）
* 方法简介（作者是如何解决这个问题的）、简要的方法归属（方法和什么经典方法或已有工作相关）
* 关键贡献或创新点
* 实验或结果简述
* 对结果的讨论

请你针对以上每个部分给出简洁明了的总结。按照相应的格式输出：

## Output

你的最终输出应当：

1. 应当仅包括一个 JSON 对象，**不包含任何额外的文本描述**
2. **不包含markdown格式**等任何不利于直接解析的额外文本
3. 确保Json格式正确，严格使用**双引号**包裹所有键和值
4. 如果页面中不存在某个部分，请**不要编造内容**，而是将对应字段留空即可。

Json包含以下字段。

{
    'introduction': '...',
    'method': '...',
    'contribution': '...',
    'experiment': '...'
    'discussion': '...'
}
'''.strip()
GATHER_PROMPT = '''
## Role

你是一位经验丰富的学术助手，精通论文阅读与信息提取，尤其擅长在复杂技术论文中梳理关键观点和贡献。

## Instruction

以下是一篇论文的{section}部分的内容。请你将这些内容合并成一个完整的段落，确保逻辑连贯、语句通顺。并确保内容保持和原文一致。当内容出现冲突时，以多数内容为准。

## Output

你的输出是一段文本
'''
MERGE_PROMPT = '''
## Role
你是一位经验丰富的学术助手，精通论文阅读与信息提取，尤其擅长在复杂技术论文中梳理关键观点和贡献。

## Instruction
以下是一个论文的各个部分的内容。请你将这些内容用中文合并成一篇文章，以详细介绍这篇论文的主要内容和贡献。你需要确保术语准确、逻辑连贯、语句通顺，不遗漏原文细节。部分术语、缩写等可以保留英文原文。

## Output
你的输出是一段或多段文本。
'''


class Usage():
    # Singleton class to hold usage information
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Usage, cls).__new__(cls)
            cls._instance.input_tokens = 0
            cls._instance.output_tokens = 0
            cls._instance.cached_tokens = 0
        return cls._instance

    def update_usage(self, usage: openai.types.CompletionUsage | None):
        if usage is None:
            return
        self.output_tokens += usage.completion_tokens
        self.input_tokens += usage.prompt_tokens
        if usage.prompt_tokens_details is not None \
                and usage.prompt_tokens_details.cached_tokens is not None:
            self.input_tokens -= usage.prompt_tokens_details.cached_tokens
            self.cached_tokens += usage.prompt_tokens_details.cached_tokens

    def __str__(self):
        return (
            f'Usage(input_tokens={self.input_tokens}, '
            f'output_tokens={self.output_tokens}, '
            f'cached_tokens={self.cached_tokens})'
        )


def read_document(path: str):
    '''
    Reads a PDF document and extracts its text content.

    Args:
        path (str): The file path to the PDF document.
    Returns:
        str: The extracted text content from the PDF.
    '''
    with pymupdf.open(path) as pdf:
        # Extract text
        text = []
        for page_num in range(len(pdf)):
            page = pdf.load_page(page_num)
            text.append(page.get_text())

    return text


async def summarize_content(
    llm: openai.AsyncClient, content: str, sem: asyncio.Semaphore | None = None, retry: int = 5
) -> Dict[str, str]:
    '''
    Summarizes the content using OpenAI's language model.

    Args:
        llm (openai.AsyncClient): The OpenAI client for making requests.
        content (str): The content to summarize.
        sem (asyncio.Semaphore | None): Optional semaphore for limiting concurrency.
        retry (int): Number of retries in case of failure.
    Returns:
        str: The summary of the content.
    '''
    if sem:
        async with sem:
            return await summarize_content(llm, content, None, retry)

    while retry > 0:
        try:
            response = await llm.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {'role': 'system', 'content': SUMMARIZE_PROMPT},
                    {'role': 'user', 'content': content}
                ]
            )
            Usage().update_usage(response.usage)
            summary = response.choices[0].message.content.strip()
            summary_dict = json.loads(summary)
            return {
                'introduction': summary_dict.get('introduction', ''),
                'method': summary_dict.get('method', ''),
                'contribution': summary_dict.get('contribution', ''),
                'experiment': summary_dict.get('experiment', ''),
                'discussion': summary_dict.get('discussion', '')
            }
        except Exception as e:
            await asyncio.sleep(1)
            retry -= 1
    return {
        'introduction': '',
        'method': '',
        'contribution': '',
        'experiment': '',
        'discussion': ''
    }


async def gather_content(
    llm: openai.AsyncClient, section: str, content: List[str],
    sem: asyncio.Semaphore | None = None,
    retry: int = 5
) -> str:
    '''
    Merge multiple content strings into a single string.
    Args:
        llm (openai.AsyncClient): The OpenAI client for making requests.
        content (List[str]): The list of content strings to merge.
        sem (asyncio.Semaphore | None): Optional semaphore for limiting concurrency.
    Returns:
        str: The merged content string.
    '''
    if sem:
        async with sem:
            return await gather_content(llm, section, content, None, retry)
    while retry > 0:
        try:
            response = await llm.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {'role': 'system', 'content': GATHER_PROMPT.format(
                        section=section)},
                    {'role': 'user', 'content': '\n'.join(
                        [f'* {_}' for _ in content])}
                ]
            )
            Usage().update_usage(response.usage)
            return response.choices[0].message.content.strip()
        except Exception as e:
            await asyncio.sleep(1)
            retry -= 1
    return ''


async def merge_sections(
    llm: openai.AsyncClient, document: Dict[str, str],
    sem: asyncio.Semaphore | None = None, retry: int = 5
) -> str:
    '''
    Merges sections of the document into a single string.

    Args:
        llm (openai.AsyncClient): The OpenAI client for making requests.
        document (Dict[str, str]): The document with sections to merge.
        sem (asyncio.Semaphore | None): Optional semaphore for limiting concurrency.
        retry (int): Number of retries in case of failure.
    Returns:
        str: The merged content string.
    '''
    if sem:
        async with sem:
            return await merge_sections(llm, document, None, retry)

    while retry > 0:
        try:
            response = await llm.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {'role': 'system', 'content': MERGE_PROMPT},
                    {'role': 'user', 'content': '\n'.join([
                        f'{key}: {value}' for key, value in document.items()
                    ])}
                ]
            )
            Usage().update_usage(response.usage)
            return response.choices[0].message.content.strip()
        except Exception as e:
            await asyncio.sleep(1)
            retry -= 1
    return ''


async def main():
    '''
    Main function
    '''
    document = read_document(PDF_FILE)
    llm = openai.AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(5)  # Limit concurrent requests
    results = await asyncio.gather(
        *[summarize_content(llm, page, sem) for page in document]
    )

    sections = {}
    for i, result in enumerate(results):
        for key, value in result.items():
            if key not in sections:
                sections[key] = []
            sections[key].append(value)

    gathered_sections = {
        k: v
        for k, v in zip(sections, await asyncio.gather(*[
            gather_content(llm, key, sections[key], sem) for key in sections
        ]))
    }
    merged_content = await merge_sections(llm, gathered_sections, sem)
    print(merged_content)
    print('-' * 20)
    print(Usage())


if __name__ == '__main__':
    if not API_KEY:
        print(f'Please set the API_KEY variable in script {__file__}.')
    asyncio.run(main())
