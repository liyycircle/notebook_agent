from typing import Any, Callable, List, Optional, cast
from react_agent.configuration import Configuration
import json, os, time
import pandas as pd
import requests


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
    requirements = [
        "Use os.path.join('../data', file_path) for file reading. ",
        "Use Chinese descriptions. ",
        "Ensure Chinese characters display correctly in plots if any. ",
        "Ensure the code is executable.",
        "If hypothesis testing is required, the default significance level is 0.05, and conclusions should be described based on this value"
    ]
    description = f"根据要求{requirements},完成{query}的代码，并封装为ipynb框架的json格式，不要做任何发散，直接返回可运行的框架json。"

    return description

def save_notebook(notebook):
    """Save the json format of notebook to ipynb file."""
    
    def get_notebook_name():
        return 'notebook_' + str(int(time.time())) + '.ipynb'
    
    file_name = get_notebook_name()
    with open(os.path.join('dest', file_name), 'w', encoding='utf-8') as f:
        json.dump(notebook, f, ensure_ascii=False, indent=1)
    return f"{file_name} 保存成功"

def gen_notebook(notebook_name: str, notebook: str) -> str:
    """create a jupter notebook from the json schema, named as notebook_name. return success or failed."""

    try:
        notebook = json.loads(notebook)
        with open(os.path.join('dest', f'{notebook_name}.ipynb'), 'w', encoding='utf-8') as f:
            json.dump(notebook, f, ensure_ascii=False, indent=1)
        return f"{notebook_name} 保存成功"
    except Exception as e:
        return f"保存失败: {e}"


def run_notebook(cells: List[int]) -> str:
    """运行 cell list 中的指定 cell，返回运行结果。用于检测生成的notebook是否能正常运行，应当在gen_notebook之后调用
    
    Args:
        cells (List[int]): 要运行的cell索引列表，从0开始
        
    Returns:
        str: 运行结果，包含成功或失败信息
    """
    try:
        # 读取notebook文件
        with open(os.path.join('dest', 'temp.ipynb'), 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        
        # 创建NotebookClient
        client = NotebookClient(nb)
        
        # 只运行指定的cells
        for cell_idx in cells:
            if 0 <= cell_idx < len(nb.cells):
                cell = nb.cells[cell_idx]
                if cell.cell_type == 'code':
                    try:
                        # 执行单个cell
                        client.execute_cell(cell, cell_idx)
                        print(f"Cell {cell_idx} 执行成功")
                    except CellExecutionError as e:
                        print(f"Cell {cell_idx} 执行失败: {str(e)}")
            else:
                print(f"Cell {cell_idx} 不存在")
        
        return "指定cells运行完成"
    except Exception as e:
        return f"运行失败: {str(e)}"

TOOLS: List[Callable[..., Any]] = [generate_notebook, save_notebook]
APP_TOOLS: List[Callable[..., Any]] = [gen_notebook]
