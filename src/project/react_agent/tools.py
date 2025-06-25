from typing import Any, Callable, List, Optional, cast, Annotated
import json, os, time
import pandas as pd
import requests
from pydantic import Field



def gen_notebook(notebook_name: str, notebook: str) -> str:
    """create a jupter notebook following the nbformat, named as notebook_name. the name should follow nnformat. return success or failed.
    nnformat = "summary of the notebook content"_str(uuid.uuid4())[-4:]
    nbformat = {
        "cells": [...],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 或 R",
                "language": "python 或 R",
                "name": "python3 或 R"
            },
            "language_info": {
                "name": "python 或 R",
                "version": ""
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }
    """
    try:
        notebook = json.loads(notebook)
        with open(os.path.join('dest', notebook_name), 'w', encoding='utf-8') as f:
            json.dump(notebook, f, ensure_ascii=False, indent=1)
        return f"{notebook_name} 保存成功"
    except Exception as e:
        return f"保存失败: {e}"

def add_cell(
    content: Annotated[str, Field(description="the content of the jupter notebook cell")],
    cell_type: Annotated[str, Field(description="the type of the jupter notebook cell, use code or markdown")],
    cell_index: Annotated[int, Field(description="insert position, default is -1, which means add to the end")] 
) -> str:
    """add cell to the notebook, the cell type is code or markdown, the default position is the end of the notebook"""
    print("content", content, flush=True)
    print("cell_type", cell_type, flush=True)
    print("cell_index", cell_index, flush=True)
    return "add cell success"

def update_cell_by_id(
    cell_id: Annotated[str, Field(description="the id of the notebook cell, which aims to be updated")],
    new_content: Annotated[str, Field(description="the content to update for the target cell")]
) -> str:
    """update the notebook cell by cell id"""
    print("cell_id", cell_id, "\nnew_content", new_content)


def run_notebook(cells: List[int]) -> str:
    """Run specified cells in the notebook and return execution results. cells is a list of cell id to run. If empty, all cells will be run."""
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


APP_TOOLS: List[Callable[..., Any]] = [gen_notebook, add_cell, update_cell_by_id, run_notebook]
