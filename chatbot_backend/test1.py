import sys
import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.utils import embedding_functions
import re
import concurrent.futures
from tqdm import tqdm
from urllib.parse import urljoin, urlparse
from typing import List, Dict
from langchain_groq import ChatGroq
import os
import json

# Initialize ChromaDB
chroma_client = chromadb.Client()
chroma_collection = chroma_client.get_or_create_collection(
    name="web_content",
    embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
)

# Initialize Groq LLM
os.environ["GROQ_API_KEY"] = "your_valid_groq_api_key"  # Replace with your valid Groq API key
llm = ChatGroq(
    model_name="mixtral-8x7b-32768",
    temperature=0.7,
    max_tokens=4096
)

def crawl_urls(homepage: str, max_pages: int = 100) -> List[str]:
    print(f"Starting crawl from: {homepage}", file=sys.stderr)
    visited = set()
    to_visit = [homepage]
    all_urls = set()

    with tqdm(total=max_pages, desc="Crawling URLs") as pbar:
        while to_visit and len(all_urls) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue

            visited.add(current_url)
            try:
                response = requests.get(current_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                print(f"Crawling: {current_url}", file=sys.stderr)

                soup = BeautifulSoup(response.text, 'html.parser')

                for link in soup.find_all('a', href=True):
                    href = urljoin(current_url, link['href'])
                    parsed_href = urlparse(href)

                    if parsed_href.netloc == urlparse(homepage).netloc:
                        if href not in visited:
                            to_visit.append(href)
                            all_urls.add(href)
                            print(f"Discovered URL: {href}", file=sys.stderr)
                            pbar.update(1)
                            if len(all_urls) >= max_pages:
                                break

            except Exception as e:
                print(f"Error crawling {current_url}: {e}", file=sys.stderr)

    print(f"Discovered URLs: {list(all_urls)}", file=sys.stderr)
    return list(all_urls)

def scrape_urls(urls: List[str]) -> List[Dict]:
    def scrape_single_url(url: str) -> Dict:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()
            text = re.sub(r'[^\w\s.,?!-]', '', text)

            return {"url": url, "content": text, "status": "success"}
        except Exception as e:
            return {"url": url, "content": "", "status": f"error: {str(e)}"}

    print("Starting content scraping...", file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(tqdm(
            executor.map(scrape_single_url, urls),
            total=len(urls),
            desc="Scraping URLs"
        ))

    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\nSuccessfully scraped {success_count} out of {len(urls)} URLs", file=sys.stderr)

    return results

def chunk_text(text: str, chunk_size: int = 1000) -> List[str]:
    words = text.split()
    chunks, current_chunk, current_length = [], [], 0

    for word in words:
        current_length += len(word) + 1
        if current_length > chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def process_and_store(scraped_data: List[Dict]):
    print("Processing and storing content...", file=sys.stderr)
    chroma_docs, chroma_meta, chroma_ids = [], [], []
    doc_counter = 0

    for item in scraped_data:
        if item["status"] == "success" and item["content"]:
            chunks = chunk_text(item["content"])
            for chunk in chunks:
                chroma_docs.append(chunk)
                chroma_meta.append({"url": item["url"]})
                chroma_ids.append(f"doc_{doc_counter}")
                doc_counter += 1

    if chroma_docs:
        chroma_collection.add(
            documents=chroma_docs,
            metadatas=chroma_meta,
            ids=chroma_ids
        )
        print(f"Stored {len(chroma_docs)} chunks in ChromaDB", file=sys.stderr)

def query_and_respond(query: str) -> Dict:
    try:
        print("Querying ChromaDB", file=sys.stderr)
        results = chroma_collection.query(
            query_texts=[query],
            n_results=1
        )

        contexts = [doc for doc in results['documents'][0]]
        print("Retrieved contexts from ChromaDB", file=sys.stderr)

        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context.
        Your answers should be accurate, informative, and directly related to the context provided."""

        user_prompt = f"""Context information is below.
        ---------------------
        {' '.join(contexts)}
        ---------------------
        Given the context information, please answer this question: {query}

        If the context doesn't contain relevant information, please say so instead of making up an answer."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        print("Invoking Groq LLM", file=sys.stderr)
        response = llm.invoke(messages).content
        print("Groq LLM response received", file=sys.stderr)

        return {
            "query": query,
            "response": response,
            "contexts": contexts
        }
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {
            "query": query,
            "response": f"Error processing query: {e}",
            "contexts": []
        }

def chat_interface():
    print("\nWelcome to the website chatbot! Type 'exit' to quit.", file=sys.stderr)
    print("Using Groq's Mixtral-8x7b model for responses...", file=sys.stderr)

    while True:
        query = input("\nEnter your question: ")
        if query.lower() == 'exit':
            break

        print("\nProcessing your question...", file=sys.stderr)
        result = query_and_respond(query)

        print("\nResponse:", result["response"])
        print("\nSources used:")
        for i, context in enumerate(result["contexts"], 1):
            print(f"\n{i}. {context[:200]}...", file=sys.stderr)

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            command = sys.argv[1]
            if command == 'query' and len(sys.argv) > 2:
                query = sys.argv[2]
                result = query_and_respond(query)
                print(json.dumps(result))
            elif command == 'crawl' and len(sys.argv) > 3:
                homepage = sys.argv[2]
                max_pages = int(sys.argv[3])
                result = crawl_urls(homepage, max_pages)
                print(json.dumps(result))
            elif command == 'scrape' and len(sys.argv) > 2:
                urls = json.loads(sys.argv[2])
                result = scrape_urls(urls)
                print(json.dumps(result))
            elif command == 'store' and len(sys.argv) > 2:
                data = json.loads(sys.argv[2])
                process_and_store(data)
                print(json.dumps({"response": "Data stored successfully"}))
            else:
                print(json.dumps({"response": "Invalid command or arguments"}))
        else:
            print(json.dumps({"response": "No command provided"}))
    except Exception as e:
        print(json.dumps({"response": f"Error processing command: {e}"}))
        sys.exit(1)
