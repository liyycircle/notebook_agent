# curl -X POST "http://localhost:8080/app" \
# -H "Content-Type: application/json" \
# -d '{"content": "天气如何"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "生成一个使用iris数据集绘制散点图的notebook", "role": "user", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "同意", "role": "user", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "system_stop", "role": "user", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"role": "tool", "content": "notebook 已生成", "tool_call_id": "call_0_fc59e883-1bc2-40e4-9b48-bb345daa0ed0", "threadid": "3", "status": "success", "tool_name": "gen_notebook"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"role": "tool", "content": "缺少箱线图", "tool_call_id": "call_1_ac0da83b-41ba-4be0-86ba-aba45840bb9c", "threadid": "3", "status": "failed", "tool_name": "run_notebook"}'

--------------------------------

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "hi", "role": "user", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "当前notebook内容如下：undefined，用户指令：是", "threadid": "3"}'

curl -X POST "https://www.heywhale.com/api/model/services/684a43d8d39dde42ade0effa" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"role": "user", "content": "生成", "threadid": "123"}}}'
# -d '{"content": "notebook中如何绘制散点图", "threadid": "123"}'
curl -X POST "https://www.heywhale.com/api/model/services/684a43d8d39dde42ade0effa" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"role": "user", "content": "system_stop", "threadid": "123"}}}'


------------------------
curl -X POST "https://www.heywhale.com/api/model/services/68358645754a7d40325faa4c" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"content": "当前notebook内容如下：{\n  \"_id\": \"68352ca80cd1787176d7d411\",\n  \"Name\": \"test007-notebook copilot demo\",\n  \"Creator\": {\n    \"_id\": \"61765a14de7bb50017397743\",\n    \"Name\": \"test007\",\n    \"Avatar\": \"//cdn.kesci.com/images/avatar/5.jpg\",\n    \"id\": \"61765a14de7bb50017397743\"\n  },\n  \"Language\": \"python\",\n  \"CreateDate\": \"2025-05-27T03:08:24.941Z\",\n  \"UpdateDate\": \"2025-05-28T07:38:35.508Z\",\n  \"Canvas\": {\n    \"_id\": \"68352ca80cd1787176d7d413\",\n    \"Modules\": [],\n    \"Markers\": [],\n    \"Groups\": [],\n    \"RenderedIndex\": {\n      \"_id\": \"68352ca80cd1787176d7d414\",\n      \"Modules\": [],\n      \"Markers\": [],\n      \"Groups\": []\n    },\n    \"Meta\": {\n      \"IdCounter\": 0,\n      \"Width\": 2000,\n      \"Height\": 2000,\n      \"_id\": \"68352ca80cd1787176d7d415\"\n    }\n  },\n  \"Head\": \"68352ca80cd1787176d7d411\",\n  \"Lab\": {\n    \"_id\": \"68352ca80cd1787176d7d402\",\n    \"User\": {\n      \"_id\": \"61765a14de7bb50017397743\",\n      \"id\": \"61765a14de7bb50017397743\"\n    },\n    \"Title\": \"test007-notebook copilot demo\",\n    \"Private\": true,\n    \"OrganizationInfo\": {\n      \"Organization\": \"5abb0216f5628022ef83b213\",\n      \"OrganizationTag\": [],\n      \"AuthorizedGroups\": []\n    },\n    \"AuthorizedMembers\": [],\n    \"CooperateMembers\": [],\n    \"id\": \"68352ca80cd1787176d7d402\",\n    \"permissions\": {\n      \"comment\": true\n    }\n  },\n  \"RenderedContentUrl\": \"https://s3.cn-north-1.amazonaws.com.cn/kesci-nbrender-content/20250527/4a28d783-20be-4c29-a1cc-97f808cb1250.html.gz\",\n  \"Content\": {\n    \"cells\": [\n      {\n        \"cell_type\": \"code\",\n        \"metadata\": {\n          \"id\": \"810CF482643D4985AFA558B9F60AF78D\",\n          \"notebookId\": \"68352ca80cd1787176d7d411\",\n          \"jupyter\": {},\n          \"tags\": [],\n          \"slideshow\": {\n            \"slide_type\": \"slide\"\n          },\n          \"trusted\": true,\n          \"collapsed\": false,\n          \"scrolled\": false,\n          \"runtime\": {\n            \"status\": \"default\",\n            \"execution_status\": null,\n            \"is_visible\": true\n          }\n        },\n        \"source\": \"# 试试这个经典示例\\nprint (\\\"hello ModelWhale\\\")\",\n        \"outputs\": [],\n        \"execution_count\": null,\n        \"prompt\": null\n      }\n    ],\n    \"metadata\": {\n      \"kernelspec\": {\n        \"language\": \"python\",\n        \"display_name\": \"Python 3\",\n        \"name\": \"python3\"\n      },\n      \"language_info\": {\n        \"codemirror_mode\": {\n          \"name\": \"ipython\",\n          \"version\": 3\n        },\n        \"name\": \"python\",\n        \"mimetype\": \"text/x-python\",\n        \"nbconvert_exporter\": \"python\",\n        \"file_extension\": \".py\",\n        \"version\": \"3.5.2\",\n        \"pygments_lexer\": \"ipython3\"\n      }\n    },\n    \"nbformat\": 4,\n    \"nbformat_minor\": 0\n  }\n}，用户指令：test", "threadid": "123"}}}'

curl -X POST "https://www.heywhale.com/api/model/services/6841494d5dc2628efedf2d37" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"role": "user", "content": "system_stop", "threadid": "581cb1a59918c58b531eabe4-6839423f58571bac9108cf2f"}}}'

curl -X POST "https://www.heywhale.com/api/model/services/6837ddc4754a7d4032661a62" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"role": "tool", "status": "success", "content": "notebook 已生成", "tool_call_id": "call_1_fe33f71b-8e5e-45de-86b9-dc126550abde", "threadid": "581cb1a59918c58b531eabe4-684fbb0790ded2a061dc6c40"}}}'

