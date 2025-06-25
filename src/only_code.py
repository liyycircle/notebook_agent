from pydantic import BaseModel
import json

class NBCell(BaseModel):
    nbCell: dict
    agentCell: dict

    # TODO: 处理img base64
    def __init__(self, nbCell):
        self.nbCell = nbCell
        self.agentCell = {
            "cell_id": self.nbCell['metadata']['id']
        }
        # if self.cellBody['cell_type']=='code':
        #    for output in self.outputs:
        #       if 'text/html' in output.get('data', {}).keys():
        #           del output['data']['text/html']
        return self.agentCell

def get_valid_nbinfo(content_info):
    valid_dict = json.loads(content_info)
    nb_content = valid_dict['Content']['cells']
    cell_list = [NBCell(cell) for cell in nb_content]