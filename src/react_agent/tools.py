"""This module provides example tools for web scraping and search functionality.

It includes a basic Tavily search function (as an example)

These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

from typing import Any, Callable, List, Optional, cast

from langchain_tavily import TavilySearch  # type: ignore[import-not-found]

from react_agent.configuration import Configuration
import json, os, time
import pandas as pd


# async def search(query: str) -> Optional[dict[str, Any]]:
#     """Search for general web results.

#     This function performs a search using the Tavily search engine, which is designed
#     to provide comprehensive, accurate, and trusted results. It's particularly useful
#     for answering questions about current events.
#     """
#     configuration = Configuration.from_context()
#     wrapped = TavilySearch(max_results=configuration.max_search_results)
#     return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


def summary_csv(file_path: str):
    """Read the csv file and return summary data
    
    This function should be applied before considering what elements should be incorporated into the EDA analysis or hypothesis testing"""

    df = pd.read_csv(os.path.join('data', file_path))
    return df.describe().to_dict()

def generate_notebook(query: str):
    """create the json format of notebook for the given query"""

    description = f"请完成{query}的代码，并封装为ipynb框架的json格式，最终仅返回json。注意：1. Use os.path.join('../data', file_path) for file reading. 2. Use Chinese descriptions. 3. Ensure Chinese characters display correctly in plots if any. 4. Ensure the code is executable. 5. If hypothesis testing is required, the default significance level is 0.05, and conclusions should be described based on this value"

    return description

def save_notebook(notebook):
    """Save the json format of notebook to ipynb file."""
    
    def get_notebook_name():
        return 'notebook_' + str(int(time.time())) + '.ipynb'
    
    file_name = get_notebook_name()
    with open(os.path.join('dest', file_name), 'w', encoding='utf-8') as f:
        json.dump(notebook, f, ensure_ascii=False, indent=1)
    return f"{file_name} 保存成功"


TOOLS: List[Callable[..., Any]] = [generate_notebook, save_notebook, summary_csv]
