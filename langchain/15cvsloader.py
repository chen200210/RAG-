from langchain_community.document_loaders import CSVLoader

loader = CSVLoader(file_path="./data/stu.csv", csv_args={"delimiter": "."})

documents = loader.load()
# for document in documents:
#     print(document, type(document))


# .lazy_load

documents2 = loader.lazy_load()
for document in documents2:
    print(document, type(document))
