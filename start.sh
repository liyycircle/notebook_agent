# curl -X POST "http://localhost:8080/app" \
# -H "Content-Type: application/json" \
# -d '{"content": "天气如何"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "绘制散点图", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "使用iris数据集", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "确认", "threadid": "3"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "notebook中使用iris数据集绘制散点图", "threadid": "2"}'

curl -X POST "http://localhost:8080/app" \
-H "Content-Type: application/json" \
-d '{"content": "是", "threadid": "2"}'

curl -X POST "https://www.heywhale.com/api/model/services/6837ddc4754a7d4032661a62" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"content": "notebook中如何绘制散点图", "threadid": "123"}}}'
# -d '{"content": "notebook中如何绘制散点图", "threadid": "123"}'

curl -X POST "https://www.heywhale.com/api/model/services/68358645754a7d40325faa4c" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"content": "当前notebook内容如下：{\n  \"_id\": \"68352ca80cd1787176d7d411\",\n  \"Name\": \"test007-notebook copilot demo\",\n  \"Creator\": {\n    \"_id\": \"61765a14de7bb50017397743\",\n    \"Name\": \"test007\",\n    \"Avatar\": \"//cdn.kesci.com/images/avatar/5.jpg\",\n    \"id\": \"61765a14de7bb50017397743\"\n  },\n  \"Language\": \"python\",\n  \"CreateDate\": \"2025-05-27T03:08:24.941Z\",\n  \"UpdateDate\": \"2025-05-28T07:38:35.508Z\",\n  \"Canvas\": {\n    \"_id\": \"68352ca80cd1787176d7d413\",\n    \"Modules\": [],\n    \"Markers\": [],\n    \"Groups\": [],\n    \"RenderedIndex\": {\n      \"_id\": \"68352ca80cd1787176d7d414\",\n      \"Modules\": [],\n      \"Markers\": [],\n      \"Groups\": []\n    },\n    \"Meta\": {\n      \"IdCounter\": 0,\n      \"Width\": 2000,\n      \"Height\": 2000,\n      \"_id\": \"68352ca80cd1787176d7d415\"\n    }\n  },\n  \"Head\": \"68352ca80cd1787176d7d411\",\n  \"Lab\": {\n    \"_id\": \"68352ca80cd1787176d7d402\",\n    \"User\": {\n      \"_id\": \"61765a14de7bb50017397743\",\n      \"id\": \"61765a14de7bb50017397743\"\n    },\n    \"Title\": \"test007-notebook copilot demo\",\n    \"Private\": true,\n    \"OrganizationInfo\": {\n      \"Organization\": \"5abb0216f5628022ef83b213\",\n      \"OrganizationTag\": [],\n      \"AuthorizedGroups\": []\n    },\n    \"AuthorizedMembers\": [],\n    \"CooperateMembers\": [],\n    \"id\": \"68352ca80cd1787176d7d402\",\n    \"permissions\": {\n      \"comment\": true\n    }\n  },\n  \"RenderedContentUrl\": \"https://s3.cn-north-1.amazonaws.com.cn/kesci-nbrender-content/20250527/4a28d783-20be-4c29-a1cc-97f808cb1250.html.gz\",\n  \"Content\": {\n    \"cells\": [\n      {\n        \"cell_type\": \"code\",\n        \"metadata\": {\n          \"id\": \"810CF482643D4985AFA558B9F60AF78D\",\n          \"notebookId\": \"68352ca80cd1787176d7d411\",\n          \"jupyter\": {},\n          \"tags\": [],\n          \"slideshow\": {\n            \"slide_type\": \"slide\"\n          },\n          \"trusted\": true,\n          \"collapsed\": false,\n          \"scrolled\": false,\n          \"runtime\": {\n            \"status\": \"default\",\n            \"execution_status\": null,\n            \"is_visible\": true\n          }\n        },\n        \"source\": \"# 试试这个经典示例\\nprint (\\\"hello ModelWhale\\\")\",\n        \"outputs\": [],\n        \"execution_count\": null,\n        \"prompt\": null\n      }\n    ],\n    \"metadata\": {\n      \"kernelspec\": {\n        \"language\": \"python\",\n        \"display_name\": \"Python 3\",\n        \"name\": \"python3\"\n      },\n      \"language_info\": {\n        \"codemirror_mode\": {\n          \"name\": \"ipython\",\n          \"version\": 3\n        },\n        \"name\": \"python\",\n        \"mimetype\": \"text/x-python\",\n        \"nbconvert_exporter\": \"python\",\n        \"file_extension\": \".py\",\n        \"version\": \"3.5.2\",\n        \"pygments_lexer\": \"ipython3\"\n      }\n    },\n    \"nbformat\": 4,\n    \"nbformat_minor\": 0\n  }\n}，用户指令：test", "threadid": "123"}}}'

curl -X POST "https://www.heywhale.com/api/model/services/683819a75dc2628efebfe4d3" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"content": "notebook中使用iris数据集绘制散点图", "threadid": "1"}}}'

curl -X POST "https://www.heywhale.com/api/model/services/683819a75dc2628efebfe4d3" \
-H "Content-Type: application/json" \
-d '{"content": {"input": {"content": "同意", "threadid": "1"}}}'