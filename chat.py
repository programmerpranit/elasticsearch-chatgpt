import os
import streamlit as st
import openai
from elasticsearch import Elasticsearch
import logging

# This code is part of an Elastic Blog showing how to combine
# Elasticsearch's search relevancy power with 
# OpenAI's GPT's Question Answering power
# https://www.elastic.co/blog/chatgpt-elasticsearch-openai-meets-private-data

# Code is presented for demo purposes but should not be used in production
# You may encounter exceptions which are not handled in the code

openai_api = os.environ['openai_api']
cloud_id = os.environ['cloud_id']
cloud_user = os.environ['cloud_user']
cloud_pass = os.environ['cloud_pass']
es_index = os.environ['es_index']
chat_title = os.environ['chat_title']
vector_field = os.environ['vector_field']

openai.api_key = openai_api
model = "gpt-3.5-turbo-0301"

# Connect to Elastic Cloud cluster
def es_connect(cid, user, passwd):
    es = Elasticsearch(cloud_id=cid, basic_auth=(user, passwd))
    return es

# Search ElasticSearch index and return body and URL of the result
def search(query_text):
    cid = cloud_id
    cp = cloud_pass
    cu = cloud_user
    es = es_connect(cid, cu, cp)

    # Elasticsearch query (BM25) and kNN configuration for hybrid search
    query = {
        "bool": {
            "must": [{
                "match": {
                    "title": {
                        "query": query_text,
                        "boost": 1
                    }
                }
            }],
            "filter": [{
                "exists": {
                    "field": vector_field
                }
            }]
        }
    }

    knn = {
        "field": vector_field,
        "k": 1,
        "num_candidates": 20,
        "query_vector_builder": {
            "text_embedding": {
                "model_id": "sentence-transformers__all-distilroberta-v1",
                "model_text": query_text
            }
        },
        "boost": 24
    }

    fields = ["title", "body_content", "url"]
    
    resp = es.search(index=es_index,
                     query=query,
                     knn=knn,
                     fields=fields,
                     size=1,
                     source=False)

    logging.info(resp)
    logging.info("---------------")
    logging.info(resp['hits'])

    body = resp['hits']['hits'][0]['fields']['body_content'][0]
    url = resp['hits']['hits'][0]['fields']['url'][0]

    return body, url

def truncate_text(text, max_tokens):
    tokens = text.split()
    if len(tokens) <= max_tokens:
        return text

    return ' '.join(tokens[:max_tokens])

# Generate a response from ChatGPT based on the given prompt
def chat_gpt(prompt, model="gpt-3.5-turbo", max_tokens=1024, max_context_tokens=4000, safety_margin=5):
    # Truncate the prompt content to fit within the model's context length
    truncated_prompt = truncate_text(prompt, max_context_tokens - max_tokens - safety_margin)

    response = openai.ChatCompletion.create(model=model,
                                            messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": truncated_prompt}])

    return response["choices"][0]["message"]["content"]


st.title(chat_title)

# Main chat form
with st.form("chat_form"):
    query = st.text_input("You: ")
    submit_button = st.form_submit_button("Send")

# Generate and display response on form submission
negResponse = "I'm unable to answer the question based on the information I have from Elastic Docs."
if submit_button:
    resp, url = search(query)
    prompt = f"Answer this question: {query}\nUsing only the information from this Elastic Doc: {resp}\nIf the answer is not contained in the supplied doc reply '{negResponse}' and nothing else"
    answer = chat_gpt(prompt)
    
    if negResponse in answer:
        st.write(f"ChatGPT: {answer.strip()}")
    else:
        st.write(f"ChatGPT: {answer.strip()}\n\nDocs: {url}")
