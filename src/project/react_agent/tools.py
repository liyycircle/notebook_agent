from typing import Any, Callable, List, Optional, cast
import json, os, time
import pandas as pd

def gen_notebook(notebook_name: str, notebook: str) -> str:
    """create a jupter notebook from the json schema, named as notebook_name. return success or failed. the notebook should be runable"""
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


APP_TOOLS: List[Callable[..., Any]] = [gen_notebook]
TOOLS: List[Callable[..., Any]] = [gen_notebook]
