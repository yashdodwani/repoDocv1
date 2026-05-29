import json
with open('/home/voyager4/projects/repoDocv1/frontend/package.json', 'r') as f:
    data = json.load(f)
data['overrides'] = {
    "ajv": "^8.12.0",
    "ajv-keywords": "^5.1.0"
}
with open('/home/voyager4/projects/repoDocv1/frontend/package.json', 'w') as f:
    json.dump(data, f, indent=2)
