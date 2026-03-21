import json

d = {"name": "zhou", "age": "10", "gender": "male"}

s = json.dumps(d)
print(s)


l = [
    {"name": "zho1u", "age": "101", "gender": "male"},
    {"name": "zhou2", "age": "102", "gender": "female"},
    {"name": "zhou3", "age": "103", "gender": "male"},
    {"name": "zhou4", "age": "104", "gender": "female"},
]

a = json.dumps(l)
print(l)


jsonstr = '{"name": "zho1u", "age": "101", "gender": "male"}'
jsonarrystr = json.dumps(l)
res_dict = json.loads(jsonstr)
print(res_dict, type(res_dict))

res_list = json.loads(jsonarrystr)
print(res_list, type(res_list))
